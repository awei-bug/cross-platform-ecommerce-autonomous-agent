from datetime import datetime
from typing import Any

from pydantic import BaseModel


class HealthComponentScore(BaseModel):
    key: str
    label: str
    score: float
    weight: float
    detail: str


class ShopHealth(BaseModel):
    score: float
    algorithm_version: str
    components: list[HealthComponentScore]


class DiagnosisEvidence(BaseModel):
    metric: str
    value: Any
    threshold: str
    source: str


class DiagnosticIssue(BaseModel):
    kind: str
    severity: str
    shop_id: str
    shop_name: str
    product_id: str | None = None
    product_title: str | None = None
    title: str
    detail: str
    evidence: list[DiagnosisEvidence]
    confidence: str
    recommendation: str
    risk_level: str
    estimated_loss: float
    loss_note: str
    urgency: int
    priority: float


class ShopComparisonRow(BaseModel):
    shop_id: str
    shop_name: str
    platform_label: str
    health_score: float
    product_count: int
    critical_issues: int
    warning_issues: int
    revenue_7d: float
    data_source: str


class MetricDefinition(BaseModel):
    key: str
    label: str
    definition: str
    unit: str


class DiagnosticReportListItem(BaseModel):
    id: str
    shop_id: str
    title: str
    source: str
    model_id: str | None = None
    is_demo: bool = True
    created_at: datetime


class DiagnosticReport(BaseModel):
    id: str
    shop_id: str
    title: str
    source: str
    model_id: str | None = None
    content: str
    snapshot: dict[str, Any]
    is_demo: bool = True
    created_at: datetime


class DiagnosticExportJob(BaseModel):
    id: str
    report_id: str
    format: str
    file_name: str
    file_size: int
    status: str
    is_demo: bool = True
    created_at: datetime


class DiagnosticOverview(BaseModel):
    shop_id: str
    generated_at: datetime
    data_source: str
    is_demo: bool = True
    health: ShopHealth
    issues: list[DiagnosticIssue]
    comparison: list[ShopComparisonRow]
    metric_definitions: list[MetricDefinition]
