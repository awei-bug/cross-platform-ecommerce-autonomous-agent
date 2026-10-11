from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import Platform
from app.schemas.products import ProductRisk


class DashboardMetric(BaseModel):
    key: str
    label: str
    value: float
    unit: str
    comparison: float
    comparison_label: str
    definition: str


class TrendPoint(BaseModel):
    date: str
    sales: float
    orders: int


class DashboardRiskItem(BaseModel):
    id: str
    level: ProductRisk
    title: str
    detail: str
    estimated_loss: float
    deadline: str
    route: str
    shop_name: str


class OperationTask(BaseModel):
    id: str
    title: str
    owner: str
    status: str
    progress: int
    due_at: str


class TopProduct(BaseModel):
    id: str
    sku: str
    title: str
    platform: Platform
    platform_label: str
    revenue: float
    sales: int
    trend: float


class AiBrief(BaseModel):
    headline: str
    summary: str
    evidence: list[str]
    actions: list[str]
    context_label: str


class DashboardOverview(BaseModel):
    metrics: list[DashboardMetric]
    trend: list[TrendPoint]
    risks: list[DashboardRiskItem]
    tasks: list[OperationTask]
    top_products: list[TopProduct]
    ai_brief: AiBrief
    data_updated_at: datetime
    is_demo: bool = True
