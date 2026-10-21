"""内容发布工作台（抖音内容投稿）路由。

职责边界：
- 连接：复用平台无关 OAuth state，保存用户 access_token（加密）到 platform=douyin_content 连接；
- 草稿：仅本地落库，不触达平台；
- 发布：校验授权 + 拉取视频二进制 + 调用抖音内容投稿接口，缺授权/缺视频显式失败。
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import require_demo_user
from app.db.session import get_db
from app.integrations.douyin_content import DouyinContentApiError, DouyinContentClient
from app.schemas.auth import UserProfile
from app.schemas.content_studio import (
    ContentConnectAuthorize,
    ContentConnectCallback,
    ContentConnectStatus,
    ContentDisconnect,
    ContentPublish,
    ContentPublishCreate,
    ContentPublishList,
)
from app.schemas.integrations import ConnectorState
from app.services import content_connections
from app.services.content_publish_service import (
    ContentPublishError,
    create_draft,
    list_publishes,
    publish_content,
)
from app.services.oauth_state import OAuthStateError
from app.services.token_cipher import TokenCipher, TokenEncryptionConfigurationError

router = APIRouter(prefix="/content-studio", tags=["content-studio"])


def _require_cipher(settings: Settings) -> TokenCipher:
    try:
        return TokenCipher(settings.token_encryption_keys or "")
    except TokenEncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _configured_content_client(settings: Settings) -> DouyinContentClient:
    missing = content_connections.missing_content_configuration(settings)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "douyin_content_credentials_required",
                "message": "抖音内容开放应用服务端配置不完整",
                "missing": missing,
            },
        )
    return DouyinContentClient(
        client_key=settings.douyin_content_client_key or "",
        client_secret=settings.douyin_content_client_secret or "",
        redirect_uri=settings.douyin_content_redirect_uri or "",
        api_base_url=settings.douyin_content_api_base_url,
        timeout_seconds=settings.douyin_content_timeout_seconds,
    )


@router.get("/connect/status", response_model=ContentConnectStatus)
def content_connect_status(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ContentConnectStatus:
    settings = get_settings()
    connection = content_connections.get_content_connection(db, user.organization_id)
    if content_connections.missing_content_configuration(settings):
        return ContentConnectStatus(
            state=ConnectorState.CREDENTIALS_REQUIRED,
            message="服务端未配置抖音内容开放应用凭证",
        )
    if connection is None or connection.state != ConnectorState.READY.value:
        return ContentConnectStatus(
            state=ConnectorState.AUTHORIZATION_REQUIRED,
            message="尚未授权抖音内容账号",
            last_error=connection.last_error if connection else None,
        )
    return ContentConnectStatus(
        state=ConnectorState.READY,
        platform_user_name=connection.platform_user_name,
        scopes=connection.scopes or [],
        authorized_at=connection.authorized_at,
        message="抖音内容账号已连接",
    )


@router.post("/connect/authorize", response_model=ContentConnectAuthorize)
def content_connect_authorize(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ContentConnectAuthorize:
    settings = get_settings()
    client = _configured_content_client(settings)
    _require_cipher(settings)
    raw_state, expires_at = content_connections.create_oauth_state(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        redirect_uri=settings.douyin_content_redirect_uri or "",
        ttl_seconds=settings.oauth_state_ttl_seconds,
    )
    return ContentConnectAuthorize(
        authorization_url=client.build_authorization_url(raw_state),
        expires_at=expires_at,
    )


@router.get("/connect/callback", response_model=ContentConnectCallback)
async def content_connect_callback(
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[str | None, Query(min_length=1, max_length=2000)] = None,
    oauth_state: Annotated[str | None, Query(alias="state", min_length=32, max_length=500)] = None,
    error: Annotated[str | None, Query(max_length=200)] = None,
    error_description: Annotated[str | None, Query(max_length=1000)] = None,
) -> ContentConnectCallback:
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_description or error,
        )
    if not code or not oauth_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="抖音内容 OAuth 回调缺少 code 或 state",
        )
    try:
        state_record = content_connections.consume_oauth_state(db, oauth_state)
    except OAuthStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    settings = get_settings()
    client = _configured_content_client(settings)
    client.redirect_uri = state_record.redirect_uri
    try:
        cipher = _require_cipher(settings)
        token = await client.exchange_code(code)
        connection = content_connections.save_authorized_connection(
            db,
            organization_id=state_record.organization_id,
            client_key=settings.douyin_content_client_key or "",
            token=token,
            cipher=cipher,
        )
    except (DouyinContentApiError, TokenEncryptionConfigurationError) as exc:
        content_connections.save_connection_error(db, state_record.organization_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="抖音内容授权失败，请重新发起授权",
        ) from exc

    return ContentConnectCallback(
        state=ConnectorState.READY,
        platform_user_name=connection.platform_user_name or "抖音用户",
        authorized_at=connection.authorized_at or connection.updated_at,
    )


@router.post("/connect/disconnect", response_model=ContentDisconnect)
def content_disconnect(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ContentDisconnect:
    disconnected_at = content_connections.disconnect_content(db, user.organization_id)
    return ContentDisconnect(
        platform="douyin_content",
        state=ConnectorState.REVOKED,
        disconnected_at=disconnected_at,
    )


@router.post("/publishes", response_model=ContentPublish, status_code=201)
def create_content_draft(
    payload: ContentPublishCreate,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ContentPublish:
    return ContentPublish(
        **create_draft(
            db,
            user.organization_id,
            title=payload.title,
            text=payload.text,
            video_url=payload.video_url,
            cover_url=payload.cover_url,
        )
    )


@router.get("/publishes", response_model=ContentPublishList)
def list_content_publishes(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ContentPublishList:
    return ContentPublishList(items=list_publishes(db, user.organization_id))


@router.post("/publishes/{publish_id}/publish", response_model=ContentPublish)
def publish_content_route(
    publish_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ContentPublish:
    """真实投稿到抖音。未授权/缺视频/平台异常时显式失败，不伪造成功。"""
    try:
        result = publish_content(db, user.organization_id, publish_id)
    except ContentPublishError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return ContentPublish(**result)
