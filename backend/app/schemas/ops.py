from datetime import datetime

from pydantic import BaseModel, Field


class OpsTask(BaseModel):
    kind: str
    id: str
    title: str
    status: str
    progress: int = 0
    attempts: int = 1
    max_attempts: int = 3
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    updated_at: datetime
    completed_at: datetime | None = None
    is_demo: bool = True


class OpsTotals(BaseModel):
    total: int = 0
    succeeded: int = 0
    running: int = 0
    failed: int = 0
    dead_letter: int = 0
    dismissed: int = 0


class OpsRecentFailure(BaseModel):
    kind: str
    id: str
    title: str
    error: str | None = None
    attempts: int = 1
    updated_at: datetime


class OpsMetrics(BaseModel):
    generated_at: datetime
    totals: OpsTotals
    failure_rate: float
    avg_duration_seconds: float
    by_kind: dict[str, dict[str, int]] = Field(default_factory=dict)
    recent_failures: list[OpsRecentFailure] = Field(default_factory=list)


class OpsSweepResult(BaseModel):
    checked_at: datetime
    timed_out: list[dict]
    dead_lettered: list[dict]
