from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import CapabilityMode, Platform, Severity


class Organization(BaseModel):
    id: str
    name: str


class Shop(BaseModel):
    id: str
    name: str
    platform: Platform
    platform_label: str
    status: str
    last_synced_at: datetime
    data_source: str = "seeded"


class WorkspaceContext(BaseModel):
    organization_id: str
    shop_id: str
    platform: Platform
    time_range: str = "today"


class WorkspaceSummary(BaseModel):
    today_sales: int
    paid_orders: int
    active_alerts: int
    pending_tasks: int
    updated_at: datetime


class WorkspaceBootstrap(BaseModel):
    organization: Organization
    shops: list[Shop]
    context: WorkspaceContext
    summary: WorkspaceSummary


class PlatformCapability(BaseModel):
    key: str
    label: str
    mode: CapabilityMode
    reason: str | None = None


class AlertItem(BaseModel):
    id: str
    title: str
    description: str
    severity: Severity
    shop_id: str
    shop_name: str
    created_at: datetime
    is_read: bool = False


class AlertReadStateUpdate(BaseModel):
    is_read: bool = True


class AlertReadAllResult(BaseModel):
    changed: int


class SearchResult(BaseModel):
    id: str
    type: str
    title: str
    subtitle: str
    route: str
