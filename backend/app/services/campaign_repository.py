from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.schemas.campaigns import (
    AdAccount,
    AdCampaign,
    AdOverview,
    AdRecommendation,
    AdSummary,
    AdTrendPoint,
    BudgetAlert,
    CampaignStatus,
)
from app.schemas.common import Platform
from app.services.shop_scope import parse_shop_scope

SHANGHAI = ZoneInfo("Asia/Shanghai")
DATA_UPDATED_AT = datetime(2026, 9, 12, 23, 50, tzinfo=SHANGHAI)

CAMPAIGNS = [
    AdCampaign(
        id="campaign-tb-001",
        account_id="ad-account-tb-001",
        account_name="淘宝直通车 · 柔肤旗舰店",
        platform=Platform.TAOBAO,
        platform_label="淘宝",
        shop_id="shop-taobao-001",
        shop_name="柔肤旗舰店",
        name="秋季面霜核心词",
        status=CampaignStatus.RUNNING,
        impressions=182400,
        clicks=6840,
        spend=12680,
        ctr=3.75,
        conversion_rate=6.82,
        conversions=467,
        revenue=49860,
        roi=3.93,
        budget=15000,
        budget_used=12680,
        anomaly=False,
        updated_at=DATA_UPDATED_AT,
    ),
    AdCampaign(
        id="campaign-tb-002",
        account_id="ad-account-tb-001",
        account_name="淘宝直通车 · 柔肤旗舰店",
        platform=Platform.TAOBAO,
        platform_label="淘宝",
        shop_id="shop-taobao-001",
        shop_name="柔肤旗舰店",
        name="敏感肌人群扩量",
        status=CampaignStatus.RUNNING,
        impressions=243100,
        clicks=4980,
        spend=9850,
        ctr=2.05,
        conversion_rate=2.11,
        conversions=105,
        revenue=21400,
        roi=2.17,
        budget=10000,
        budget_used=9850,
        anomaly=True,
        updated_at=DATA_UPDATED_AT,
    ),
    AdCampaign(
        id="campaign-dy-001",
        account_id="ad-account-dy-001",
        account_name="抖店千川 · 旗舰店",
        platform=Platform.DOUYIN,
        platform_label="抖店",
        shop_id="shop-douyin-001",
        shop_name="柔肤抖店旗舰店",
        name="短视频引流计划",
        status=CampaignStatus.RUNNING,
        impressions=318500,
        clicks=10420,
        spend=15680,
        ctr=3.27,
        conversion_rate=7.46,
        conversions=777,
        revenue=68400,
        roi=4.36,
        budget=22000,
        budget_used=15680,
        anomaly=False,
        updated_at=DATA_UPDATED_AT,
    ),
    AdCampaign(
        id="campaign-dy-002",
        account_id="ad-account-dy-001",
        account_name="抖店千川 · 旗舰店",
        platform=Platform.DOUYIN,
        platform_label="抖店",
        shop_id="shop-douyin-001",
        shop_name="柔肤抖店旗舰店",
        name="直播间加热 · 9月",
        status=CampaignStatus.PAUSED,
        impressions=156200,
        clicks=3910,
        spend=7200,
        ctr=2.50,
        conversion_rate=1.74,
        conversions=68,
        revenue=11900,
        roi=1.65,
        budget=12000,
        budget_used=7200,
        anomaly=True,
        updated_at=DATA_UPDATED_AT,
    ),
    AdCampaign(
        id="campaign-pdd-001",
        account_id="ad-account-pdd-001",
        account_name="拼多多推广 · 专营店",
        platform=Platform.PINDUODUO,
        platform_label="拼多多",
        shop_id="shop-pdd-001",
        shop_name="柔肤拼多多专营店",
        name="洁面套装搜索推广",
        status=CampaignStatus.RUNNING,
        impressions=205600,
        clicks=7320,
        spend=8650,
        ctr=3.56,
        conversion_rate=5.45,
        conversions=399,
        revenue=33280,
        roi=3.85,
        budget=10000,
        budget_used=8650,
        anomaly=False,
        updated_at=DATA_UPDATED_AT,
    ),
    AdCampaign(
        id="campaign-pdd-002",
        account_id="ad-account-pdd-001",
        account_name="拼多多推广 · 专营店",
        platform=Platform.PINDUODUO,
        platform_label="拼多多",
        shop_id="shop-pdd-001",
        shop_name="柔肤拼多多专营店",
        name="大促蓄水人群",
        status=CampaignStatus.REVIEW,
        impressions=98400,
        clicks=2180,
        spend=3900,
        ctr=2.22,
        conversion_rate=3.12,
        conversions=68,
        revenue=12500,
        roi=3.21,
        budget=8000,
        budget_used=3900,
        anomaly=False,
        updated_at=DATA_UPDATED_AT,
    ),
]


def _scoped_campaigns(
    shop_id: str, platform: Platform, account_id: str, status: CampaignStatus | None, q: str
) -> list[AdCampaign]:
    shop_scope = parse_shop_scope(shop_id)
    keyword = q.strip().lower()
    return [
        item
        for item in CAMPAIGNS
        if (shop_scope is None or item.shop_id in shop_scope)
        and (platform == Platform.ALL or item.platform == platform)
        and (not account_id or item.account_id == account_id)
        and (status is None or item.status == status)
        and (not keyword or keyword in item.name.lower() or keyword in item.account_name.lower())
    ]


def _accounts(campaigns: list[AdCampaign]) -> list[AdAccount]:
    by_account: dict[str, list[AdCampaign]] = {}
    for campaign in campaigns:
        by_account.setdefault(campaign.account_id, []).append(campaign)
    return [
        AdAccount(
            id=account_id,
            name=items[0].account_name,
            platform=items[0].platform,
            platform_label=items[0].platform_label,
            shop_id=items[0].shop_id,
            shop_name=items[0].shop_name,
            status="投放中"
            if any(item.status == CampaignStatus.RUNNING for item in items)
            else "已暂停",
            spend_7d=round(sum(item.spend for item in items), 2),
            budget_7d=round(sum(item.budget for item in items), 2),
            roi=round(sum(item.revenue for item in items) / sum(item.spend for item in items), 2),
        )
        for account_id, items in by_account.items()
    ]


def _trend(campaigns: list[AdCampaign]) -> list[AdTrendPoint]:
    factors = [0.72, 0.84, 0.81, 0.93, 0.97, 1.06, 1.0]
    dates = [(DATA_UPDATED_AT - timedelta(days=6 - index)).strftime("%m-%d") for index in range(7)]
    spend = sum(item.spend for item in campaigns)
    revenue = sum(item.revenue for item in campaigns)
    conversions = sum(item.conversions for item in campaigns)
    return [
        AdTrendPoint(
            date=date,
            spend=round(spend / 7 * factor, 2),
            revenue=round(revenue / 7 * factor, 2),
            conversions=round(conversions / 7 * factor),
        )
        for date, factor in zip(dates, factors, strict=True)
    ]


def get_ad_overview(
    shop_id: str,
    platform: Platform = Platform.ALL,
    account_id: str = "",
    status: CampaignStatus | None = None,
    q: str = "",
) -> AdOverview:
    campaigns = _scoped_campaigns(shop_id, platform, account_id, status, q)
    spend = sum(item.spend for item in campaigns)
    revenue = sum(item.revenue for item in campaigns)
    budget_alerts = [
        BudgetAlert(
            id=f"budget-{account.id}",
            account_id=account.id,
            account_name=account.name,
            shop_name=account.shop_name,
            spend=account.spend_7d,
            budget=account.budget_7d,
            usage_percent=round(account.spend_7d / account.budget_7d * 100, 1),
            message=(
                f"{account.name} 已消耗 {account.spend_7d / account.budget_7d:.0%}，接近预算阈值。"
            ),
        )
        for account in _accounts(campaigns)
        if account.budget_7d and account.spend_7d / account.budget_7d >= 0.8
    ]
    recommendations = [
        AdRecommendation(
            id=f"recommendation-{item.id}",
            campaign_id=item.id,
            level="critical" if item.roi < 2 else "info",
            title="建议降低出价并复核素材" if item.roi < 2 else "建议追加预算",
            detail=(
                f"{item.name} 消耗 ¥{item.spend:,.0f}，ROI 仅 {item.roi:.2f}，已连续低于账户均值。"
                if item.roi < 2
                else (
                    f"{item.name} ROI {item.roi:.2f}，"
                    f"转化率 {item.conversion_rate:.2f}%，具备扩量空间。"
                )
            ),
            evidence=[
                f"花费 ¥{item.spend:,.0f}",
                f"ROI {item.roi:.2f}",
                f"转化 {item.conversions} 单",
            ],
            action="查看计划" if item.roi < 2 else "调整预算",
        )
        for item in campaigns
        if item.anomaly or item.roi >= 3.8
    ][:4]
    return AdOverview(
        accounts=_accounts(campaigns),
        campaigns=campaigns,
        trend=_trend(campaigns),
        budget_alerts=budget_alerts,
        recommendations=recommendations,
        summary=AdSummary(
            spend=round(spend, 2),
            revenue=round(revenue, 2),
            roi=round(revenue / spend, 2) if spend else 0,
            impressions=sum(item.impressions for item in campaigns),
            clicks=sum(item.clicks for item in campaigns),
            conversions=sum(item.conversions for item in campaigns),
            active_campaigns=sum(item.status == CampaignStatus.RUNNING for item in campaigns),
            anomaly_campaigns=sum(item.anomaly for item in campaigns),
        ),
        data_updated_at=DATA_UPDATED_AT,
    )
