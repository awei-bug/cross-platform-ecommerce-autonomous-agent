from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AiConfigurationModel, AiDiscoveredModelModel
from app.schemas.ai import AiConfigurationCreate, AiConfigurationPatch
from app.services.ai_provider_registry import get_provider, mask_secret
from app.services.token_cipher import TokenCipher


def now() -> datetime:
    return datetime.now(UTC)


def _cipher() -> TokenCipher:
    return TokenCipher(get_settings().token_encryption_keys or "")


def _validate_api_key(value: str) -> str:
    """Reject pasted junk before it is encrypted and stored.

    A pasted error message (with spaces) used to be accepted silently and only
    surfaced as a confusing 401 much later, so validate the shape up front.
    """
    candidate = value.strip()
    if not candidate:
        raise ValueError("API Key 不能为空")
    if any(char.isspace() for char in candidate):
        raise ValueError("API Key 不能包含空格或换行，请重新完整复制后粘贴")
    if len(candidate) < 16:
        raise ValueError("API Key 长度异常，请确认复制完整")
    return candidate


def _to_model(row: AiConfigurationModel, models: list[AiDiscoveredModelModel]) -> dict:
    provider = get_provider(row.provider_id)
    api_key = _cipher().decrypt(row.encrypted_api_key) if row.encrypted_api_key else None
    return {
        "id": row.id,
        "provider_id": row.provider_id,
        "provider_name": provider.name,
        "display_name": row.display_name,
        "base_url": row.base_url,
        "api_key_masked": mask_secret(api_key),
        "selected_model": row.selected_model,
        "status": row.status,
        "last_tested_at": row.last_tested_at,
        "last_error": row.last_error,
        "is_enabled": row.is_enabled,
        "is_demo": row.is_demo,
        "models": [
            {
                "id": item.id,
                "model_id": item.model_id,
                "display_name": item.display_name,
                "capabilities": item.capabilities,
                "is_free": item.is_free,
                "discovered_at": item.discovered_at,
            }
            for item in models
        ],
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_configurations(db: Session, organization_id: str) -> list[dict]:
    rows = db.scalars(
        select(AiConfigurationModel)
        .where(AiConfigurationModel.organization_id == organization_id)
        .order_by(AiConfigurationModel.created_at)
    ).all()
    return [
        _to_model(
            row,
            db.scalars(
                select(AiDiscoveredModelModel)
                .where(AiDiscoveredModelModel.configuration_id == row.id)
                .order_by(
                    AiDiscoveredModelModel.is_free.desc().nulls_last(),
                    AiDiscoveredModelModel.model_id,
                )
            ).all(),
        )
        for row in rows
    ]


def get_configuration(
    db: Session, organization_id: str, configuration_id: str
) -> AiConfigurationModel:
    row = db.scalar(
        select(AiConfigurationModel).where(
            AiConfigurationModel.id == configuration_id,
            AiConfigurationModel.organization_id == organization_id,
        )
    )
    if row is None:
        raise ValueError("AI 配置不存在")
    return row


def serialize_configuration(db: Session, row: AiConfigurationModel) -> dict:
    models = db.scalars(
        select(AiDiscoveredModelModel)
        .where(AiDiscoveredModelModel.configuration_id == row.id)
        .order_by(
            AiDiscoveredModelModel.is_free.desc().nulls_last(),
            AiDiscoveredModelModel.model_id,
        )
    ).all()
    return _to_model(row, models)


def create_configuration(db: Session, organization_id: str, payload: AiConfigurationCreate) -> dict:
    provider = get_provider(payload.provider_id)
    existing = db.scalar(
        select(AiConfigurationModel).where(
            AiConfigurationModel.organization_id == organization_id,
            AiConfigurationModel.provider_id == provider.id,
        )
    )
    if existing:
        raise ValueError("该厂商已经配置，请在原配置上更新")
    if provider.requires_api_key and not payload.api_key:
        raise ValueError("该厂商需要 API Key")
    if payload.api_key:
        _validate_api_key(payload.api_key)
    timestamp = now()
    row = AiConfigurationModel(
        id=f"aicfg-{uuid4().hex[:16]}",
        organization_id=organization_id,
        provider_id=provider.id,
        display_name=payload.display_name or provider.name,
        base_url=(payload.base_url or provider.default_base_url).rstrip("/"),
        encrypted_api_key=_cipher().encrypt(payload.api_key) if payload.api_key else None,
        selected_model=payload.selected_model,
        status="not_tested",
        is_enabled=True,
        is_demo=provider.id == "mock",
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_configuration(db, row)


def patch_configuration(
    db: Session, organization_id: str, configuration_id: str, payload: AiConfigurationPatch
) -> dict:
    row = get_configuration(db, organization_id, configuration_id)
    values = payload.model_dump(exclude_unset=True)
    if "base_url" in values and values["base_url"]:
        values["base_url"] = values["base_url"].rstrip("/")
    if "api_key" in values:
        raw_key = values.pop("api_key")
        if raw_key:
            _validate_api_key(raw_key)
        values["encrypted_api_key"] = _cipher().encrypt(raw_key) if raw_key else None
    values.pop("api_key", None)
    for key, value in values.items():
        setattr(row, key, value)
    row.status = "not_tested"
    row.last_error = None
    row.updated_at = now()
    db.commit()
    db.refresh(row)
    return serialize_configuration(db, row)


def save_models(db: Session, row: AiConfigurationModel, model_rows: list[dict]) -> list[dict]:
    db.execute(
        delete(AiDiscoveredModelModel).where(AiDiscoveredModelModel.configuration_id == row.id)
    )
    discovered_at = now()
    for model in model_rows:
        db.add(
            AiDiscoveredModelModel(
                id=f"aimodel-{uuid4().hex[:16]}",
                configuration_id=row.id,
                provider_id=row.provider_id,
                model_id=model["model_id"],
                display_name=model["display_name"],
                capabilities=model["capabilities"],
                is_free=model.get("is_free"),
                discovered_at=discovered_at,
            )
        )
    db.commit()
    return model_rows


def api_key_for(row: AiConfigurationModel) -> str | None:
    return _cipher().decrypt(row.encrypted_api_key) if row.encrypted_api_key else None
