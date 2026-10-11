import asyncio
import re
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AssetModel, AssetVersionModel, AuditLogModel, GenerationJobModel
from app.schemas.ai import AssetCreate, GenerationJobCreate
from app.services.ai_generation import AiGenerationError, generate_text
from app.services.ai_provider_registry import get_provider
from app.services.ai_repository import api_key_for, get_configuration
from app.services.asset_storage import AssetStorageError, delete_object, get_bytes, put_bytes


def now() -> datetime:
    return datetime.now(UTC)


def _version(row: AssetVersionModel) -> dict:
    return {
        "id": row.id,
        "version_number": row.version_number,
        "source": row.source,
        "content": row.content,
        "preview_url": row.preview_url,
        "object_key": row.object_key,
        "content_type": row.content_type,
        "file_size": row.file_size,
        "quality_status": row.quality_status,
        "quality_issues": row.quality_issues,
        "created_at": row.created_at,
    }


def _asset(db: Session, row: AssetModel) -> dict:
    versions = db.scalars(
        select(AssetVersionModel)
        .where(AssetVersionModel.asset_id == row.id)
        .order_by(AssetVersionModel.version_number.desc())
    ).all()
    return {
        "id": row.id,
        "product_id": row.product_id,
        "title": row.title,
        "asset_type": row.asset_type,
        "status": row.status,
        "current_version_id": row.current_version_id,
        "tags": row.tags,
        "versions": [_version(version) for version in versions],
        "is_demo": row.is_demo,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def seed_assets(db: Session, organization_id: str) -> None:
    if db.scalar(
        select(AssetModel.id).where(AssetModel.organization_id == organization_id).limit(1)
    ):
        return
    timestamp = now()
    examples = [
        (
            "春季保湿面霜·主图文案",
            "copy",
            "product-10028",
            "主图卖点：轻盈不粘，换季也能稳住肌肤水润感。",
            ["主图", "保湿", "已质检"],
        ),
        (
            "柔肤面霜·详情页结构",
            "template",
            "product-10028",
            "首屏利益点\n成分与功效\n使用方法\n用户信任\n售后保障",
            ["详情页", "模板"],
        ),
        (
            "新品种草短视频脚本",
            "video_script",
            "product-10031",
            "3 秒痛点开场：换季干燥、上妆卡粉怎么办？\n"
            "镜头 2：展示质地\n镜头 3：使用前后对比\n结尾：引导进店",
            ["短视频", "待确认"],
        ),
    ]
    for title, asset_type, product_id, content, tags in examples:
        asset_id = f"asset-{uuid4().hex[:16]}"
        version_id = f"assetver-{uuid4().hex[:16]}"
        version = AssetVersionModel(
            id=version_id,
            asset_id=asset_id,
            version_number=1,
            source="demo",
            content=content,
            preview_url=None,
            quality_status="passed",
            quality_issues=[],
            created_at=timestamp,
        )
        db.add(
            AssetModel(
                id=asset_id,
                organization_id=organization_id,
                product_id=product_id,
                title=title,
                asset_type=asset_type,
                status="approved" if "已质检" in tags else "review",
                current_version_id=version_id,
                tags=tags,
                is_demo=True,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        db.add(version)
    db.commit()


def list_assets(db: Session, organization_id: str, asset_type: str | None = None) -> dict:
    seed_assets(db, organization_id)
    query = (
        select(AssetModel)
        .where(AssetModel.organization_id == organization_id)
        .order_by(AssetModel.updated_at.desc())
    )
    if asset_type:
        query = query.where(AssetModel.asset_type == asset_type)
    rows = db.scalars(query).all()
    return {"items": [_asset(db, row) for row in rows], "total": len(rows), "is_demo": True}


def create_asset(
    db: Session, organization_id: str, payload: AssetCreate, source: str = "manual"
) -> dict:
    timestamp = now()
    asset_id = f"asset-{uuid4().hex[:16]}"
    version_id = f"assetver-{uuid4().hex[:16]}"
    version = AssetVersionModel(
        id=version_id,
        asset_id=asset_id,
        version_number=1,
        source=source,
        content=payload.content,
        quality_status="pending",
        quality_issues=[],
        created_at=timestamp,
    )
    row = AssetModel(
        id=asset_id,
        organization_id=organization_id,
        product_id=payload.product_id,
        title=payload.title,
        asset_type=payload.asset_type.value,
        status="review",
        current_version_id=version_id,
        tags=payload.tags,
        is_demo=source == "demo",
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(row)
    db.add(version)
    db.commit()
    db.refresh(row)
    return _asset(db, row)



def create_uploaded_asset(
    db: Session,
    organization_id: str,
    title: str,
    asset_type: str,
    content: bytes,
    content_type: str,
    filename: str,
    product_id: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Persist an uploaded binary as a reviewable asset version.

    Storage is written before the database transaction is committed. If the DB write
    fails, the object is removed best-effort so an upload cannot leave an orphaned file.
    """
    asset_id = f"asset-{uuid4().hex[:16]}"
    version_id = f"assetver-{uuid4().hex[:16]}"
    safe_name = re.sub(r"[^0-9A-Za-z._-]+", "_", filename).strip("._") or "asset"
    object_key = f"{organization_id}/assets/{asset_id}/{version_id}-{safe_name}"
    stored = put_bytes(object_key, content, content_type)
    timestamp = now()
    try:
        preview_url = f"/api/v1/assets/versions/{version_id}/preview"
        if content_type.startswith("text/"):
            preview_content = content.decode("utf-8", errors="replace")[:20000]
        else:
            preview_content = f"文件素材：{filename}"
        version = AssetVersionModel(
            id=version_id,
            asset_id=asset_id,
            version_number=1,
            source="upload",
            content=preview_content,
            preview_url=preview_url,
            object_key=stored.object_key,
            content_type=stored.content_type,
            file_size=stored.file_size,
            quality_status="pending",
            quality_issues=["尚未完成平台尺寸、敏感词与版权检查"],
            created_at=timestamp,
        )
        row = AssetModel(
            id=asset_id,
            organization_id=organization_id,
            product_id=product_id,
            title=title,
            asset_type=asset_type,
            status="review",
            current_version_id=version_id,
            tags=list(tags or []) + ["待质检"],
            is_demo=False,
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(row)
        db.add(version)
        db.commit()
        db.refresh(row)
        return _asset(db, row)
    except Exception:
        db.rollback()
        try:
            delete_object(object_key)
        except AssetStorageError:
            pass
        raise


def get_asset_version_for_preview(
    db: Session, organization_id: str, version_id: str
) -> AssetVersionModel:
    version = db.scalar(
        select(AssetVersionModel)
        .join(AssetModel, AssetModel.id == AssetVersionModel.asset_id)
        .where(
            AssetVersionModel.id == version_id,
            AssetModel.organization_id == organization_id,
        )
    )
    if version is None or not version.object_key:
        raise ValueError("素材预览不存在")
    return version


def read_asset_preview(
    db: Session, organization_id: str, version_id: str
) -> tuple[bytes, str]:
    version = get_asset_version_for_preview(db, organization_id, version_id)
    content, detected_type = get_bytes(version.object_key or "")
    return content, version.content_type or detected_type

def confirm_asset_version(
    db: Session, organization_id: str, asset_id: str, version_id: str, actor: str
) -> dict:
    asset = db.scalar(
        select(AssetModel).where(
            AssetModel.id == asset_id,
            AssetModel.organization_id == organization_id,
        )
    )
    if asset is None:
        raise ValueError("素材不存在")
    version = db.scalar(
        select(AssetVersionModel).where(
            AssetVersionModel.id == version_id,
            AssetVersionModel.asset_id == asset_id,
        )
    )
    if version is None:
        raise ValueError("素材版本不存在")
    timestamp = now()
    asset.current_version_id = version.id
    asset.status = "approved"
    asset.updated_at = timestamp
    tags = list(asset.tags or [])
    tags = [tag for tag in tags if tag not in {"待确认", "草稿"}]
    if "已确认" not in tags:
        tags.append("已确认")
    asset.tags = tags
    db.add(
        AuditLogModel(
            id=f"audit-{uuid4().hex[:16]}",
            job_id=None,
            domain="asset",
            entity_id=asset.id,
            entity_reference=version.id,
            action="confirm_asset_version",
            action_label="确认素材版本",
            actor=actor,
            result="succeeded",
            note="运营人工确认候选素材版本；未自动发布或覆盖平台线上素材。",
            metadata_json={"version_number": version.version_number, "source": version.source},
            is_demo=asset.is_demo,
            created_at=timestamp,
        )
    )
    db.commit()
    db.refresh(asset)
    return _asset(db, asset)

def get_job(db: Session, organization_id: str, job_id: str) -> GenerationJobModel:
    row = db.scalar(
        select(GenerationJobModel).where(
            GenerationJobModel.id == job_id, GenerationJobModel.organization_id == organization_id
        )
    )
    if row is None:
        raise ValueError("生成任务不存在")
    return row


def serialize_job(row: GenerationJobModel) -> dict:
    return {
        "id": row.id,
        "asset_id": row.asset_id,
        "asset_type": row.asset_type,
        "prompt": row.prompt,
        "model_id": row.model_id,
        "status": row.status,
        "progress": row.progress,
        "result_version_id": row.result_version_id,
        "error_message": row.error_message,
        "is_demo": row.is_demo,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def create_generation_job(
    db: Session, organization_id: str, payload: GenerationJobCreate, model_id: str
) -> dict:
    timestamp = now()
    row = GenerationJobModel(
        id=f"gen-{uuid4().hex[:16]}",
        organization_id=organization_id,
        asset_id=payload.asset_id,
        configuration_id=payload.configuration_id,
        asset_type=payload.asset_type.value,
        prompt=payload.prompt,
        model_id=model_id,
        status="queued",
        progress=0,
        is_demo=payload.configuration_id is None or model_id.startswith("demo-"),
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_job(row)


def execute_generation_job(db: Session, job_id: str) -> None:
    row = db.get(GenerationJobModel, job_id)
    if not row:
        return
    row.status = "running"
    row.progress = 45
    row.updated_at = now()
    db.flush()

    live_generation = False
    try:
        if row.configuration_id:
            configuration = get_configuration(db, row.organization_id, row.configuration_id)
            provider = get_provider(configuration.provider_id)
            if provider.id != "mock":
                if not get_settings().ai_live_generation_enabled:
                    raise AiGenerationError(
                        "真实模型生成默认关闭，请设置 AI_LIVE_GENERATION_ENABLED=true 后重试"
                    )
                live_generation = True
                generated = asyncio.run(
                    generate_text(
                        provider,
                        configuration.base_url,
                        api_key_for(configuration),
                        row.model_id,
                        row.prompt,
                        row.asset_type,
                    )
                )
            else:
                generated = None
        else:
            generated = None

        if generated is not None:
            label = {
                "copy": "AI 候选文案",
                "video_script": "AI 候选脚本",
                "template": "AI 候选模板",
            }.get(row.asset_type, "AI 候选素材")
            content = f"【{label}】\n{generated}\n\n候选结果需要运营确认后保存，不会自动发布。"
        elif row.asset_type == "copy":
            content = (
                f"【AI 候选文案】\n{row.prompt}\n\n"
                "卖点建议：突出使用场景、核心利益点和信任背书。\n\n"
                "演示说明：候选结果需要运营确认后保存。"
            )
        elif row.asset_type == "video_script":
            content = (
                f"【AI 候选脚本】\n开场 3 秒：{row.prompt}\n"
                "镜头 2：展示产品质地与使用动作\n镜头 3：补充真实场景与利益点\n"
                "结尾：引导查看商品详情\n\n演示结果，不会自动发布。"
            )
        else:
            content = (
                f"【AI 素材创意方案】\n{row.prompt}\n\n"
                "画面建议：主体清晰、留出平台标题安全区，使用统一品牌色。\n\n"
                "演示结果，不会自动覆盖线上素材。"
            )

        version_id = f"assetver-{uuid4().hex[:16]}"
        if row.asset_id:
            asset = db.get(AssetModel, row.asset_id)
            if not asset or asset.organization_id != row.organization_id:
                raise ValueError("生成任务关联的素材不存在")
        else:
            asset_id = f"asset-{uuid4().hex[:16]}"
            asset = AssetModel(
                id=asset_id,
                organization_id=row.organization_id,
                product_id=None,
                title=f"AI 生成·{row.asset_type}",
                asset_type=row.asset_type,
                status="review",
                current_version_id=None,
                tags=["AI 生成", "待确认"],
                is_demo=not live_generation,
                created_at=now(),
                updated_at=now(),
            )
            db.add(asset)
            row.asset_id = asset_id
        latest = (
            db.scalar(
                select(func.max(AssetVersionModel.version_number)).where(
                    AssetVersionModel.asset_id == asset.id
                )
            )
            or 0
        )
        version = AssetVersionModel(
            id=version_id,
            asset_id=asset.id,
            version_number=latest + 1,
            source="ai" if live_generation else "ai-demo",
            content=content,
            preview_url=None,
            quality_status="pending",
            quality_issues=["未完成真实平台敏感词与版权检查"],
            created_at=now(),
        )
        db.add(version)
        asset.current_version_id = version_id
        asset.updated_at = now()
        if live_generation:
            asset.is_demo = False
        row.result_version_id = version_id
        row.is_demo = not live_generation
        row.status = "succeeded"
        row.progress = 100
        row.error_message = None
        row.updated_at = now()
        db.commit()
    except Exception as exc:
        row.status = "failed"
        row.progress = 100
        row.error_message = str(exc)[:500]
        row.updated_at = now()
        db.commit()



