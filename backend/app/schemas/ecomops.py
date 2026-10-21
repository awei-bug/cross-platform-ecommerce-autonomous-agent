from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Workflow = Literal[
    "initialization",
    "selection",
    "listing",
    "marketing",
    "service",
    "fulfillment",
    "analytics",
]
Platform = Literal["amazon", "aliexpress", "temu", "shopee", "tiktok_shop"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class RiskRule(StrictModel):
    id: str = Field(min_length=1, max_length=64)
    dimension: Literal["prohibited", "intellectual_property", "advertising", "privacy", "customs"]
    pattern: str = Field(min_length=1, max_length=100)
    level: Literal["low", "medium", "high"]
    replacement: str = Field(default="", max_length=100)


class Policy(StrictModel):
    stock_amount_limit: float = Field(default=10000, ge=0, le=1e9)
    budget_change_limit_pct: float = Field(default=20, ge=0, le=100)
    refund_limit: float = Field(default=50, ge=0, le=1e8)
    selection_min_score: float = Field(default=65, ge=0, le=100)
    min_margin_pct: float = Field(default=15, ge=0, lt=100)
    max_attempts: int = Field(default=3, ge=1, le=10)
    rules: list[RiskRule] = Field(
        default_factory=lambda: [
            RiskRule(id="ads-001", dimension="advertising", pattern="全球第一", level="low"),
            RiskRule(id="ads-002", dimension="advertising", pattern="100% cure", level="medium"),
            RiskRule(id="ban-001", dimension="prohibited", pattern="违禁品", level="high"),
            RiskRule(
                id="ip-001", dimension="intellectual_property", pattern="疑似侵权", level="medium"
            ),
            RiskRule(id="privacy-001", dimension="privacy", pattern="泄露客户隐私", level="high"),
            RiskRule(id="customs-001", dimension="customs", pattern="规避海关", level="high"),
        ],
        max_length=200,
    )

    @model_validator(mode="after")
    def unique_rules(self):
        if len({r.id for r in self.rules}) != len(self.rules):
            raise ValueError("规则 ID 不得重复")
        return self


class ConfigurationUpdate(StrictModel):
    version: int = Field(ge=1)
    policy: Policy


class RecordInput(StrictModel):
    kind: Literal["product", "supplier", "customer", "competitor", "order", "metric", "term"]
    key: str = Field(min_length=1, max_length=120)
    data: dict = Field(default_factory=dict)
    source: str = Field(min_length=1, max_length=200)
    is_demo: bool = False


class ImportRequest(StrictModel):
    records: list[RecordInput] = Field(min_length=1, max_length=500)


class BusinessInput(StrictModel):
    use_ai: bool = False
    research_collection_id: str = Field(default="", max_length=80, pattern="^[a-zA-Z0-9_-]*$")
    sku: str = Field(default="", max_length=120)
    platform: Platform = "amazon"
    country: str = Field(default="US", min_length=2, max_length=2, pattern="^[A-Z]{2}$")
    language: Literal["en", "zh", "de", "ja", "fr", "es"] = "en"
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    exchange_rate_to_usd: float = Field(default=1, gt=0, le=1e6)
    title: str = Field(default="", max_length=200)
    content: str = Field(default="", max_length=10000)
    price: float = Field(default=0, ge=0, le=1e8)
    procurement: float = Field(default=0, ge=0, le=1e8)
    freight: float = Field(default=0, ge=0, le=1e8)
    tax: float = Field(default=0, ge=0, le=1e8)
    loss: float = Field(default=0, ge=0, le=1e8)
    commission_pct: float = Field(default=15, ge=0, lt=100)
    ad_rate_pct: float = Field(default=10, ge=0, lt=100)
    quantity: int = Field(default=100, ge=1, le=10000000)
    market_score: float = Field(default=70, ge=0, le=100)
    competition_score: float = Field(default=70, ge=0, le=100)
    supply_score: float = Field(default=70, ge=0, le=100)
    compliance_score: float = Field(default=70, ge=0, le=100)
    budget_before: float = Field(default=100, ge=0, le=1e8)
    budget_after: float = Field(default=100, ge=0, le=1e8)
    ad_spend: float = Field(default=0, ge=0, le=1e8)
    refund_amount: float = Field(default=0, ge=0, le=1e8)
    service_intent: Literal["consultation", "refund", "review", "logistics"] = "consultation"
    order_key: str = Field(default="", max_length=120)
    stock: int = Field(default=100, ge=0, le=10000000)
    safety_stock: int = Field(default=20, ge=0, le=10000000)
    daily_sales: float = Field(default=5, ge=0, le=1e7)
    lead_days: int = Field(default=14, ge=0, le=730)
    destination_address: str = Field(default="", max_length=500)
    tracking_status: Literal["unknown", "in_transit", "delayed", "lost", "damaged", "customs"] = (
        "unknown"
    )

    @model_validator(mode="after")
    def valid_rates(self):
        if self.commission_pct + self.ad_rate_pct >= 100:
            raise ValueError("佣金与广告费率之和必须小于 100%")
        if self.currency == "USD" and self.exchange_rate_to_usd != 1:
            raise ValueError("USD 本位币汇率必须为 1")
        return self


class RunCreate(StrictModel):
    workflow: Workflow
    title: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=8, max_length=120)
    priority: int = Field(default=5, ge=1, le=10)
    input: BusinessInput = Field(default_factory=BusinessInput)


class Intervention(StrictModel):
    action: Literal[
        "approve", "reject", "takeover", "resume", "cancel", "retry", "priority", "reevaluate"
    ]
    review_version: int | None = Field(default=None, ge=1)
    task_id: str | None = None
    note: str = Field(min_length=2, max_length=2000)
    priority: int = Field(default=5, ge=1, le=10)


class ScheduleCreate(StrictModel):
    workflow: Literal["selection", "analytics"]
    interval_hours: int = Field(default=24, ge=1, le=8784)
    input: BusinessInput = Field(default_factory=BusinessInput)


class ScheduleUpdate(StrictModel):
    enabled: bool
