"""诊断反思引擎：规则诊断 + 证据校验 + 风险分级。

对应文档第四阶段"诊断反思 Agent"，三条硬约束在此落地：

1. 无证据不结论：每条诊断必须携带 evidence（指标名/实测值/阈值/来源），
   反思阶段对 evidence 为空的结论直接丢弃并记录原因；
2. 信息不足不硬编：竞品覆盖不足或数据缺失时，相关结论置信度降级并
   触发补采信号，由编排器决定重新调度，而不是强行输出方案；
3. 高风险不自动执行：涉及改价、上下架、批量修改标题的建议 risk_level=high，
   初始状态保持 pending，必须人工确认后才能进入后续动作。
"""
from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

from app.db.models import ProductModel
from app.services.order_repository import ORDERS

SHANGHAI = ZoneInfo("Asia/Shanghai")

LOW_STOCK_THRESHOLD = 25
CONVERSION_THRESHOLD = 3.0
MARGIN_THRESHOLD = 0.20
PRICE_GAP_RATIO = 0.05
AFTER_SALE_THRESHOLD_MINUTES = 120
MIN_COMPETITOR_COVERAGE = 2

# 建议文案命中这些词即视为高风险写操作建议
HIGH_RISK_KEYWORDS = (
    "改价",
    "调整价格",
    "价格下调",
    "上下架",
    "下架",
    "上架",
    "修改标题",
    "批量修改",
    "批量调整",
)


def _evidence(metric: str, value: Any, threshold: Any, source: str) -> dict[str, Any]:
    return {"metric": metric, "value": value, "threshold": threshold, "source": source}


def _is_high_risk(recommendation: str) -> bool:
    return any(keyword in recommendation for keyword in HIGH_RISK_KEYWORDS)


def check_data_quality(products: list[ProductModel]) -> dict[str, Any]:
    """数据 Agent 的质量校验：缺失字段、异常值、空数据。"""
    missing_cost = [p.sku for p in products if p.cost <= 0]
    zero_sales_online = [p.sku for p in products if p.status == "online" and p.sales_7d <= 0]
    zero_conversion_online = [
        p.sku for p in products if p.status == "online" and p.conversion_rate <= 0
    ]
    return {
        "product_count": len(products),
        "missing_cost_skus": missing_cost,
        "zero_sales_online_skus": zero_sales_online,
        "zero_conversion_online_skus": zero_conversion_online,
        "issues": (
            bool(missing_cost) or bool(zero_sales_online) or bool(zero_conversion_online)
        ),
    }


def _inventory_drafts(products: list[ProductModel]) -> list[dict]:
    drafts = []
    for product in products:
        if product.stock <= 0:
            drafts.append(
                {
                    "product_id": product.id,
                    "shop_id": product.shop_id,
                    "shop_name": product.shop_name,
                    "kind": "inventory",
                    "severity": "critical",
                    "title": f"{product.title} 库存为零",
                    "detail": (
                        f"{product.shop_name} 的 {product.title} 已无可售库存，"
                        "链接存在失效风险。"
                    ),
                    "evidence": [
                        _evidence("stock", product.stock, "> 0", "商品中心实时数据"),
                        _evidence(
                            "sales_7d",
                            product.sales_7d,
                            "参考近 7 日销量",
                            "商品中心实时数据",
                        ),
                    ],
                    "recommendation": (
                        "立即补货或临时下架链接，避免平台判定无货违规"
                        "（下架需人工确认）"
                    ),
                }
            )
        elif product.stock < LOW_STOCK_THRESHOLD:
            drafts.append(
                {
                    "product_id": product.id,
                    "shop_id": product.shop_id,
                    "shop_name": product.shop_name,
                    "kind": "inventory",
                    "severity": "warning",
                    "title": f"{product.title} 库存低于安全线",
                    "detail": (
                        f"当前库存 {product.stock} 件，按近 7 日销量 "
                        f"{product.sales_7d} 件测算约可售 "
                        f"{round(product.stock / max(product.sales_7d / 7, 0.1), 1)} 天。"
                    ),
                    "evidence": [
                        _evidence(
                            "stock",
                            product.stock,
                            f">= {LOW_STOCK_THRESHOLD}",
                            "商品中心实时数据",
                        ),
                        _evidence(
                            "sales_7d",
                            product.sales_7d,
                            "参考近 7 日销量",
                            "商品中心实时数据",
                        ),
                    ],
                    "recommendation": "生成补货任务并同步投放上限，防止断货损失（只读建议）",
                }
            )
    return drafts


def _margin_drafts(products: list[ProductModel]) -> list[dict]:
    drafts = []
    for product in products:
        if product.cost <= 0:
            continue  # 无成本数据不算毛利结论，交给数据质量校验
        margin = (product.price - product.cost) / max(product.price, 0.01)
        if margin < MARGIN_THRESHOLD:
            drafts.append(
                {
                    "product_id": product.id,
                    "shop_id": product.shop_id,
                    "shop_name": product.shop_name,
                    "kind": "margin",
                    "severity": "warning",
                    "title": f"{product.title} 毛利率低于 {MARGIN_THRESHOLD:.0%}",
                    "detail": (
                        f"售价 {product.price:.2f} 元、成本 {product.cost:.2f} 元，"
                        f"毛利率 {margin:.1%}，低于安全线。"
                    ),
                    "evidence": [
                        _evidence("price", product.price, "-", "商品中心实时数据"),
                        _evidence("cost", product.cost, "-", "商品中心实时数据"),
                        _evidence(
                            "margin",
                            f"{margin:.1%}",
                            f">= {MARGIN_THRESHOLD:.0%}",
                            "本地计算",
                        ),
                    ],
                    "recommendation": "核算渠道费用后决定是否调价或更换规格组合（改价需人工确认）",
                }
            )
    return drafts


def _conversion_drafts(products: list[ProductModel]) -> list[dict]:
    drafts = []
    for product in products:
        if product.status != "online" or product.conversion_rate <= 0:
            continue
        if product.conversion_rate < CONVERSION_THRESHOLD:
            drafts.append(
                {
                    "product_id": product.id,
                    "shop_id": product.shop_id,
                    "shop_name": product.shop_name,
                    "kind": "conversion",
                    "severity": "warning",
                    "title": f"{product.title} 转化率低于类目参考值",
                    "detail": (
                        f"当前转化率 {product.conversion_rate:.1f}%，低于参考阈值 "
                        f"{CONVERSION_THRESHOLD:.1f}%，需结合竞品卖点排查主图与价格。"
                    ),
                    "evidence": [
                        _evidence(
                            "conversion_rate",
                            f"{product.conversion_rate:.1f}%",
                            f">= {CONVERSION_THRESHOLD:.1f}%",
                            "商品中心实时数据",
                        ),
                    ],
                    "recommendation": "对比竞品卖点与定价，优化主图利益点（只读建议）",
                }
            )
    return drafts


def _review_drafts(products: list[ProductModel]) -> list[dict]:
    drafts = []
    for product in products:
        labels = list(product.risk_labels)
        if not any("差评" in label for label in labels):
            continue
        drafts.append(
            {
                "product_id": product.id,
                "shop_id": product.shop_id,
                "shop_name": product.shop_name,
                "kind": "review",
                "severity": "critical",
                "title": f"{product.title} 差评风险升高",
                "detail": f"风险标签：{'；'.join(labels)}。差评会直接影响转化与店铺体验分。",
                "evidence": [
                    _evidence("risk_labels", "；".join(labels), "-", "商品中心风险标签"),
                ],
                "recommendation": "优先处理差评工单并回复安抚，暂不改动商品（只读建议）",
            }
        )
    return drafts


def _price_gap_drafts(
    products: list[ProductModel], competitor_map: dict[str, list[dict]]
) -> list[dict]:
    drafts = []
    for product in products:
        competitors = competitor_map.get(product.id, [])
        if not competitors:
            continue
        cheapest = min(competitors, key=lambda item: item["price"])
        if cheapest["price"] >= product.price * (1 - PRICE_GAP_RATIO):
            continue
        gap = (product.price - cheapest["price"]) / max(product.price, 0.01)
        drafts.append(
            {
                "product_id": product.id,
                "shop_id": product.shop_id,
                "shop_name": product.shop_name,
                "kind": "price_gap",
                "severity": "warning",
                "title": f"{product.title} 面临竞品低价挤压",
                "detail": (
                    f"对标竞品「{cheapest['title']}」售价 {cheapest['price']:.2f} 元，"
                    f"低于本店 {gap:.1%}（相似度 {cheapest.get('similarity', 0):.2f}）。"
                ),
                "evidence": [
                    _evidence("price", product.price, "-", "商品中心实时数据"),
                    _evidence(
                        "competitor_price",
                        cheapest["price"],
                        f"本店价 x (1 - {PRICE_GAP_RATIO:.0%}) 以内",
                        f"竞品库：{cheapest['title']}",
                    ),
                    _evidence(
                        "competitor_sales_7d",
                        cheapest["sales_7d"],
                        "-",
                        f"竞品库：{cheapest['title']}",
                    ),
                ],
                "recommendation": (
                    "评估跟价、优惠券或差异化卖点应对（改价需人工确认）"
                ),
            }
        )
    return drafts


def _after_sale_drafts() -> list[dict]:
    drafts = []
    for order in ORDERS:
        status = order.after_sale_status.value
        remaining = order.remaining_minutes
        if status not in {"requested", "merchant_processing"}:
            continue
        if remaining is None or remaining > AFTER_SALE_THRESHOLD_MINUTES:
            continue
        drafts.append(
            {
                "product_id": None,
                "shop_id": order.shop_id,
                "shop_name": order.shop_name,
                "kind": "after_sale",
                "severity": "critical" if remaining <= 30 else "warning",
                "title": f"售后即将超时：{order.order_no}",
                "detail": f"{order.shop_name} 订单 {order.order_no} 售后剩余 {remaining} 分钟。",
                "evidence": [
                    _evidence(
                        "remaining_minutes",
                        remaining,
                        f"> {AFTER_SALE_THRESHOLD_MINUTES}",
                        "订单中心实时数据",
                    ),
                    _evidence("after_sale_status", status, "-", "订单中心实时数据"),
                ],
                "recommendation": "立即进入订单台处理并确认回复口径（只读建议）",
            }
        )
    return drafts


def run_diagnosis(
    products: list[ProductModel],
    competitor_map: dict[str, list[dict]],
    *,
    include_after_sale: bool = True,
    shop_scope: set[str] | None = None,
) -> list[dict]:
    """汇总全部规则诊断。每条草稿必带 evidence。

    shop_scope 非空时，售后类诊断只保留范围內店铺（与商品范围保持一致）。
    """
    drafts: list[dict] = []
    drafts.extend(_inventory_drafts(products))
    drafts.extend(_margin_drafts(products))
    drafts.extend(_conversion_drafts(products))
    drafts.extend(_review_drafts(products))
    drafts.extend(_price_gap_drafts(products, competitor_map))
    if include_after_sale:
        drafts.extend(
            draft
            for draft in _after_sale_drafts()
            if shop_scope is None or draft["shop_id"] in shop_scope
        )
    for draft in drafts:
        draft["confidence"] = "high"
        draft["risk_level"] = "high" if _is_high_risk(draft["recommendation"]) else "low"
        draft["status"] = "pending"
        draft["decided_by"] = None
        draft["decision_note"] = None
        draft["decided_at"] = None
    return drafts


def reflect(
    drafts: list[dict],
    *,
    data_quality: dict[str, Any],
    competitor_coverage: dict[str, int],
) -> dict[str, Any]:
    """反思自检：证据校验、充足性判断、风险标注。

    返回 {kept, discarded, notes, supplement}。supplement 指示编排器
    是否需要补采数据或竞品后重跑诊断（闭环迭代，最多由编排器限轮次）。
    """
    kept: list[dict] = []
    discarded: list[dict] = []
    notes: list[str] = []
    supplement = {"data": False, "competitor": False}

    for draft in drafts:
        if not draft.get("evidence"):
            discarded.append({"title": draft["title"], "reason": "缺少指标证据，反思阶段判定无效"})
            continue
        if draft["kind"] == "price_gap":
            product_id = draft.get("product_id") or ""
            coverage = competitor_coverage.get(product_id, 0)
            if coverage < MIN_COMPETITOR_COVERAGE:
                draft["confidence"] = "low"
                notes.append(
                    f"「{draft['title']}」竞品覆盖不足（{coverage}/{MIN_COMPETITOR_COVERAGE}），"
                    "置信度降级并触发竞品补采"
                )
                supplement["competitor"] = True
        if draft["kind"] == "margin" and data_quality.get("missing_cost_skus"):
            draft["confidence"] = "low"
            notes.append("部分商品缺少成本价，毛利类结论置信度受限")
        kept.append(draft)

    if data_quality.get("issues"):
        supplement["data"] = True
        notes.append(
            "数据质量校验发现缺失字段："
            f"缺成本价 {len(data_quality.get('missing_cost_skus', []))} 个 SKU，"
            f"在线无销量 {len(data_quality.get('zero_sales_online_skus', []))} 个 SKU"
        )

    high_risk = sum(1 for item in kept if item.get("risk_level") == "high")
    if high_risk:
        notes.append(f"{high_risk} 条结论涉及写操作建议，已拦截机器自主执行，等待人工确认")

    return {
        "kept": kept,
        "discarded": discarded,
        "notes": notes,
        "supplement": supplement,
    }
