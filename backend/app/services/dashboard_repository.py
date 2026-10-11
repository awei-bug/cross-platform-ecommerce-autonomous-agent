from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ProductModel
from app.schemas.dashboard import (
    AiBrief,
    DashboardMetric,
    DashboardOverview,
    DashboardRiskItem,
    OperationTask,
    TopProduct,
    TrendPoint,
)
from app.schemas.products import ProductRisk
from app.services.shop_scope import parse_shop_scope

DEFAULT_ORG = "org-demo-001"
SHANGHAI = ZoneInfo("Asia/Shanghai")
DASHBOARD_UPDATED_AT = datetime(2026, 9, 12, 9, 40, tzinfo=SHANGHAI)


def get_dashboard_overview(db: Session, shop_id: str) -> DashboardOverview:
    shop_scope = parse_shop_scope(shop_id)
    stmt = select(ProductModel).where(ProductModel.organization_id == DEFAULT_ORG)
    if shop_scope is not None:
        stmt = stmt.where(ProductModel.shop_id.in_(shop_scope))
    scoped = list(db.scalars(stmt))

    total_revenue = sum(item.revenue_7d for item in scoped)
    total_sales = sum(item.sales_7d for item in scoped)
    online = sum(item.status == "online" for item in scoped)
    critical = sum(item.risk == ProductRisk.CRITICAL.value for item in scoped)
    daily_sales = total_revenue / 7 if total_revenue else 0
    order_value = total_revenue / total_sales if total_sales else 0
    context_label = (
        "全部店铺"
        if shop_scope is None
        else (
            scoped[0].shop_name
            if len(shop_scope) == 1 and scoped
            else f"{len(shop_scope)} 个店铺"
        )
    )

    factors = [0.86, 0.92, 0.89, 1.04, 0.97, 1.08, 1.14]
    dates = ["09-06", "09-07", "09-08", "09-09", "09-10", "09-11", "09-12"]
    trend = [
        TrendPoint(
            date=date,
            sales=round(daily_sales * factor, 2),
            orders=round(total_sales / 7 * factor),
        )
        for date, factor in zip(dates, factors, strict=True)
    ]
    top = sorted(scoped, key=lambda item: item.revenue_7d, reverse=True)[:5]
    risky = sorted(
        [item for item in scoped if item.risk != ProductRisk.NORMAL.value],
        key=lambda item: (item.risk == ProductRisk.CRITICAL.value, item.revenue_7d),
        reverse=True,
    )[:4]

    risks = [
        DashboardRiskItem(
            id=f"risk-{item.id}",
            level=item.risk,
            title=item.risk_labels[0] if item.risk_labels else "商品异常待复核",
            detail=f"{item.sku} · {item.title}，当前库存 {item.stock} 件",
            estimated_loss=round(
                max(
                    item.revenue_7d
                    / 7
                    * (0.35 if item.risk == ProductRisk.CRITICAL.value else 0.16),
                    380,
                ),
                2,
            ),
            deadline="今天 14:00" if item.risk == ProductRisk.CRITICAL.value else "今天 18:00",
            route=f"/products?sku={item.sku}&risk={item.risk}",
            shop_name=item.shop_name,
        )
        for item in risky
    ]

    ai_summary = (
        f"{context_label}当前有 {critical} 个紧急商品风险；在线商品 {online} 个。"
        "AI 仅基于本页演示数据给出建议，不会自动执行高风险操作。"
    )

    return DashboardOverview(
        metrics=[
            DashboardMetric(
                key="sales",
                label="今日销售额",
                value=round(daily_sales * 1.14, 2),
                unit="currency",
                comparison=12.6,
                comparison_label="较昨日",
                definition="已支付订单实付金额，不含退款中订单",
            ),
            DashboardMetric(
                key="orders",
                label="支付订单",
                value=round(total_sales / 7 * 1.14),
                unit="integer",
                comparison=8.4,
                comparison_label="较昨日",
                definition="付款成功的去重订单数",
            ),
            DashboardMetric(
                key="conversion",
                label="平均转化率",
                unit="percent",
                value=round(sum(item.conversion_rate for item in scoped) / len(scoped), 2)
                if scoped
                else 0,
                comparison=-0.7,
                comparison_label="较上周同期",
                definition="支付买家数 / 商品详情访客数",
            ),
            DashboardMetric(
                key="aov",
                label="客单价",
                value=round(order_value, 2),
                unit="currency",
                comparison=3.2,
                comparison_label="较昨日",
                definition="支付金额 / 支付订单数",
            ),
        ],
        trend=trend,
        risks=risks,
        tasks=[
            OperationTask(
                id="task-001",
                title="补齐高风险 SKU 安全库存",
                owner="商品运营",
                status="进行中",
                progress=68,
                due_at="今天 14:00",
            ),
            OperationTask(
                id="task-002",
                title="复核周末活动价格冲突",
                owner="活动运营",
                status="待确认",
                progress=35,
                due_at="今天 17:30",
            ),
            OperationTask(
                id="task-003",
                title="更新抖店主图合规素材",
                owner="内容运营",
                status="进行中",
                progress=82,
                due_at="明天 11:00",
            ),
        ],
        top_products=[
            TopProduct(
                id=item.id,
                sku=item.sku,
                title=item.title,
                platform=item.platform,
                platform_label=item.platform_label,
                revenue=item.revenue_7d,
                sales=item.sales_7d,
                trend=round((index + 1) * 2.4 - 1.1, 1),
            )
            for index, item in enumerate(top)
        ],
        ai_brief=AiBrief(
            headline="优先保住高流量商品库存，再处理价格与素材异常",
            summary=ai_summary,
            evidence=[
                f"近 7 日商品成交额 ¥{total_revenue:,.0f}",
                f"高风险商品 {critical} 个",
                f"平均客单价 ¥{order_value:,.0f}",
            ],
            actions=["查看紧急商品", "生成今日运营清单", "复核能力与授权"],
            context_label=f"{context_label} · 2026-09-12",
        ),
        data_updated_at=DASHBOARD_UPDATED_AT,
    )
