from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentStepKind(StrEnum):
    DATA_COLLECT = "data_collect"
    COMPETITOR_SCAN = "competitor_scan"
    DIAGNOSIS = "diagnosis"
    RECOMMENDATION = "recommendation"
    SELF_CHECK = "self_check"
    SUPPLEMENT_DATA = "supplement_data"
    SUPPLEMENT_COMPETITOR = "supplement_competitor"
    REDIAGNOSIS = "rediagnosis"


class AgentRunStatus(StrEnum):
    PLANNING = "planning"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AgentStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class DiagnosisStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DiagnosisConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DiagnosisRiskLevel(StrEnum):
    HIGH = "high"
    LOW = "low"


class AgentPlanStep(BaseModel):
    kind: AgentStepKind
    title: str
    wave: int
    depends_on: list[AgentStepKind] = Field(default_factory=list)


class AgentStep(BaseModel):
    id: str
    run_id: str
    sequence: int
    wave: int
    kind: AgentStepKind
    title: str
    status: AgentStepStatus
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    duration_ms: int = 0
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AgentRunSummary(BaseModel):
    steps_total: int = 0
    steps_succeeded: int = 0
    diagnoses_total: int = 0
    discarded_conclusions: int = 0
    supplement_rounds: int = 0
    high_risk_pending: int = 0
    reflection_notes: list[str] = Field(default_factory=list)


class DiagnosisEvidence(BaseModel):
    metric: str
    value: Any
    threshold: str
    source: str


class Diagnosis(BaseModel):
    id: str
    run_id: str
    shop_id: str
    shop_name: str
    product_id: str | None = None
    kind: str
    severity: str
    title: str
    detail: str
    evidence: list[DiagnosisEvidence]
    confidence: DiagnosisConfidence
    recommendation: str
    risk_level: DiagnosisRiskLevel
    status: DiagnosisStatus
    decided_by: str | None = None
    decision_note: str | None = None
    decided_at: datetime | None = None
    is_demo: bool = True
    created_at: datetime


class AgentRun(BaseModel):
    id: str
    goal: str
    shop_ids: list[str]
    status: AgentRunStatus
    plan: list[AgentPlanStep]
    summary: AgentRunSummary
    steps: list[AgentStep]
    diagnoses: list[Diagnosis]
    error_message: str | None = None
    is_demo: bool = True
    created_at: datetime
    completed_at: datetime | None = None


class AgentRunListItem(BaseModel):
    id: str
    goal: str
    status: AgentRunStatus
    shop_ids: list[str]
    diagnoses_total: int = 0
    high_risk_pending: int = 0
    created_at: datetime
    completed_at: datetime | None = None
    is_demo: bool = True


class AgentRunCreate(BaseModel):
    goal: str = Field(min_length=4, max_length=500)
    shop_ids: list[str] = Field(default_factory=list, max_length=20)


class DiagnosisDecision(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=500)


class CompetitorItem(BaseModel):
    id: str
    category: str
    title: str
    platform_label: str
    price: float
    sales_7d: int
    conversion_rate: float
    selling_points: list[str]
    review_pain_points: list[str]
    source: str
    similarity: float | None = None
    is_demo: bool = True
    created_at: datetime
    updated_at: datetime


class CompetitorCreate(BaseModel):
    category: str = Field(default="美容护肤 / 面部护理", max_length=120)
    title: str = Field(min_length=2, max_length=200)
    price: float = Field(ge=0, le=1_000_000)
    selling_points: list[str] = Field(default_factory=list, max_length=10)
    review_pain_points: list[str] = Field(default_factory=list, max_length=10)
    platform_label: str = Field(default="人工录入", max_length=32)


class CompetitorImportRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=50)
    category: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=10, ge=1, le=40)


class CompetitorImportResult(BaseModel):
    keyword: str
    source: str
    created: int
    updated: int
    note: str
    items: list[CompetitorItem]
