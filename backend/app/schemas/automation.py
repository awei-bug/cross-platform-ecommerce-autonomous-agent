from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AutomationRuleType(StrEnum):
    AFTER_SALE_SLA = "after_sale_sla"
    INVENTORY_LOW = "inventory_low"
    PRODUCT_QUALITY = "product_quality"


class AutomationMode(StrEnum):
    SUGGEST = "suggest"
    APPROVAL_REQUIRED = "approval_required"
    AUTO = "auto"


class AutomationRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AutomationTaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class AutomationRule(BaseModel):
    id: str
    name: str
    rule_type: AutomationRuleType
    description: str
    mode: AutomationMode
    config: dict[str, Any]
    is_enabled: bool
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_demo: bool = True


class AutomationMatch(BaseModel):
    task_id: str | None = None
    entity_id: str
    entity_type: str
    reference: str
    title: str
    severity: str
    reason: str
    suggested_action: str


class AutomationTask(BaseModel):
    id: str
    run_id: str
    rule_id: str
    entity_id: str
    entity_type: str
    reference: str
    title: str
    severity: str
    reason: str
    suggested_action: str
    status: AutomationTaskStatus
    assignee: str | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    is_demo: bool = True


class AutomationRun(BaseModel):
    id: str
    rule_id: str
    rule_name: str
    status: AutomationRunStatus
    matched_count: int
    task_count: int
    results: list[AutomationMatch]
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None
    is_demo: bool = True


class AutomationOverview(BaseModel):
    rules: list[AutomationRule]
    runs: list[AutomationRun]
    tasks: list[AutomationTask]
    data_updated_at: datetime
    is_demo: bool = True


class AutomationRuleUpdate(BaseModel):
    is_enabled: bool | None = None
    mode: AutomationMode | None = None
    config: dict[str, Any] | None = None


class AutomationTaskUpdate(BaseModel):
    status: AutomationTaskStatus | None = None
    assignee: str | None = Field(default=None, max_length=80)


class AutomationRunRequest(BaseModel):
    confirm: bool = Field(default=False, description="确认扫描当前规则范围")
