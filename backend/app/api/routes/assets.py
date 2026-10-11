from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_demo_user
from app.db.session import get_db
from app.schemas.ai import (
    AssetCreate,
    AssetListResponse,
    AssetResponse,
    GenerationJobCreate,
    GenerationJobResponse,
)
from app.schemas.auth import UserProfile
from app.services.ai_provider_registry import get_provider
from app.services.ai_repository import api_key_for, get_configuration
from app.services.asset_repository import (
    confirm_asset_version,
    create_asset,
    create_generation_job,
    create_uploaded_asset,
    get_asset_version_for_preview,
    get_job,
    list_assets,
    read_asset_preview,
    serialize_job,
)
from app.services.asset_storage import AssetStorageError
from app.workers.tasks import process_generation_job

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=AssetListResponse)
def assets(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    asset_type: str | None = Query(default=None),
) -> AssetListResponse:
    return AssetListResponse(**list_assets(db, user.organization_id, asset_type))


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    payload: AssetCreate,
) -> AssetResponse:
    return AssetResponse(**create_asset(db, user.organization_id, payload))


@router.post("/uploads", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def upload(
    request: Request,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    title: str | None = Query(default=None),
    asset_type: str | None = Query(default=None),
    product_id: str | None = Query(default=None),
    tags: str | None = Query(default=None),
) -> AssetResponse:
    """Upload raw bytes into the configured local or MinIO store.

    The endpoint intentionally accepts the request body directly, so the backend does
    not need a multipart parser and clients can upload browser File/Blob streams.
    """
    content_type = request.headers.get("content-type", "application/octet-stream").split(";", 1)[0]
    max_bytes = get_settings().asset_upload_max_bytes
    content = await request.body()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="素材文件不能超过 25 MB"
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="素材文件不能为空"
        )

    inferred_type = (
        asset_type
        or ("image" if content_type.startswith("image/") else None)
        or ("video" if content_type.startswith("video/") else None)
        or ("copy" if content_type.startswith("text/") else None)
    )
    if inferred_type not in {"copy", "image", "video", "video_script", "template"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不支持的素材类型"
        )
    filename = unquote(request.headers.get("x-filename", "asset"))
    try:
        result = create_uploaded_asset(
            db,
            user.organization_id,
            title=(title or filename or "未命名素材").strip()[:200],
            asset_type=inferred_type,
            content=content,
            content_type=content_type,
            filename=filename,
            product_id=product_id,
            tags=[item.strip() for item in (tags or "").split(",") if item.strip()],
        )
    except AssetStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return AssetResponse(**result)

@router.get("/versions/{version_id}/preview")
def preview(
    version_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        version = get_asset_version_for_preview(db, user.organization_id, version_id)
        content, content_type = read_asset_preview(db, user.organization_id, version_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AssetStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Asset-Object-Key": version.object_key or "",
        },
    )


@router.post("/{asset_id}/versions/{version_id}/confirm", response_model=AssetResponse)
def confirm_version(
    asset_id: str,
    version_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AssetResponse:
    try:
        return AssetResponse(
            **confirm_asset_version(db, user.organization_id, asset_id, version_id, user.name)
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobResponse)
def generation_job(
    job_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> GenerationJobResponse:
    try:
        return GenerationJobResponse(**serialize_job(get_job(db, user.organization_id, job_id)))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/generation-jobs", response_model=GenerationJobResponse, status_code=status.HTTP_202_ACCEPTED
)
def generate(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    payload: GenerationJobCreate,
) -> GenerationJobResponse:
    model_id = payload.model_id
    if payload.configuration_id:
        try:
            configuration = get_configuration(db, user.organization_id, payload.configuration_id)
            provider = get_provider(configuration.provider_id)
            if not configuration.is_enabled:
                raise ValueError("该 AI 配置已停用")
            if not model_id:
                model_id = configuration.selected_model
            if not model_id:
                raise ValueError("请先在 AI 配置中选择默认模型")
            if provider.requires_api_key and not api_key_for(configuration):
                raise ValueError("该 AI 配置未保存 API Key")
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
    if not model_id:
        model_id = "demo-copy-v1" if payload.asset_type.value == "copy" else "demo-visual-v1"
    job = create_generation_job(db, user.organization_id, payload, model_id)
    task = process_generation_job.delay(job["id"])
    if task and not task.id:
        pass
    return GenerationJobResponse(**job)


