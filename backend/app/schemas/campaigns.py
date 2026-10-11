from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from app.schemas.common import Platform


class CampaignStatus(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"
    REVIEW = "review"


class AdAccount(BaseModel):
    id: str
    name: str
    platform: Platform
    platform_label: str
    shop_id: str
    shop_name: str
    status: str
    spend_7d: float
    budget_7d: float
    roi: float


class AdCampaign(BaseModel):
    id: str
    account_id: str
    account_name: str
    platform: Platform
    platform_label: str
    shop_id: str
    shop_name: str
    name: str
    status: CampaignStatus
    impressions: int
    clicks: int
    spend: float
    ctr: float
    conversion_rate: float
    conversions: int
    revenue: float
    roi: float
    budget: float
    budget_used: float
    anomaly: bool
    updated_at: datetime


class AdTrendPoint(BaseModel):
    date: str
    spend: float
    revenue: float
    conversions: int


class BudgetAlert(BaseModel):
    id: str
    account_id: str
    account_name: str
    shop_name: str
    spend: float
    budget: float
    usage_percent: float
    message: str
    severity: str = "warning"


class AdRecommendation(BaseModel):
    id: str
    campaign_id: str
    level: str
    title: str
    detail: str
    evidence: list[str]
    action: str


class AdSummary(BaseModel):
    spend: float
    revenue: float
    roi: float
    impressions: int
    clicks: int
    conversions: int
    active_campaigns: int
    anomaly_campaigns: int


class AdOverview(BaseModel):
    accounts: list[AdAccount]
    campaigns: list[AdCampaign]
    trend: list[AdTrendPoint]
    budget_alerts: list[BudgetAlert]
    recommendations: list[AdRecommendation]
    summary: AdSummary
    data_updated_at: datetime
    is_demo: bool = True
