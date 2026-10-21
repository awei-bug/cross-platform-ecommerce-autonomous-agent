"""内容发布服务：草稿管理与抖音内容投稿的真实调用。

草稿只落本地库，不触达任何平台。发布时：
1. 校验草稿状态为 draft；
2. 校验抖音内容账号已授权（platform=douyin_content 且状态 ready，access_token 可解密）；
3. 拉取视频二进制（草稿的 video_url），调用 DouyinContentClient.create_video；
4. 成功翻 is_demo=False 并落 external_id；失败写 error_message 与 failed 状态。

未授权或缺少视频时一律显式报错，绝不以演示数据冒充真实发布成功。
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import ContentPublishModel
from app.integrations.douyin_content import DouyinContentApiError, DouyinContentClient
from app.services.content_connections import (
    get_content_connection,
    missing_content_configuration,
)
from app.services.token_cipher import TokenCipher, TokenDecryptionError

DEFAULT_ORG = "org-demo-001"
PUBLISH_MAX_VIDEO_BYTES = 200 * 1024 * 1024  # 抖音开放平台视频上限约 200MB


class ContentPublishError(RuntimeError):
    """业务校验或平台调用失败（非代码异常），调用方映射为 4xx/5xx。"""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def create_draft(
    db: Session,
    organization_id: str,
    *,
    title: str,
    text: str,
    video_url: str | None = None,
    cover_url: str | None = None,
) -> dict:
    now = _utc_now()
    model = ContentPublishModel(
        id=f"cp-{uuid4().hex}",
        organization_id=organization_id,
        platform="douyin",
        title=title.strip()[:200],
        text=text.strip()[:2000],
        video_url=(video_url or "").strip()[:1000] or None,
        cover_url=(cover_url or "").strip()[:1000] or None,
        status="draft",
        is_demo=False,
        created_at=now,
        updated_at=now,
    )
    db.add(model)
    db.commit()
    return _serialize(model)


def list_publishes(db: Session, organization_id: str) -> list[dict]:
    rows = db.scalars(
        select(ContentPublishModel)
        .where(ContentPublishModel.organization_id == organization_id)
        .order_by(ContentPublishModel.created_at.desc())
    ).all()
    return [_serialize(row) for row in rows]


def get_publish(db: Session, organization_id: str, publish_id: str) -> dict | None:
    row = db.scalar(
        select(ContentPublishModel).where(
            ContentPublishModel.id == publish_id,
            ContentPublishModel.organization_id == organization_id,
        )
    )
    return _serialize(row) if row is not None else None


def _build_client(settings: Settings) -> DouyinContentClient:
    return DouyinContentClient(
        client_key=settings.douyin_content_client_key or "",
        client_secret=settings.douyin_content_client_secret or "",
        redirect_uri=settings.douyin_content_redirect_uri or "",
        api_base_url=settings.douyin_content_api_base_url,
        timeout_seconds=settings.douyin_content_timeout_seconds,
    )


async def _fetch_video_bytes(
    video_url: str, *, transport: httpx.AsyncBaseTransport | None
) -> bytes:
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        response = await client.get(video_url)
        response.raise_for_status()
        data = response.content
    if not data:
        raise ContentPublishError("视频链接返回了空内容")
    if len(data) > PUBLISH_MAX_VIDEO_BYTES:
        raise ContentPublishError("视频文件超过 200MB，无法投稿到抖音")
    return data


def publish_content(
    db: Session,
    organization_id: str,
    publish_id: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """真实投稿到抖音。缺授权或缺视频时显式失败，不做任何伪造。"""
    settings = get_settings()
    missing = missing_content_configuration(settings)
    if missing:
        raise ContentPublishError(
            "尚未配置抖音内容开放应用凭证（缺少 "
            + "、".join(missing)
            + "）；个人可在抖音开放平台创建开放应用并申请「投稿到抖音」能力"
        )

    row = db.scalar(
        select(ContentPublishModel).where(
            ContentPublishModel.id == publish_id,
            ContentPublishModel.organization_id == organization_id,
        )
    )
    if row is None:
        raise ContentPublishError("内容草稿不存在")
    if row.status != "draft":
        raise ContentPublishError("该内容已发布或非草稿状态，无法重复发布")

    connection = get_content_connection(db, organization_id)
    if connection is None or connection.state != "ready" or not connection.encrypted_access_token:
        db.commit()
        raise ContentPublishError("尚未授权抖音内容账号，请先在内容工作台连接")

    try:
        cipher = TokenCipher(settings.token_encryption_keys or "")
        access_token = cipher.decrypt(connection.encrypted_access_token)
    except TokenDecryptionError as exc:
        raise ContentPublishError("抖音内容令牌无法解密，请重新授权") from exc

    if not row.video_url:
        raise ContentPublishError("缺少视频文件或链接，无法投稿")

    client = _build_client(settings)
    client.transport = transport

    # 同步拉取视频二进制（发布为同步 HTTP 调用链，便于契约测试注入 transport）。
    try:
        import asyncio

        video = asyncio.run(
            _fetch_video_bytes(row.video_url, transport=transport)
        )
    except (httpx.HTTPError, ContentPublishError) as exc:
        row.status = "failed"
        row.error_message = f"视频拉取失败：{exc}"
        row.updated_at = _utc_now()
        db.commit()
        raise ContentPublishError(f"视频拉取失败：{exc}") from exc

    try:
        result = asyncio.run(
            client.create_video(
                access_token,
                title=row.title,
                text=row.text,
                video=video,
                filename="content.mp4",
                cover_url=row.cover_url,
            )
        )
    except DouyinContentApiError as exc:
        row.status = "failed"
        row.error_message = str(exc)[:1000]
        row.updated_at = _utc_now()
        db.commit()
        raise ContentPublishError(f"抖音投稿失败：{exc}") from exc

    row.status = "published"
    row.external_id = result.get("item_id")
    row.external_url = f"https://www.douyin.com/video/{result.get('item_id')}"
    row.is_demo = False
    row.error_message = None
    row.updated_at = _utc_now()
    db.commit()
    return _serialize(row)


def _serialize(row: ContentPublishModel) -> dict:
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "platform": row.platform,
        "title": row.title,
        "text": row.text,
        "video_url": row.video_url,
        "cover_url": row.cover_url,
        "status": row.status,
        "external_id": row.external_id,
        "external_url": row.external_url,
        "error_message": row.error_message,
        "is_demo": row.is_demo,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
