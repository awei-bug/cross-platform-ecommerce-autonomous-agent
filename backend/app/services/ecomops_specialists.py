"""Business calculations and evidence-producing specialist tools.

Pure local tools never claim platform side effects or model-generated text.
"""

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.ecomops import OpsRecord, OpsRun, OpsTask
from app.schemas.ecomops import BusinessInput, Policy
from app.services.ecomops_catalog import AGENTS, EXTERNAL_STEPS, PLATFORMS


class Hold(Exception):
    def __init__(self, status: str, reason: str, output: dict | None = None):
        self.status, self.reason, self.output = status, reason, output or {}
        super().__init__(reason)


def records(db: Session, org: str, kind: str) -> list[OpsRecord]:
    return list(
        db.scalars(
            select(OpsRecord).where(
                OpsRecord.organization_id == org,
                OpsRecord.kind == kind,
            )
        )
    )


def content_for(db: Session, run: OpsRun) -> str:
    data = BusinessInput(**run.input)
    product = next(
        (
            r
            for r in records(db, run.organization_id, "product")
            if r.key == data.sku.strip().upper()
        ),
        None,
    )
    return "\n".join(
        [
            data.title,
            data.content,
            *(
                [str(product.payload.get("title", "")), str(product.payload.get("description", ""))]
                if product
                else []
            ),
        ]
    )


def scan(text: str, policy: Policy) -> tuple[str, list[dict]]:
    matches = []
    for rule in policy.rules:
        if rule.pattern.casefold() in text.casefold():
            matches.append(rule.model_dump())
            if rule.level == "low":
                # Literal, case insensitive replacement; never execute user regexes.
                import re

                text = re.sub(
                    re.escape(rule.pattern),
                    lambda _, value=rule.replacement: value,
                    text,
                    flags=re.IGNORECASE,
                )
    return text.strip(), matches


def costs(data: BusinessInput) -> dict:
    fixed = data.procurement + data.freight + data.tax + data.loss
    variable_rate = (data.commission_pct + data.ad_rate_pct) / 100
    landed = fixed + data.price * variable_rate
    profit = data.price - landed
    margin = profit / data.price * 100 if data.price else 0
    return {
        "currency": data.currency,
        "fx_to_usd": data.exchange_rate_to_usd,
        "fixed_cost": round(fixed, 4),
        "landed_cost": round(landed, 4),
        "break_even_price": round(fixed / (1 - variable_rate), 4),
        "unit_profit": round(profit, 4),
        "margin_pct": round(margin, 2),
        "expected_roi_pct": round(profit / landed * 100, 2) if landed else None,
        "stock_amount_usd": round(data.procurement * data.quantity * data.exchange_rate_to_usd, 2),
        "formula": "landed = 采购+头程+税费+损耗+售价×(佣金率+广告费率)",
        "source": "提交的成本报价与汇率；未经供应商或平台核实",
    }


def aggregate(db: Session, org: str) -> dict:
    rows = records(db, org, "metric")
    fields = [
        "revenue",
        "cost",
        "ad_spend",
        "orders",
        "customers",
        "repeat_customers",
        "refunds",
        "visits",
        "conversions",
    ]
    totals = {key: sum(float(r.payload.get(key, 0)) for r in rows) for key in fields}
    revenue, orders = totals["revenue"], totals["orders"]

    def ratio(a, b):
        return round(a / b, 4) if b else None

    return {
        "currency": "USD",
        "totals": totals,
        "gmv": revenue,
        "gross_margin": ratio(revenue - totals["cost"], revenue),
        "average_order_value": ratio(revenue, orders),
        "repeat_rate": ratio(totals["repeat_customers"], totals["customers"]),
        "refund_rate": ratio(totals["refunds"], orders),
        "conversion_rate": ratio(totals["conversions"], totals["visits"]),
        "marketing_roas": ratio(revenue, totals["ad_spend"]),
        "net_roi": ratio(
            revenue - totals["cost"] - totals["ad_spend"], totals["cost"] + totals["ad_spend"]
        ),
        "evidence": [{"key": r.key, "source": r.source, "is_demo": r.is_demo} for r in rows],
        "scope": "已导入的非重叠 USD 指标区间；空分母返回 null；不等同归因广告 ROI",
        "missing": [] if rows else ["尚无指标数据，不能推断经营表现"],
    }


def performance(db: Session, org: str) -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    tasks = list(
        db.scalars(
            select(OpsTask)
            .join(OpsRun, OpsTask.run_id == OpsRun.id)
            .where(
                OpsTask.organization_id == org,
                OpsRun.created_at >= cutoff,
            )
        )
    )
    result = []
    for key, name, _ in AGENTS:
        own = [t for t in tasks if t.agent == key]
        elapsed = [
            (t.completed_at - t.started_at).total_seconds() * 1000
            for t in own
            if t.completed_at and t.started_at
        ]
        result.append(
            {
                "id": key,
                "name": name,
                "tasks": len(own),
                "succeeded": sum(t.status == "succeeded" for t in own),
                "completion_rate": (
                    sum(t.status == "succeeded" for t in own) / len(own) if own else None
                ),
                "avg_duration_ms": round(sum(elapsed) / len(elapsed), 2) if elapsed else None,
                "decision_accuracy": None,
                "cost_saved": None,
            }
        )
    return {
        "window_days": 30,
        "agents": result,
        "limitation": "准确率与成本节约需人工标注和成本基线，当前不估造",
    }


def execute_tool(db: Session, run: OpsRun, task: OpsTask, policy: Policy) -> dict:
    data = BusinessInput(**run.input)
    org, key = run.organization_id, task.key
    text, matches = scan(content_for(db, run), policy)
    base = {"execution": "local_rules", "platform_write": False}
    if key in EXTERNAL_STEPS:
        raise Hold(
            "waiting_integration",
            "该平台官方连接器尚未实现，未执行任何外部动作",
            {
                "platform": data.platform,
                "required_adapter": key,
                "authorization": "not_available",
                "platform_write": False,
            },
        )
    if key == "connections":
        return {
            **base,
            "platforms": PLATFORMS,
            "operating_mode": "sandbox",
            "live_ready": False,
            "six_channel_sync_verified": False,
        }
    if key == "governance":
        counts = {
            k: len(records(db, org, k)) for k in ["product", "supplier", "customer", "competitor"]
        }
        if not counts["product"] or not counts["supplier"]:
            raise Hold("waiting_data", "请先导入产品与供应商数据，再重试本步骤", {"counts": counts})
        return {
            **base,
            "counts": counts,
            "sku_rule": "trim + uppercase",
            "currency_rule": "原币金额 × 导入时汇率 = USD；汇率需明确提供",
        }
    if key == "roles":
        return {
            **base,
            "agents": [{"id": a, "name": n, "responsibility": r} for a, n, r in AGENTS],
            "communication": "transactional SQL outbox + Celery group",
            "arbitration": "风控优先；冲突暂停由管理员接管",
            "policy": policy.model_dump(),
        }
    if key == "rules":
        return {
            **base,
            "rules": [r.model_dump() for r in policy.rules],
            "dimensions": [
                "prohibited",
                "intellectual_property",
                "advertising",
                "privacy",
                "customs",
            ],
            "limitation": "内置示例规则不构成完整法规或专利检索；需逐站点维护审核",
            "config_version": run.config_version,
        }
    if key in {"precheck", "listing_check", "marketing_check", "service_check", "trade_check"}:
        if key in {"listing_check", "trade_check"}:
            raise Hold(
                "waiting_review",
                "需人工核验版权/知识产权及目标国法规证据；示例词库不能证明合规",
                {
                    **base,
                    "matches": matches,
                    "sanitized_content": text,
                    "missing_checks": ["知识产权与版权证据", f"{data.country} 税务及清关规则"],
                },
            )
        return {
            **base,
            "matches": matches,
            "sanitized_content": text,
            "scope": "仅检查已配置规则，不代表完整法律合规",
        }
    if key == "market":
        if data.research_collection_id:
            from app.schemas.research import ResearchAnalysis
            from app.services.browser_research import analyze_research

            report = analyze_research(
                db,
                org,
                ResearchAnalysis(
                    collection_id=data.research_collection_id,
                    country=data.country,
                    currency=data.currency,
                    commission_pct=data.commission_pct,
                    ad_rate_pct=data.ad_rate_pct,
                    target_margin_pct=policy.min_margin_pct,
                ),
            )
            if not report["sample_count"]:
                raise Hold("waiting_data", "该采集批次缺少本站点/币种的有效公开竞品证据", report)
            return {
                **base,
                **report,
                "market_score": None,
                "scope": "公开商品页面样本对标；不推断销量与市场需求",
            }
        evidence = records(db, org, "competitor")
        if not evidence:
            raise Hold("waiting_data", "缺少竞品证据，请导入公开授权数据后重试")
        return {
            **base,
            "competitors": [{"key": r.key, "source": r.source, **r.payload} for r in evidence],
            "market_score": data.market_score,
            "scope": "导入数据对标；未爬取平台或社媒，不推断实时趋势",
        }
    if key == "cost":
        return {**base, **costs(data)}
    if key == "evaluate":
        if not data.price or not data.procurement:
            raise Hold(
                "waiting_data",
                "选品需提供大于零的售价和采购报价",
                {
                    "recovery": "new_run_required",
                    "missing": ["price", "procurement"],
                    "next_step": "修订报价后新建任务，保留本次执行与审批记录",
                },
            )
        c = costs(data)
        dimensions = {
            "market": data.market_score,
            "competition": data.competition_score,
            "profit": max(0, min(100, c["margin_pct"] * 2)),
            "supply": data.supply_score,
            "compliance": data.compliance_score,
        }
        score = round(sum(dimensions.values()) / 5, 2)
        output = {
            **base,
            **c,
            "score": score,
            "dimensions": dimensions,
            "weights": "五个维度等权 20%",
            "scores_source": "报价计算及人工输入的评估分",
        }
        if score < policy.selection_min_score or c["margin_pct"] < policy.min_margin_pct:
            raise Hold(
                "rejected",
                "评分或毛利率低于阈值，退回市场调研重新筛选",
                {
                    **output,
                    "return_to": "market",
                    "suggestion": "补充候选品类或修订可验证成本后重新发起选品",
                },
            )
        return output
    if key == "listing_copy":
        # Template fallback is explicit; translate only via configured, verified model tools later.
        return {
            **base,
            "version": 1,
            "title": (text.splitlines()[0] if text else data.sku)[:200],
            "content": text,
            "requested_language": data.language,
            "translation_status": "human_or_model_localization_required",
            "keywords": list(dict.fromkeys(text.split()))[:20],
            "five_bullets": [
                "产品参数待核对",
                "核心卖点待核对",
                "材质与用途待核对",
                "包装与配件待核对",
                "使用限制待核对",
            ],
            "status": "draft",
            "low_risk_corrections": matches,
            "quality_standard": "本地化、事实依据、五点描述及平台字数限制需核验",
        }
    if key in {"stock_plan", "inventory"}:
        target = math.ceil(data.daily_sales * data.lead_days + data.safety_stock)
        return {
            **base,
            "sku": data.sku,
            "stock": data.stock,
            "target_stock": target,
            "replenish_quantity": max(0, target - data.stock),
            "low_stock": data.stock <= data.safety_stock,
            "stock_amount": costs(data)["stock_amount_usd"],
            "marketing_action": "降低投放并核实可售库存"
            if data.stock <= data.safety_stock
            else "维持投放",
            "due_in_hours": 24,
            "owner": "fulfillment",
            "source": "提交的库存与日销快照",
        }
    if key in {"warmup", "marketing_plan"}:
        return {
            **base,
            "currency": data.currency,
            "daily_budget": data.budget_after,
            "channels": {
                "onsite": round(data.budget_after * 0.7, 2),
                "activity": round(data.budget_after * 0.2, 2),
                "offsite": round(data.budget_after * 0.1, 2),
            },
            "budget_change_pct": (
                round((data.budget_after - data.budget_before) / data.budget_before * 100, 2)
                if data.budget_before
                else None
            ),
            "status": "proposal",
            "owner": "marketing",
            "due_in_hours": 24,
        }
    if key == "ad_monitor":
        if data.ad_spend > data.budget_after:
            raise Hold("terminated", "广告消耗快照超过预算，停止本地任务并交管理员处理平台投放")
        return {**base, "spend": data.ad_spend, "budget": data.budget_after}
    if key == "service_context":
        order = next((r for r in records(db, org, "order") if r.key == data.order_key), None)
        return {
            **base,
            "intent": data.service_intent,
            "order_found": order is not None,
            "knowledge": {"sku": data.sku, "tracking_status": data.tracking_status},
            "escalate": not order,
            "timezone": "目标站点工作时段需连接器配置，不自动发送",
        }
    if key == "service_decide":
        return {
            **base,
            "intent": data.service_intent,
            "refund_usd": data.refund_amount * data.exchange_rate_to_usd,
            "reply_draft": "我们已收到您的请求，正在核实订单与物流情况，将尽快提供处理方案。",
            "language": "zh",
            "localization_required": data.language != "zh",
            "status": "draft",
            "responsibility": "需核实订单证据",
            "platform_synced": False,
        }
    if key == "feedback":
        return {
            **base,
            "owner": "selection",
            "sku": data.sku,
            "feedback": text,
            "due_in_hours": 48,
            "status": "improvement_proposal",
        }
    if key == "order_check":
        if not data.order_key or not data.destination_address or not data.sku:
            raise Hold(
                "waiting_data",
                "订单缺少编号、SKU 或目的地址",
                {
                    "recovery": "new_run_required",
                    "missing": ["order_key", "sku", "destination_address"],
                    "next_step": "补齐订单参数后新建任务；原任务输入保持不可变",
                },
            )
        if data.stock < data.quantity:
            raise Hold("waiting_review", "可售库存不足，暂停履约并转人工避免超卖")
        return {
            **base,
            "order_key": data.order_key,
            "inventory_sufficient": True,
            "address_present": True,
            "address_validated": False,
            "scope": "只检查完整性；地址可投递性待官方物流验证",
        }
    if key == "warehouse":
        return {
            **base,
            "order_key": data.order_key,
            "quantity": data.quantity,
            "status": "warehouse_instruction_draft",
            "stock_deducted": False,
            "shipping_label": None,
        }
    if key == "tracking":
        return {
            **base,
            "status": data.tracking_status,
            "exception": data.tracking_status in {"delayed", "lost", "damaged", "customs"},
            "owner": "service",
            "notify_customer": "draft_only",
            "live_tracking": False,
        }
    if key == "aggregate":
        return {**base, **aggregate(db, org)}
    if key == "diagnose":
        metrics = aggregate(db, org)
        issues = []
        if metrics["refund_rate"] is not None and metrics["refund_rate"] > 0.1:
            issues.append(
                {
                    "owner": "service",
                    "issue": "退款率超过诊断参考线 10%",
                    "evidence": metrics["refund_rate"],
                    "cause": "待结合售后原因核实",
                }
            )
        if metrics["gross_margin"] is not None and metrics["gross_margin"] < 0.15:
            issues.append(
                {
                    "owner": "selection",
                    "issue": "毛利率低于诊断参考线 15%",
                    "evidence": metrics["gross_margin"],
                    "cause": "待拆分采购/物流/税费",
                }
            )
        return {
            **base,
            "issues": issues,
            "evidence": metrics["evidence"],
            "conclusion": "相关性诊断；缺少时间序列和渠道归因时不声明根因",
        }
    if key in {"strategy", "handoff"}:
        dependencies = list(db.scalars(select(OpsTask).where(OpsTask.run_id == run.id)))
        return {
            **base,
            "work_orders": [
                {
                    "task_id": t.id,
                    "owner": t.agent,
                    "title": t.title,
                    "output": t.output,
                    "due_in_hours": 48,
                    "quality_standard": "证据、负责人和可追踪的完成记录",
                }
                for t in dependencies
                if t.key in task.dependencies
            ],
            "status": "internal_handoff",
            "external_actions": "须通过对应业务流程的合规与平台门禁",
        }
    raise ValueError(f"没有为步骤 {key} 注册执行工具")
