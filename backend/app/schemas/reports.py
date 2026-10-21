from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class ReportTemplateType(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    PRODUCT = "product"
    AD = "ad"
    AFTER_SALE = "after_sale"


class ReportFormat(StrEnum):
    EXCEL = "excel"
    PDF = "pdf"


class ReportTemplate(BaseModel):
    id: ReportTemplateType
    name: str
    description: str
    category: str
    default_metrics: list[str]


class ReportMetric(BaseModel):
    key: str
    label: str
    value: float
    display_value: str
    change: float
    direction: str


class ReportTrendPoint(BaseModel):
    date: str
    revenue: float
    orders: int
    spend: float
    refunds: float


class ReportRow(BaseModel):
    id: str
    name: str
    shop_name: str
    platform_label: str
    revenue: float
    orders: int
    spend: float
    roi: float
    refund_rate: float


class ReportExportJob(BaseModel):
    id: str
    template_id: ReportTemplateType
    template_name: str
    format: ReportFormat
    status: str
    progress: int
    file_name: str
    file_size: int = 0
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    is_demo: bool = True


class ReportNote(BaseModel):
    id: str
    template_id: ReportTemplateType
    title: str
    conclusion: str
    next_actions: str
    author: str
    created_at: datetime
    is_demo: bool = True


class ReportOverview(BaseModel):
    templates: list[ReportTemplate]
    selected_template: ReportTemplateType
    selected_metrics: list[str]
    metrics: list[ReportMetric]
    trend: list[ReportTrendPoint]
    rows: list[ReportRow]
    exports: list[ReportExportJob]
    notes: list[ReportNote]
    data_updated_at: datetime
    is_demo: bool = True


class ReportExportRequest(BaseModel):
    template_id: ReportTemplateType
    format: ReportFormat
    shop_id: str = "shop-all"
    start_date: str = ""
    end_date: str = ""
    metrics: list[str] = []


class ReportNoteRequest(BaseModel):
    template_id: ReportTemplateType
    title: str
    conclusion: str
    next_actions: str
