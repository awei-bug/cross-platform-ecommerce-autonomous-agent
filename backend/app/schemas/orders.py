from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import Pagination, Platform


class OrderStatus(StrEnum):
    PENDING_SHIPMENT = "pending_shipment"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CLOSED = "closed"


class AfterSaleStatus(StrEnum):
    NONE = "none"
    REQUESTED = "requested"
    MERCHANT_PROCESSING = "merchant_processing"
    BUYER_RETURNING = "buyer_returning"
    REFUND_PROCESSING = "refund_processing"
    RESOLVED = "resolved"


class OrderRisk(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    NORMAL = "normal"


class OrderAction(StrEnum):
    REMIND_SHIP = "remind_ship"
    APPROVE_REFUND = "approve_refund"
    REJECT_REFUND = "reject_refund"
    SEND_REPLY = "send_reply"
    MARK_FOLLOW_UP = "mark_follow_up"


class OrderActionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class OrderListItem(BaseModel):
    id: str
    order_no: str
    platform: Platform
    platform_label: str
    shop_id: str
    shop_name: str
    buyer_masked: str
    item_title: str
    sku: str
    quantity: int
    amount: float
    order_status: OrderStatus
    after_sale_status: AfterSaleStatus
    risk: OrderRisk
    risk_reasons: list[str]
    sla_deadline: datetime | None
    remaining_minutes: int | None
    estimated_loss: float
    created_at: datetime
    updated_at: datetime
    sensitive_data_masked: bool = True


class OrderSummary(BaseModel):
    total: int
    critical: int
    overdue: int
    due_within_2h: int
    pending_after_sale: int
    pending_shipment: int
    estimated_loss: float


class OrderListResponse(BaseModel):
    items: list[OrderListItem]
    pagination: Pagination
    summary: OrderSummary
    data_updated_at: datetime
    is_demo: bool = True


class OrderLine(BaseModel):
    sku: str
    title: str
    quantity: int
    unit_price: float


class OrderTimelineItem(BaseModel):
    time: datetime
    title: str
    detail: str
    state: str


class ConversationMessage(BaseModel):
    id: str
    sender: str
    sender_type: str
    content: str
    sent_at: datetime


class AiReplySuggestion(BaseModel):
    id: str
    tone: str
    content: str
    evidence: list[str]


class OrderAuditEntry(BaseModel):
    id: str
    order_id: str
    order_no: str
    action: OrderAction
    action_label: str
    actor: str
    result: str
    note: str
    created_at: datetime
    is_demo: bool = True


class OrderDetail(OrderListItem):
    buyer_phone_masked: str
    shipping_address_masked: str
    logistics_company: str | None
    tracking_no_masked: str | None
    lines: list[OrderLine]
    timeline: list[OrderTimelineItem]
    conversation: list[ConversationMessage]
    ai_replies: list[AiReplySuggestion]
    available_actions: list[OrderAction]
    audit_entries: list[OrderAuditEntry]
    capability_note: str
    is_demo: bool = True


class OrderActionRequest(BaseModel):
    action: OrderAction
    order_ids: list[str] = Field(min_length=1, max_length=50)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=8, max_length=120)


class OrderActionItemResult(BaseModel):
    order_id: str
    order_no: str
    success: bool
    message: str


class OrderActionJob(BaseModel):
    id: str
    action: OrderAction
    status: OrderActionStatus
    progress: int = Field(ge=0, le=100)
    total: int
    succeeded: int
    failed: int
    created_at: datetime
    updated_at: datetime
    results: list[OrderActionItemResult] = Field(default_factory=list)
    is_demo: bool = True
