"""数据诊断服务：健康分、问题清单与店铺对比。

对应实施计划阶段 E 与 IMPLEMENTATION_PLAN 6.6 的设计约束：

- 健康分保留**可解释分项**与**版本化算法**（`HEALTH_ALGORITHM_VERSION`），
  分数变动可追溯，不搞黑箱加权；
- 问题清单按「预计损失金额 × 紧迫度 × 置信度」排序，且每条问题沿用
  诊断引擎的证据链约束，无数据支撑不进清单；
- 指标口径由服务端下发（`metric_definitions`），前端统一展示，
  估算值明确标注假设，不把估算伪装成实时事实。
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ProductModel, ShopModel
from app.services.competitor_repository import DEFAULT_CATEGORY, search_competitors
from app.services.diagnosis_engine import (
    AFTER_SALE_THRESHOLD_MINUTES,
    CONVERSION_THRESHOLD,
    LOW_STOCK_THRESHOLD,
    MARGIN_THRESHOLD,
    run_diagnosis,
)
from app.services.order_repository import ORDERS

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_ORG = "org-demo-001"

HEALTH_ALGORITHM_VERSION = "health-score-v1"

HEALTH_WEIGHTS: dict[str, float] = {
    "inventory": 0.30,
    "conversion": 0.20,
    "review": 0.20,
    "price": 0.15,
    "after_sale": 0.15,
}

HEALTH_LABELS: dict[str, str] = {
    "inventory": "库存健康",
    "conversion": "转化效率",
    "review": "差评风险",
    "price": "价格竞争力",
    "after_sale": "售后时效",
}

# 置信度折算系数：反思阶段降级的结论在排序中同步降权
CONFIDENCE_FACTOR: dict[str, float] = {"high": 1.0, "medium": 0.7, "low": 0.4}

# 售后类问题的客单价假设（演示数据订单不含金额字段，估算值必须带假设说明）
AFTER_SALE_ASSUMED_TICKET = {"critical": 300.0, "warning": 150.0}

METRIC_DEFINITIONS: list[dict[str, str]] = [
    {
        "key": "health_score",
        "label": "店铺健康分",
        "definition": (
            "五个可解释分项（库存健康、转化效率、差评风险、价格竞争力、售后时效）"
            "按固定权重加权平均，每项 0-100，算法版本 health-score-v1。"
        ),
        "unit": "分",
    },
    {
        "key": "estimated_loss",
        "label": "预计损失",
        "definition": (
            "基于近 7 日销量、毛利率与问题系数的估算金额，用于排序优先级，"
            "不是财务口径的实际损失。"
        ),
        "unit": "元",
    },
    {
        "key": "urgency",
        "label": "紧迫度",
        "definition": "按售后剩余时效、库存可售天数或问题严重度折算为 0-100 分。",
        "unit": "分",
    },
    {
        "key": "conversion_rate",
        "label": "转化率",
        "definition": f"低于 {CONVERSION_THRESHOLD:.1f}% 判定为转化异常，参考值为演示环境阈值。",
        "unit": "%",
    },
    {
        "key": "margin",
        "label": "毛利率",
        "definition": f"（售价 - 成本价）/ 售价，低于 {MARGIN_THRESHOLD:.0%} 判定为毛利偏低。",
        "unit": "%",
    },
    {
        "key": "low_stock",
        "label": "库存安全线",
        "definition": f"库存低于 {LOW_STOCK_THRESHOLD} 件判定为低于安全线，为零判定为缺货。",
        "unit": "件",
    },
    {
        "key": "after_sale_sla",
        "label": "售后时效",
        "definition": f"售后剩余时间在 {AFTER_SALE_THRESHOLD_MINUTES} 分钟内的订单进入预警。",
        "unit": "分钟",
    },
]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 1)


def _load_products(db: Session, shop_scope: set[str] | None) -> list[ProductModel]:
    statement = select(ProductModel).where(ProductModel.organization_id == DEFAULT_ORG)
    if shop_scope is not None:
        statement = statement.where(ProductModel.shop_id.in_(shop_scope))
    return list(db.scalars(statement).all())


def _match_competitors(products: list[ProductModel]) -> dict[str, list[dict]]:
    from app.db.session import session_scope

    competitor_map: dict[str, list[dict]] = {}
    with session_scope() as db:
        for product in products:
            competitor_map[product.id] = search_competitors(
                db,
                query_texts=[product.title],
                category=DEFAULT_CATEGORY,
                organization_id=DEFAULT_ORG,
                limit=3,
            )
    return competitor_map


def _gross_margin(product: ProductModel) -> float | None:
    if product.cost <= 0 or product.price <= 0:
        return None
    return (product.price - product.cost) / product.price


def _inventory_component(products: list[ProductModel]) -> dict:
    if not products:
        return {"score": 100.0, "detail": "范围内暂无商品"}
    zero = sum(1 for item in products if item.stock <= 0)
    low = sum(1 for item in products if 0 < item.stock < LOW_STOCK_THRESHOLD)
    total = len(products)
    score = 100.0 - (zero * 100 + low * 50) / total
    return {
        "score": _clamp(score),
        "detail": f"{total} 个 SKU 中缺货 {zero} 个、低于安全线 {low} 个",
    }


def _conversion_component(products: list[ProductModel]) -> dict:
    online = [item for item in products if item.status == "online" and item.conversion_rate > 0]
    if not online:
        return {"score": 100.0, "detail": "范围内暂无有效转化数据"}
    below = [item for item in online if item.conversion_rate < CONVERSION_THRESHOLD]
    # 按 7 日销量加权：销量越大的 SKU 转化异常影响越大
    total_sales = sum(item.sales_7d for item in online) or 1
    weighted = sum(item.sales_7d for item in below) / total_sales
    score = 100.0 - weighted * 100
    return {
        "score": _clamp(score),
        "detail": (
            f"{len(below)}/{len(online)} 个在售 SKU 转化率低于 "
            f"{CONVERSION_THRESHOLD:.1f}%，按销量加权影响 {weighted:.0%}"
        ),
    }


def _review_component(products: list[ProductModel]) -> dict:
    if not products:
        return {"score": 100.0, "detail": "范围内暂无商品"}
    flagged = [
        item for item in products if any("差评" in label for label in item.risk_labels)
    ]
    ratio = len(flagged) / len(products)
    return {
        "score": _clamp(100.0 - ratio * 100),
        "detail": f"{len(flagged)}/{len(products)} 个 SKU 带差评风险标签",
    }


def _price_component(
    products: list[ProductModel], competitor_map: dict[str, list[dict]]
) -> dict:
    matched = [
        product
        for product in products
        if competitor_map.get(product.id)
        and min(item["price"] for item in competitor_map[product.id])
        < product.price * 0.95
    ]
    if not products:
        return {"score": 100.0, "detail": "范围内暂无商品"}
    ratio = len(matched) / len(products)
    return {
        "score": _clamp(100.0 - ratio * 100),
        "detail": (
            f"{len(matched)}/{len(products)} 个 SKU 面临竞品低价挤压"
            if matched
            else "暂未发现竞品低价挤压"
        ),
    }


def _after_sale_component(shop_scope: set[str] | None) -> dict:
    scoped = [
        item
        for item in ORDERS
        if shop_scope is None or item.shop_id in shop_scope
    ]
    pending = [
        item
        for item in scoped
        if item.after_sale_status.value in {"requested", "merchant_processing"}
    ]
    risky = [
        item
        for item in pending
        if item.remaining_minutes is not None
        and item.remaining_minutes <= AFTER_SALE_THRESHOLD_MINUTES
    ]
    if not pending:
        return {"score": 100.0, "detail": "暂无待处理售后订单"}
    ratio = len(risky) / len(pending)
    return {
        "score": _clamp(100.0 - ratio * 100),
        "detail": f"{len(risky)}/{len(pending)} 个待处理售后将在时效内到期",
    }


def compute_health(
    products: list[ProductModel],
    competitor_map: dict[str, list[dict]],
    shop_scope: set[str] | None,
) -> dict:
    """计算健康分与可解释分项。"""
    components = {
        "inventory": _inventory_component(products),
        "conversion": _conversion_component(products),
        "review": _review_component(products),
        "price": _price_component(products, competitor_map),
        "after_sale": _after_sale_component(shop_scope),
    }
    total = sum(item["score"] * HEALTH_WEIGHTS[key] for key, item in components.items())
    return {
        "score": _clamp(total),
        "algorithm_version": HEALTH_ALGORITHM_VERSION,
        "components": [
            {
                "key": key,
                "label": HEALTH_LABELS[key],
                "score": components[key]["score"],
                "weight": HEALTH_WEIGHTS[key],
                "detail": components[key]["detail"],
            }
            for key in HEALTH_WEIGHTS
        ],
    }


def _estimated_loss(draft: dict, products_by_id: dict[str, ProductModel]) -> tuple[float, str]:
    """估算问题损失金额，返回（金额，假设说明）。估算值必须带口径。"""
    kind = draft["kind"]
    product = products_by_id.get(draft.get("product_id") or "")
    if kind == "inventory":
        if product is None:
            return 0.0, "未关联商品，不做金额估算"
        daily_sales = product.sales_7d / 7
        margin = _gross_margin(product)
        if margin is None:
            return 0.0, "缺少成本价，仅按销量估算优先级"
        if draft["severity"] == "critical":
            return (
                round(daily_sales * 7 * margin * 0.6, 2),
                "按日均销量 x 7 天 x 毛利率 x 缺货系数 0.6 估算",
            )
        return (
            round(daily_sales * 3 * margin * 0.3, 2),
            "按日均销量 x 3 天 x 毛利率 x 低库存系数 0.3 估算",
        )
    if kind in {"conversion", "review"} and product is not None:
        factor = 0.15 if kind == "conversion" else 0.20
        return (
            round(product.revenue_7d * factor, 2),
            f"按近 7 日销售额 x 影响系数 {factor:.0%} 估算",
        )
    if kind == "price_gap" and product is not None:
        evidence = draft.get("evidence", [])
        competitor_price = next(
            (item for item in evidence if item["metric"] == "competitor_price"), None
        )
        if competitor_price is None or product.price <= 0:
            return 0.0, "缺少竞品价格证据，不做金额估算"
        gap = (product.price - float(competitor_price["value"])) / product.price
        return (
            round(product.revenue_7d * gap * 0.5, 2),
            "按近 7 日销售额 x 价差比例 x 流失系数 0.5 估算",
        )
    if kind == "margin" and product is not None:
        margin = _gross_margin(product) or 0.0
        shortfall = max(MARGIN_THRESHOLD - margin, 0.0)
        return (
            round(product.revenue_7d * shortfall * 0.5, 2),
            "按近 7 日销售额 x 毛利缺口 x 折算系数 0.5 估算",
        )
    if kind == "after_sale":
        assumed = AFTER_SALE_ASSUMED_TICKET.get(draft["severity"], 150.0)
        return assumed, f"订单金额未同步，按客单价假设 {assumed:.0f} 元估算"
    return 0.0, "该问题类型不做金额估算"


def _urgency(draft: dict, products_by_id: dict[str, ProductModel]) -> int:
    kind = draft["kind"]
    if kind == "after_sale":
        evidence = draft.get("evidence", [])
        remaining = next(
            (item for item in evidence if item["metric"] == "remaining_minutes"), None
        )
        if remaining is not None:
            minutes = float(remaining["value"])
            if minutes <= 30:
                return 100
            if minutes >= AFTER_SALE_THRESHOLD_MINUTES:
                return 20
            return int(100 - (minutes - 30) / (AFTER_SALE_THRESHOLD_MINUTES - 30) * 80)
        return 50
    if kind == "inventory":
        product = products_by_id.get(draft.get("product_id") or "")
        if product is not None:
            if product.stock <= 0:
                return 100
            days = product.stock / max(product.sales_7d / 7, 0.1)
            if days <= 1:
                return 95
            if days >= 14:
                return 10
            return int(95 - (days - 1) / 13 * 85)
    return 70 if draft["severity"] == "critical" else 40


def build_issues(
    products: list[ProductModel],
    competitor_map: dict[str, list[dict]],
    shop_scope: set[str] | None,
) -> list[dict]:
    """汇总问题清单并计算优先级分数。"""
    drafts = run_diagnosis(products, competitor_map, shop_scope=shop_scope)
    products_by_id = {product.id: product for product in products}
    issues: list[dict] = []
    for draft in drafts:
        loss, loss_note = _estimated_loss(draft, products_by_id)
        urgency = _urgency(draft, products_by_id)
        confidence = draft.get("confidence", "high")
        priority = round(
            loss * (urgency / 100) * CONFIDENCE_FACTOR.get(confidence, 0.4), 2
        )
        product = products_by_id.get(draft.get("product_id") or "")
        issues.append(
            {
                **draft,
                "product_title": product.title if product else None,
                "estimated_loss": loss,
                "loss_note": loss_note,
                "urgency": urgency,
                "priority": priority,
            }
        )
    issues.sort(key=lambda item: item["priority"], reverse=True)
    return issues


def build_comparison(
    db: Session,
    competitor_map_by_shop: dict[str, dict[str, list[dict]]],
) -> list[dict]:
    """店铺横向对比（各店健康分与问题分布）。"""
    shops = list(
        db.scalars(
            select(ShopModel).where(
                ShopModel.organization_id == DEFAULT_ORG,
                ShopModel.id != "shop-all",
            )
        ).all()
    )
    rows: list[dict] = []
    for shop in shops:
        statement = select(ProductModel).where(
            ProductModel.organization_id == DEFAULT_ORG,
            ProductModel.shop_id == shop.id,
        )
        products = list(db.scalars(statement).all())
        if not products:
            continue
        competitor_map = competitor_map_by_shop.get(shop.id, {})
        health = compute_health(products, competitor_map, {shop.id})
        issues = build_issues(products, competitor_map, {shop.id})
        rows.append(
            {
                "shop_id": shop.id,
                "shop_name": shop.name,
                "platform_label": shop.platform_label,
                "health_score": health["score"],
                "product_count": len(products),
                "critical_issues": sum(1 for item in issues if item["severity"] == "critical"),
                "warning_issues": sum(1 for item in issues if item["severity"] == "warning"),
                "revenue_7d": round(sum(item.revenue_7d for item in products), 2),
                "data_source": shop.data_source,
            }
        )
    rows.sort(key=lambda item: item["health_score"], reverse=True)
    return rows


def get_overview(db: Session, shop_id: str) -> dict:
    """诊断总览：健康分 + 问题清单 + 店铺对比 + 指标口径。"""
    shop_scope = None if shop_id in {"", "shop-all"} else {shop_id}
    products = _load_products(db, shop_scope)
    competitor_map = _match_competitors(products)
    health = compute_health(products, competitor_map, shop_scope)
    issues = build_issues(products, competitor_map, shop_scope)

    # 对比模块按店各自匹配竞品（演示数据量小；规模化后应按类目批量检索优化）
    shop_rows = list(
        db.scalars(
            select(ShopModel).where(
                ShopModel.organization_id == DEFAULT_ORG,
                ShopModel.id != "shop-all",
            )
        ).all()
    )
    comparison_map: dict[str, dict[str, list[dict]]] = {}
    data_sources: list[str] = []
    for shop in shop_rows:
        shop_products = _load_products(db, {shop.id})
        if not shop_products:
            continue
        comparison_map[shop.id] = _match_competitors(shop_products)
        data_sources.append(shop.data_source)
    comparison = build_comparison(db, comparison_map)

    is_demo = "live" not in data_sources
    return {
        "shop_id": shop_id,
        "generated_at": datetime.now(SHANGHAI),
        "data_source": "seeded" if is_demo else "live",
        "is_demo": is_demo,
        "health": health,
        "issues": issues,
        "comparison": comparison,
        "metric_definitions": METRIC_DEFINITIONS,
    }
