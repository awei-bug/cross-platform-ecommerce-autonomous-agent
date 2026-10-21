from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import require_demo_user
from app.db.session import get_db
from app.schemas.auth import UserProfile
from app.schemas.diagnostics import (
    DiagnosticExportJob,
    DiagnosticOverview,
    DiagnosticReport,
    DiagnosticReportListItem,
)
from app.services.asset_storage import AssetStorageError, get_bytes
from app.services.diagnostic_export_service import create_export, get_export
from app.services.diagnostic_report_service import (
    generate_report,
    get_report,
    list_reports,
)
from app.services.diagnostics_service import get_overview

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/overview", response_model=DiagnosticOverview)
def diagnostic_overview(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    shop_id: Annotated[str, Query()] = "shop-all",
) -> DiagnosticOverview:
    """诊断总览：健康分、问题清单（损失 x 紧迫度 x 置信度排序）与店铺对比。"""
    return DiagnosticOverview(**get_overview(db, shop_id))


@router.post("/reports", response_model=DiagnosticReport, status_code=201)
def create_diagnostic_report(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    shop_id: Annotated[str, Query()] = "shop-all",
) -> DiagnosticReport:
    """生成诊断报告。配置了可用模型且开关打开时走真实模型，否则规则模板。"""
    return DiagnosticReport(
        **generate_report(db, user.organization_id, shop_id)
    )


@router.get("/reports", response_model=list[DiagnosticReportListItem])
def list_diagnostic_reports(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DiagnosticReportListItem]:
    return [DiagnosticReportListItem(**item) for item in list_reports(db, user.organization_id)]


@router.get("/reports/{report_id}", response_model=DiagnosticReport)
def get_diagnostic_report(
    report_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DiagnosticReport:
    report = get_report(db, user.organization_id, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="诊断报告不存在")
    return DiagnosticReport(**report)


@router.post(
    "/reports/{report_id}/exports", response_model=DiagnosticExportJob, status_code=201
)
def create_diagnostic_export(
    report_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    export_format: Annotated[str, Query(alias="format")] = "pdf",
) -> DiagnosticExportJob:
    """后端生成真实 PDF / Excel 文件，元数据落库。"""
    try:
        job = create_export(db, user.organization_id, report_id, export_format)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AssetStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return DiagnosticExportJob(**job)


@router.get("/exports/{export_id}/download")
def download_diagnostic_export(
    export_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """下载导出文件。必须登录，对象键不回显给前端。"""
    export = get_export(db, user.organization_id, export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="导出文件不存在")
    try:
        content, _ = get_bytes(export.object_key)
    except AssetStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    media_type = (
        "application/pdf"
        if export.format == "pdf"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    # RFC 5987：中文名走 filename*（UTF-8 百分号编码），fallback 用纯 ASCII，
    # 避免 HTTP 头无法编码非 ASCII 字符。
    encoded_name = quote(export.file_name)
    ascii_fallback = f"diagnostic-report-{export.id}.{export.format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_fallback}\"; "
                f"filename*=UTF-8''{encoded_name}"
            ),
            "Cache-Control": "private, max-age=60",
        },
    )
