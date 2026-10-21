from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.schemas.reports import (
    ReportExportJob,
    ReportMetric,
    ReportNote,
    ReportNoteRequest,
    ReportOverview,
    ReportRow,
    ReportTemplate,
    ReportTemplateType,
    ReportTrendPoint,
)
from app.services.report_export_service import list_exports
from app.services.shop_scope import parse_shop_scope

SHANGHAI = ZoneInfo("Asia/Shanghai")
DATA_UPDATED_AT = datetime(2026, 9, 13, 9, 40, tzinfo=SHANGHAI)
DEFAULT_ORG = "org-demo-001"

TEMPLATES = [
    ReportTemplate(
        id=ReportTemplateType.DAILY,
        name="运营日报",
        description="快速复盘当日成交、订单与风险",
        category="经营",
        default_metrics=["revenue", "orders", "refund_rate"],
    ),
    ReportTemplate(
        id=ReportTemplateType.WEEKLY,
        name="运营周报",
        description="对比本周与上周的核心经营变化",
        category="经营",
        default_metrics=["revenue", "orders", "roi", "refund_rate"],
    ),
    ReportTemplate(
        id=ReportTemplateType.MONTHLY,
        name="经营月报",
        description="沉淀月度经营结果与趋势",
        category="经营",
        default_metrics=["revenue", "orders", "spend", "roi"],
    ),
    ReportTemplate(
        id=ReportTemplateType.PRODUCT,
        name="商品业绩报表",
        description="识别商品成交贡献与售后风险",
        category="商品",
        default_metrics=["revenue", "orders", "refund_rate"],
    ),
    ReportTemplate(
        id=ReportTemplateType.AD,
        name="广告报表",
        description="核算广告花费、成交与投放回报",
        category="投放",
        default_metrics=["spend", "revenue", "roi"],
    ),
    ReportTemplate(
        id=ReportTemplateType.AFTER_SALE,
        name="售后报表",
        description="定位退款率与高频售后问题",
        category="售后",
        default_metrics=["refund_rate", "orders", "revenue"],
    ),
]

METRIC_LABELS = {
    "revenue": "成交金额",
    "orders": "支付订单",
    "spend": "广告消耗",
    "roi": "广告 ROI",
    "refund_rate": "退款率",
}

ROWS = [
    ReportRow(
        id="report-row-tb",
        name="氨基酸温和洁面乳 120g",
        shop_name="柔肤旗舰店",
        platform_label="淘宝",
        revenue=49860,
        orders=467,
        spend=12680,
        roi=3.93,
        refund_rate=1.8,
    ),
    ReportRow(
        id="report-row-dy",
        name="玻尿酸补水面霜 50g",
        shop_name="柔肤抖店旗舰店",
        platform_label="抖店",
        revenue=68400,
        orders=777,
        spend=15680,
        roi=4.36,
        refund_rate=2.6,
    ),
    ReportRow(
        id="report-row-pdd",
        name="敏感肌水乳套装",
        shop_name="柔肤拼多多专营店",
        platform_label="拼多多",
        revenue=33280,
        orders=399,
        spend=8650,
        roi=3.85,
        refund_rate=4.9,
    ),
]

NOTES: list[ReportNote] = [
    ReportNote(
        id="report-note-001",
        template_id=ReportTemplateType.WEEKLY,
        title="本周投放效率提升",
        conclusion="抖店短视频引流计划贡献了最高成交，整体 ROI 高于上周。",
        next_actions="继续观察敏感肌人群扩量计划，先优化素材再考虑增加预算。",
        author="徐店长",
        created_at=DATA_UPDATED_AT - timedelta(days=1),
    ),
]


def _scoped_rows(shop_id: str) -> list[ReportRow]:
    scope = parse_shop_scope(shop_id)
    mapping = {
        "柔肤旗舰店": "shop-taobao-001",
        "柔肤抖店旗舰店": "shop-douyin-001",
        "柔肤拼多多专营店": "shop-pdd-001",
    }
    return [row for row in ROWS if scope is None or mapping[row.shop_name] in scope]


def _trend(rows: list[ReportRow]) -> list[ReportTrendPoint]:
    factors = [0.72, 0.84, 0.81, 0.93, 0.97, 1.06, 1.0]
    revenue = sum(row.revenue for row in rows)
    orders = sum(row.orders for row in rows)
    spend = sum(row.spend for row in rows)
    refunds = sum(row.orders * row.refund_rate / 100 for row in rows)
    return [
        ReportTrendPoint(
            date=(DATA_UPDATED_AT - timedelta(days=6 - index)).strftime("%m-%d"),
            revenue=round(revenue / 7 * factor, 2),
            orders=round(orders / 7 * factor),
            spend=round(spend / 7 * factor, 2),
            refunds=round(refunds / 7 * factor, 2),
        )
        for index, factor in enumerate(factors)
    ]


def get_report_overview(
    db: Session,
    shop_id: str,
    template_id: ReportTemplateType = ReportTemplateType.WEEKLY,
    metrics: str = "",
) -> ReportOverview:
    rows = _scoped_rows(shop_id)
    selected = next(template for template in TEMPLATES if template.id == template_id)
    selected_metrics = [
        item for item in metrics.split(",") if item in METRIC_LABELS
    ] or selected.default_metrics
    revenue = sum(row.revenue for row in rows)
    orders = sum(row.orders for row in rows)
    spend = sum(row.spend for row in rows)
    refund_rate = sum(row.orders * row.refund_rate for row in rows) / orders if orders else 0
    values = {
        "revenue": revenue,
        "orders": orders,
        "spend": spend,
        "roi": revenue / spend if spend else 0,
        "refund_rate": refund_rate,
    }
    changes = {"revenue": 12.4, "orders": 8.7, "spend": -4.2, "roi": 9.6, "refund_rate": -0.8}
    report_metrics = [
        ReportMetric(
            key=key,
            label=METRIC_LABELS[key],
            value=round(values[key], 2),
            display_value=(
                f"¥{values[key]:,.0f}"
                if key in {"revenue", "spend"}
                else f"{values[key]:,.2f}%"
                if key == "refund_rate"
                else f"{values[key]:,.2f}"
                if key == "roi"
                else f"{values[key]:,.0f}"
            ),
            change=changes[key],
            direction="up" if changes[key] >= 0 else "down",
        )
        for key in selected_metrics
    ]
    return ReportOverview(
        templates=TEMPLATES,
        selected_template=template_id,
        selected_metrics=selected_metrics,
        metrics=report_metrics,
        trend=_trend(rows),
        rows=rows,
        exports=[
            ReportExportJob(**item)
            for item in list_exports(db, DEFAULT_ORG, limit=8)
        ],
        notes=[note for note in NOTES if note.template_id == template_id],
        data_updated_at=DATA_UPDATED_AT,
    )


def create_note(request: ReportNoteRequest) -> ReportNote:
    note = ReportNote(
        id=f"report-note-{len(NOTES) + 1:03d}",
        template_id=request.template_id,
        title=request.title,
        conclusion=request.conclusion,
        next_actions=request.next_actions,
        author="徐店长",
        created_at=DATA_UPDATED_AT,
    )
    NOTES.insert(0, note)
    return note
