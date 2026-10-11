from datetime import UTC
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import require_demo_user
from app.db.session import get_db
from app.schemas.ai import (
    AiConfigurationCreate,
    AiConfigurationListResponse,
    AiConfigurationPatch,
    AiConnectionTestResponse,
    AiModelProbeResponse,
    AiProviderCatalogItem,
)
from app.schemas.auth import UserProfile
from app.services.ai_generation import AiGenerationError, generate_text
from app.services.ai_provider_registry import PROVIDERS, discover_models, get_provider
from app.services.ai_repository import (
    api_key_for,
    create_configuration,
    get_configuration,
    list_configurations,
    patch_configuration,
    save_models,
    serialize_configuration,
)

router = APIRouter(prefix="/ai", tags=["ai"])

# 探活用的极短提示。带上 128 token 上限，避免推理类模型把预算耗在思考上返回空内容。
PROBE_PROMPT = "直接回复两个字：可用。不要解释，不要输出思考过程。"
PROBE_MAX_TOKENS = 128
PROBE_PREVIEW_LENGTH = 200


def _catalog_item(provider) -> AiProviderCatalogItem:
    return AiProviderCatalogItem(
        id=provider.id,
        name=provider.name,
        protocol=provider.protocol,
        description=provider.description,
        default_base_url=provider.default_base_url,
        requires_api_key=provider.requires_api_key,
        supports_model_discovery=True,
        capabilities=list(provider.capabilities),
        documentation_url=provider.documentation_url,
    )


@router.get("/providers", response_model=list[AiProviderCatalogItem])
def providers(_: Annotated[UserProfile, Depends(require_demo_user)]) -> list[AiProviderCatalogItem]:
    return [_catalog_item(provider) for provider in PROVIDERS]


@router.get("/configurations", response_model=AiConfigurationListResponse)
def configurations(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AiConfigurationListResponse:
    return AiConfigurationListResponse(
        items=list_configurations(db, user.organization_id), is_demo=True
    )


@router.post("/configurations", response_model=dict, status_code=status.HTTP_201_CREATED)
def create(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    payload: AiConfigurationCreate,
) -> dict:
    try:
        return create_configuration(db, user.organization_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.patch("/configurations/{configuration_id}", response_model=dict)
def update(
    configuration_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    payload: AiConfigurationPatch,
) -> dict:
    try:
        return patch_configuration(db, user.organization_id, configuration_id, payload)
    except ValueError as exc:
        code = (
            status.HTTP_404_NOT_FOUND
            if str(exc) == "AI 配置不存在"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("/configurations/{configuration_id}/test", response_model=AiConnectionTestResponse)
async def test(
    configuration_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AiConnectionTestResponse:
    try:
        row = get_configuration(db, user.organization_id, configuration_id)
        provider = get_provider(row.provider_id)
        models = await discover_models(provider, row.base_url, api_key_for(row))
        if not models:
            raise ValueError("厂商连接成功，但没有返回可用模型；请检查权限或手动确认 Base URL")
        save_models(db, row, models)
        row.status = "connected"
        row.last_error = None
        from datetime import datetime

        row.last_tested_at = datetime.now(UTC)
        row.updated_at = row.last_tested_at
        db.commit()
        db.refresh(row)
        return AiConnectionTestResponse(
            status="connected",
            message=f"连接成功，已发现 {len(models)} 个模型",
            configuration=serialize_configuration(db, row),
            models=serialize_configuration(db, row)["models"],
        )
    except ValueError as exc:
        if "row" in locals():
            row.status = "error"
            row.last_error = str(exc)[:500]
            from datetime import datetime

            row.last_tested_at = datetime.now(UTC)
            row.updated_at = row.last_tested_at
            db.commit()
        code = (
            status.HTTP_404_NOT_FOUND
            if str(exc) == "AI 配置不存在"
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except Exception:
        if "row" in locals():
            row.status = "error"
            row.last_error = "连接失败，请检查 Base URL、API Key 和网络访问"
            from datetime import datetime

            row.last_tested_at = datetime.now(UTC)
            row.updated_at = row.last_tested_at
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="连接失败，请检查 Base URL、API Key 和网络访问",
        ) from None


@router.post(
    "/configurations/{configuration_id}/discover-models", response_model=AiConnectionTestResponse
)
async def discover(
    configuration_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AiConnectionTestResponse:
    return await test(configuration_id, user, db)


async def _probe_generate(
    provider, base_url: str, api_key: str | None, model_id: str, attempts: int = 2
) -> str:
    """Send the probe request, retrying once on transport-level flakiness."""
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return await generate_text(
                provider,
                base_url,
                api_key,
                model_id,
                PROBE_PROMPT,
                "copy",
                max_tokens=PROBE_MAX_TOKENS,
            )
        except AiGenerationError:
            raise
        except Exception as exc:  # noqa: BLE001 - 连接被重置等网络抖动，重试一次
            last_error = exc
    raise last_error if last_error else AiGenerationError("模型调用失败")


@router.post("/configurations/{configuration_id}/probe", response_model=AiModelProbeResponse)
async def probe(
    configuration_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    model_id: Annotated[str | None, Body(embed=True)] = None,
) -> AiModelProbeResponse:
    """Send one minimal real request to verify the model actually works."""
    try:
        row = get_configuration(db, user.organization_id, configuration_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    provider = get_provider(row.provider_id)
    target_model = model_id or row.selected_model
    if not target_model:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请先选择要验证的模型"
        )
    if provider.id == "mock":
        return AiModelProbeResponse(
            status="skipped",
            model_id=target_model,
            message="演示模型不会发起真实调用，无需验证",
            is_demo=True,
        )

    started = perf_counter()
    try:
        content = await _probe_generate(provider, row.base_url, api_key_for(row), target_model)
    except AiGenerationError as exc:
        message = str(exc)
        # 模型目录不校验 Key，只有真实调用才会暴露 401/403；429 多见于免费模型按天限额。
        if "401" in message or "403" in message:
            message = f"{message}；请确认 API Key 完整有效，且该账号有此模型的访问权限"
        elif "429" in message:
            message = f"{message}；已触发限流，请稍后重试或改用其他免费模型"
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"模型调用失败：{exc.__class__.__name__}",
        ) from exc

    latency_ms = int((perf_counter() - started) * 1000)
    return AiModelProbeResponse(
        status="ok",
        model_id=target_model,
        message=f"模型可用，已发起一次真实调用（{latency_ms} ms）",
        preview=content[:PROBE_PREVIEW_LENGTH],
        latency_ms=latency_ms,
        is_demo=row.is_demo,
    )


@router.delete("/configurations/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    configuration_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    from sqlalchemy import delete as sql_delete

    from app.db.models import AiDiscoveredModelModel

    try:
        row = get_configuration(db, user.organization_id, configuration_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.execute(
        sql_delete(AiDiscoveredModelModel).where(AiDiscoveredModelModel.configuration_id == row.id)
    )
    db.delete(row)
    db.commit()
