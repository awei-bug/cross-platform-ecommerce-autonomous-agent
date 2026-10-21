from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Platform(StrEnum):
    ALL = "all"
    TAOBAO = "taobao"
    DOUYIN = "douyin"
    DOUYIN_CONTENT = "douyin_content"
    PINDUODUO = "pinduoduo"


class CapabilityMode(StrEnum):
    DIRECT = "direct"
    ASYNC = "async"
    REDIRECT = "redirect"
    UNSUPPORTED = "unsupported"


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ApiMeta(BaseModel):
    request_id: str = "demo-request"
    data_updated_at: datetime
    is_demo: bool = True


class ApiResponse(BaseModel):
    data: object
    meta: ApiMeta


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str


class ReadinessResponse(BaseModel):
    status: str = "ready"
    database: str
    task_execution: str


class Pagination(BaseModel):
    page: int = Field(ge=1, default=1)
    page_size: int = Field(ge=1, le=200, default=20)
    total: int = Field(ge=0, default=0)
