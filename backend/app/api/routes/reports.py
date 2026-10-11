from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.security import require_demo_user
from app.schemas.reports import (
    ReportExportJob,
    ReportExportRequest,
    ReportNote,
    ReportNoteRequest,
    ReportOverview,
    ReportTemplateType,
)
from app.services.report_repository import create_export, create_note, get_report_overview

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(require_demo_user)])


@router.get("", response_model=ReportOverview)
def reports(
    shop_id: Annotated[str, Query()] = "shop-all",
    template_id: Annotated[ReportTemplateType, Query()] = ReportTemplateType.WEEKLY,
    metrics: Annotated[str, Query(max_length=500)] = "",
) -> ReportOverview:
    return get_report_overview(shop_id=shop_id, template_id=template_id, metrics=metrics)


@router.post("/exports", response_model=ReportExportJob)
def report_export(request: ReportExportRequest) -> ReportExportJob:
    return create_export(request)


@router.post("/notes", response_model=ReportNote)
def report_note(request: ReportNoteRequest) -> ReportNote:
    return create_note(request)
