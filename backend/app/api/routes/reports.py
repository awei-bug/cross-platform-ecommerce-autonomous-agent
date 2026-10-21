from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import require_demo_user
from app.db.session import get_db
from app.schemas.auth import UserProfile
from app.schemas.reports import (
    ReportExportJob,
    ReportExportRequest,
    ReportNote,
    ReportNoteRequest,
    ReportOverview,
    ReportTemplateType,
)
from app.services.asset_storage import AssetStorageError, get_bytes
from app.services.report_export_service import create_export, get_export
from app.services.report_repository import create_note, get_report_overview

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=ReportOverview)
def reports(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    shop_id: Annotated[str, Query()] = "shop-all",
    template_id: Annotated[ReportTemplateType, Query()] = ReportTemplateType.WEEKLY,
    metrics: Annotated[str, Query(max_length=500)] = "",
) -> ReportOverview:
    return get_report_overview(db, shop_id=shop_id, template_id=template_id, metrics=metrics)


@router.post("/exports", response_model=ReportExportJob)
def report_export(
    request: ReportExportRequest,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportExportJob:
    """生成真实 Excel / PDF 报表文件并落库导出记录。"""
    try:
        job = create_export(db, user.organization_id, request)
    except AssetStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return ReportExportJob(**job)


@router.get("/exports/{export_id}/download")
def download_report_export(
    export_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """下载报表文件。必须登录，对象键不回显给前端。"""
    record = get_export(db, user.organization_id, export_id)
    if record is None or record.object_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="导出文件不存在")
    try:
        content, _ = get_bytes(record.object_key)
    except AssetStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    media_type = (
        "application/pdf"
        if record.format == "pdf"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    encoded_name = quote(record.file_name)
    ascii_fallback = f"report-{record.id}.{record.format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded_name}"
            ),
            "Cache-Control": "private, max-age=60",
        },
    )


@router.post("/notes", response_model=ReportNote)
def report_note(
    request: ReportNoteRequest,
    user: Annotated[UserProfile, Depends(require_demo_user)],
) -> ReportNote:
    return create_note(request)
