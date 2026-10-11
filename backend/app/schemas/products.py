from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import Pagination, Platform


class ProductStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    DRAFT = "draft"


class ProductRisk(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    NORMAL = "normal"


class BatchAction(StrEnum):
    PUBLISH = "publish"
    UNPUBLISH = "unpublish"
    UPDATE_PRICE = "update_price"
    SYNC = "sync"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class ProductListItem(BaseModel):
    id: str
    sku: str
    title: str
    platform: Platform
    platform_label: str
    shop_id: str
    shop_name: str
    status: ProductStatus
    risk: ProductRisk
    risk_labels: list[str]
    price: float
    cost: float
    stock: int
    sales_7d: int
    revenue_7d: float
    conversion_rate: float
    updated_at: datetime


class ProductSummary(BaseModel):
    total: int
    critical: int
    warning: int
    offline: int
    low_stock: int


class ProductListResponse(BaseModel):
    items: list[ProductListItem]
    pagination: Pagination
    summary: ProductSummary
    data_updated_at: datetime
    is_demo: bool = True


class ProductSpec(BaseModel):
    label: str
    value: str


class CompetitorSnapshot(BaseModel):
    name: str
    price: float
    sales_7d: int
    difference: str


class AiSuggestion(BaseModel):
    title: str
    detail: str
    impact: str
    action: str


class ProductDetail(ProductListItem):
    category: str
    barcode: str
    specs: list[ProductSpec]
    competitors: list[CompetitorSnapshot]
    ai_suggestions: list[AiSuggestion]
    capability_note: str
    is_demo: bool = True


class BatchActionRequest(BaseModel):
    action: BatchAction
    product_ids: list[str] = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=8, max_length=120)


class BatchItemResult(BaseModel):
    product_id: str
    sku: str
    success: bool
    message: str


class BatchJob(BaseModel):
    id: str
    action: BatchAction
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    total: int
    succeeded: int
    failed: int
    created_at: datetime
    updated_at: datetime
    results: list[BatchItemResult] = Field(default_factory=list)
    is_demo: bool = True
