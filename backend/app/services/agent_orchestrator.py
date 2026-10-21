"""智能体编排器：目标驱动规划 + 波次并行执行 + 反思补采闭环。

对应文档第一到第三阶段的落地形态：

- 规划：自然语言目标解析为串行/波次计划，同波次步骤并行执行；
- 执行：数据汇总与竞品扫描并行 → 诊断 → 方案 → 自检；
- 反思：自检发现证据缺失或竞品覆盖不足时，动态追加补采步骤并重跑
  诊断（最多 MAX_SUPPLEMENT_ROUNDS 轮），而不是强行输出结论；
- 安全：全链路只读。编排器不创建任何 OperationJob、不调用平台写接口，
  高风险建议由诊断引擎标记为人工确认后停在本模块内。
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import (
    AgentRunModel,
    AgentStepModel,
    DiagnosisModel,
    ProductModel,
    ShopModel,
)
from app.db.session import session_scope
from app.schemas.agent import (
    AgentPlanStep,
    AgentRun,
    AgentRunListItem,
    AgentRunStatus,
    AgentRunSummary,
    AgentStep,
    AgentStepKind,
    AgentStepStatus,
    Diagnosis,
    DiagnosisConfidence,
    DiagnosisRiskLevel,
    DiagnosisStatus,
)
from app.services.competitor_repository import DEFAULT_CATEGORY, search_competitors
from app.services.diagnosis_engine import check_data_quality, reflect, run_diagnosis

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_ORG = "org-demo-001"
MAX_SUPPLEMENT_ROUNDS = 1

# 自然语言目标 -> 意图。命中任一意图即纳入计划；全部未命中走默认全流程。
GOAL_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    AgentStepKind.DATA_COLLECT.value: (
        "数据",
        "汇总",
        "拉取",
        "同步",
        "统计",
        "销量",
        "经营",
        "店铺",
    ),
    AgentStepKind.COMPETITOR_SCAN.value: ("竞品", "对标", "对比", "友商", "同行"),
    AgentStepKind.DIAGNOSIS.value: ("诊断", "流量", "转化", "问题", "异常", "风险", "健康", "下滑"),
    AgentStepKind.RECOMMENDATION.value: ("方案", "优化", "建议", "策略", "文案", "改进"),
    AgentStepKind.SELF_CHECK.value: ("自检", "复盘", "校验", "反思", "核查"),
}

STEP_TITLES: dict[str, str] = {
    AgentStepKind.DATA_COLLECT.value: "汇总多店铺经营数据并校验质量",
    AgentStepKind.COMPETITOR_SCAN.value: "检索竞品库并对标定价与卖点",
    AgentStepKind.DIAGNOSIS.value: "运行诊断规则并生成带证据的结论",
    AgentStepKind.RECOMMENDATION.value: "汇总运营优化方案（只读建议）",
    AgentStepKind.SELF_CHECK.value: "反思校验结论证据与信息充足性",
    AgentStepKind.SUPPLEMENT_DATA.value: "补采缺失的经营数据",
    AgentStepKind.SUPPLEMENT_COMPETITOR.value: "扩大竞品检索范围补采对标",
    AgentStepKind.REDIAGNOSIS.value: "基于补采数据重跑诊断",
}

STEP_DEPENDENCIES: dict[str, list[str]] = {
    AgentStepKind.DATA_COLLECT.value: [],
    AgentStepKind.COMPETITOR_SCAN.value: [],
    AgentStepKind.DIAGNOSIS.value: [
        AgentStepKind.DATA_COLLECT.value,
        AgentStepKind.COMPETITOR_SCAN.value,
    ],
    AgentStepKind.RECOMMENDATION.value: [AgentStepKind.DIAGNOSIS.value],
    AgentStepKind.SELF_CHECK.value: [AgentStepKind.RECOMMENDATION.value],
}

STEP_WAVES: dict[str, int] = {
    AgentStepKind.DATA_COLLECT.value: 1,
    AgentStepKind.COMPETITOR_SCAN.value: 1,
    AgentStepKind.DIAGNOSIS.value: 2,
    AgentStepKind.RECOMMENDATION.value: 3,
    AgentStepKind.SELF_CHECK.value: 4,
    AgentStepKind.SUPPLEMENT_DATA.value: 5,
    AgentStepKind.SUPPLEMENT_COMPETITOR.value: 5,
    AgentStepKind.REDIAGNOSIS.value: 6,
}

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def plan_goal(goal: str) -> list[dict]:
    """把自然语言目标解析为带波次的执行计划。"""
    matched = [
        kind
        for kind, keywords in GOAL_INTENT_KEYWORDS.items()
        if any(keyword in goal for keyword in keywords)
    ]
    if not matched:
        matched = [
            AgentStepKind.DATA_COLLECT.value,
            AgentStepKind.COMPETITOR_SCAN.value,
            AgentStepKind.DIAGNOSIS.value,
            AgentStepKind.RECOMMENDATION.value,
        ]
    # 自检复盘是硬约束：无论目标怎么表达，反思闭环必须存在。
    if AgentStepKind.SELF_CHECK.value not in matched:
        matched.append(AgentStepKind.SELF_CHECK.value)
    # 依赖传导：选中诊断就必须有数据；选中方案就必须有诊断与自检。
    if AgentStepKind.DIAGNOSIS.value in matched:
        matched.append(AgentStepKind.DATA_COLLECT.value)
    if AgentStepKind.RECOMMENDATION.value in matched:
        matched.extend(
            [
                AgentStepKind.DIAGNOSIS.value,
                AgentStepKind.DATA_COLLECT.value,
            ]
        )
    ordered: list[str] = []
    for kind in STEP_WAVES:
        if kind in matched and kind not in ordered:
            ordered.append(kind)
    return [
        {
            "kind": kind,
            "title": STEP_TITLES[kind],
            "wave": STEP_WAVES[kind],
            "depends_on": [
                dep for dep in STEP_DEPENDENCIES.get(kind, []) if dep in ordered
            ],
        }
        for kind in ordered
    ]


def create_run(
    db: Session,
    organization_id: str,
    *,
    goal: str,
    shop_ids: list[str] | None = None,
) -> AgentRunModel:
    now = datetime.now(SHANGHAI)
    plan = plan_goal(goal)
    run = AgentRunModel(
        id=f"agent-run-{uuid4().hex[:12]}",
        organization_id=organization_id,
        goal=goal.strip(),
        shop_ids=list(shop_ids) if shop_ids else ["shop-all"],
        status=AgentRunStatus.PLANNING.value,
        plan=plan,
        summary={},
        is_demo=True,
        created_at=now,
        updated_at=now,
    )
    db.add(run)
    for index, step in enumerate(plan, start=1):
        db.add(
            AgentStepModel(
                id=f"agent-step-{uuid4().hex[:12]}",
                run_id=run.id,
                sequence=index,
                wave=step["wave"],
                kind=step["kind"],
                title=step["title"],
                status=AgentStepStatus.PENDING.value,
                created_at=now,
            )
        )
    db.commit()
    return run


# ---------------------------------------------------------------- 步骤处理器


def _handle_data_collect(run: AgentRunModel) -> dict:
    with session_scope() as db:
        statement = select(ProductModel).where(
            ProductModel.organization_id == run.organization_id
        )
        if run.shop_ids != ["shop-all"]:
            statement = statement.where(ProductModel.shop_id.in_(run.shop_ids))
        products = list(db.scalars(statement).all())
        shop_ids = sorted({product.shop_id for product in products})
        shops = (
            list(
                db.scalars(
                    select(ShopModel).where(
                        ShopModel.organization_id == run.organization_id,
                        ShopModel.id.in_(shop_ids),
                    )
                ).all()
            )
            if shop_ids
            else []
        )
    quality = check_data_quality(products)
    return {
        "product_count": len(products),
        "shop_count": len(shops),
        "shop_names": [shop.name for shop in shops],
        "data_source": "live" if any(shop.data_source == "live" for shop in shops) else "seeded",
        "data_quality": quality,
        "_products": products,  # 仅上下文传递，不落库
    }


def _handle_competitor_scan(run: AgentRunModel, context: dict) -> dict:
    """竞品库总览扫描（独立步骤，不依赖数据收集产物）。

    商品级对标检索发生在诊断步骤内，避免同波次步骤间的数据依赖。
    """
    from app.db.models import CompetitorModel

    with session_scope() as db:
        rows = list(
            db.scalars(
                select(CompetitorModel).where(
                    CompetitorModel.organization_id == run.organization_id
                )
            ).all()
        )
    categories: dict[str, int] = {}
    for row in rows:
        categories[row.category] = categories.get(row.category, 0) + 1
    latest = max((row.updated_at for row in rows), default=None)
    return {
        "competitor_count": len(rows),
        "categories": categories,
        "latest_updated_at": latest.isoformat() if latest else None,
    }


def _match_competitors(run: AgentRunModel, products: list[ProductModel]) -> dict[str, list[dict]]:
    """按商品标题检索对标竞品。诊断与补采共用。"""
    competitor_map: dict[str, list[dict]] = {}
    with session_scope() as db:
        for product in products:
            competitor_map[product.id] = search_competitors(
                db,
                query_texts=[product.title],
                category=DEFAULT_CATEGORY,
                organization_id=run.organization_id,
                limit=3,
            )
    return competitor_map


def _handle_diagnosis(run: AgentRunModel, context: dict) -> dict:
    products: list[ProductModel] = context["products"]
    competitor_map = _match_competitors(run, products)
    context["competitor_map"] = competitor_map
    shop_scope = None if run.shop_ids == ["shop-all"] else set(run.shop_ids)
    drafts = run_diagnosis(products, competitor_map, shop_scope=shop_scope)
    context["drafts"] = drafts
    by_severity = {key: 0 for key in SEVERITY_ORDER}
    for draft in drafts:
        by_severity[draft["severity"]] = by_severity.get(draft["severity"], 0) + 1
    matched = sum(1 for items in competitor_map.values() if items)
    top_gaps = sorted(
        (
            {
                "title": next(p.title for p in products if p.id == product_id),
                "cheapest_competitor": items[0]["title"],
                "competitor_price": items[0]["price"],
                "own_price": next(p.price for p in products if p.id == product_id),
                "similarity": items[0].get("similarity", 0),
            }
            for product_id, items in competitor_map.items()
            if items
        ),
        key=lambda item: item["competitor_price"] - item["own_price"],
    )[:5]
    return {
        "drafts_total": len(drafts),
        "by_severity": by_severity,
        "competitor_matched_products": matched,
        "top_gaps": top_gaps,
    }


def _handle_recommendation(context: dict) -> dict:
    drafts: list[dict] = context.get("drafts", [])
    ordered = sorted(drafts, key=lambda item: SEVERITY_ORDER.get(item["severity"], 3))
    actions = [
        {
            "title": draft["title"],
            "severity": draft["severity"],
            "action": draft["recommendation"],
            "risk_level": draft["risk_level"],
        }
        for draft in ordered
    ]
    return {
        "actions_total": len(actions),
        "high_risk_actions": sum(1 for item in actions if item["risk_level"] == "high"),
        "actions": actions,
    }


def _handle_self_check(run: AgentRunModel, context: dict) -> dict:
    drafts: list[dict] = context.get("drafts", [])
    data_quality: dict = context.get("data_quality", {})
    competitor_map: dict[str, list[dict]] = context.get("competitor_map", {})
    competitor_coverage = {
        product_id: len(items) for product_id, items in competitor_map.items()
    }
    result = reflect(drafts, data_quality=data_quality, competitor_coverage=competitor_coverage)
    context["kept"] = result["kept"]
    context["supplement"] = result["supplement"]
    return {
        "kept": len(result["kept"]),
        "discarded": len(result["discarded"]),
        "discarded_detail": result["discarded"],
        "notes": result["notes"],
        "supplement": result["supplement"],
    }


def _handle_supplement_competitor(run: AgentRunModel, context: dict) -> dict:
    # 补采 = 扩大召回：更高 limit + 更低相似度门槛，重新检索竞品库。
    products: list[ProductModel] = context["products"]
    competitor_map: dict[str, list[dict]] = {}
    with session_scope() as db:
        for product in products:
            competitor_map[product.id] = search_competitors(
                db,
                query_texts=[product.title],
                category=DEFAULT_CATEGORY,
                organization_id=run.organization_id,
                limit=8,
                min_similarity=0.01,
            )
    context["competitor_map"] = competitor_map
    matched = sum(1 for items in competitor_map.values() if items)
    return {"competitor_matched_products": matched, "search_limit": 8}


# ---------------------------------------------------------------- 执行主循环


def _mark_step(
    db: Session, step: AgentStepModel, status: AgentStepStatus, **fields: object
) -> None:
    step.status = status.value
    for key, value in fields.items():
        setattr(step, key, value)
    db.commit()


def _execute_wave(
    db: Session, run: AgentRunModel, steps: list[AgentStepModel], context: dict
) -> bool:
    """执行同一波次的步骤（并行）。返回是否全部成功。"""
    now = datetime.now(SHANGHAI)

    async def _runner(step: AgentStepModel) -> dict:
        started = time.monotonic()
        _mark_step(db, step, AgentStepStatus.RUNNING, started_at=now)
        try:
            output = await asyncio.to_thread(_dispatch, run, step, context)
        except Exception as exc:  # noqa: BLE001 - 步骤失败必须落库后继续
            duration_ms = int((time.monotonic() - started) * 1000)
            _mark_step(
                db,
                step,
                AgentStepStatus.FAILED,
                error_message=str(exc)[:500],
                completed_at=datetime.now(SHANGHAI),
                duration_ms=duration_ms,
            )
            raise
        duration_ms = int((time.monotonic() - started) * 1000)
        # _products 是内存对象，不能进 JSON 列
        output = {key: value for key, value in output.items() if not key.startswith("_")}
        _mark_step(
            db,
            step,
            AgentStepStatus.SUCCEEDED,
            output=output,
            completed_at=datetime.now(SHANGHAI),
            duration_ms=duration_ms,
        )
        return output

    async def _gather() -> list:
        # return_exceptions=True：确保同波次所有步骤都落终态，
        # 不会因一个失败把其它步骤留在 running。
        return await asyncio.gather(
            *(_runner(step) for step in steps), return_exceptions=True
        )

    results = asyncio.run(_gather())
    return all(not isinstance(item, Exception) for item in results)


def _dispatch(run: AgentRunModel, step: AgentStepModel, context: dict) -> dict:
    kind = step.kind
    if kind == AgentStepKind.DATA_COLLECT.value:
        output = _handle_data_collect(run)
        context["products"] = output.pop("_products")
        context["data_quality"] = output["data_quality"]
        return output
    if kind == AgentStepKind.COMPETITOR_SCAN.value:
        return _handle_competitor_scan(run, context)
    if kind == AgentStepKind.DIAGNOSIS.value:
        return _handle_diagnosis(run, context)
    if kind == AgentStepKind.RECOMMENDATION.value:
        return _handle_recommendation(context)
    if kind == AgentStepKind.SELF_CHECK.value:
        return _handle_self_check(run, context)
    if kind == AgentStepKind.SUPPLEMENT_COMPETITOR.value:
        return _handle_supplement_competitor(run, context)
    if kind == AgentStepKind.SUPPLEMENT_DATA.value:
        output = _handle_data_collect(run)
        context["products"] = output.pop("_products")
        context["data_quality"] = output["data_quality"]
        return output
    if kind == AgentStepKind.REDIAGNOSIS.value:
        # 补采后重跑诊断并再次反思，保证最终结论基于最新数据
        diagnosis_output = _handle_diagnosis(run, context)
        reflect_output = _handle_self_check(run, context)
        return {**diagnosis_output, "reflection": reflect_output}
    raise ValueError(f"未知步骤类型：{kind}")


def _create_dynamic_step(
    db: Session, run: AgentRunModel, kind: AgentStepKind, sequence: int
) -> AgentStepModel:
    now = datetime.now(SHANGHAI)
    step = AgentStepModel(
        id=f"agent-step-{uuid4().hex[:12]}",
        run_id=run.id,
        sequence=sequence,
        wave=STEP_WAVES[kind.value],
        kind=kind.value,
        title=STEP_TITLES[kind.value],
        status=AgentStepStatus.PENDING.value,
        created_at=now,
    )
    db.add(step)
    db.commit()
    plan = list(run.plan)
    plan.append(
        {
            "kind": kind.value,
            "title": STEP_TITLES[kind.value],
            "wave": STEP_WAVES[kind.value],
            "depends_on": [AgentStepKind.SELF_CHECK.value],
        }
    )
    run.plan = plan
    db.commit()
    return step


def _persist_diagnoses(db: Session, run: AgentRunModel, kept: list[dict]) -> list[DiagnosisModel]:
    now = datetime.now(SHANGHAI)
    models = []
    for draft in kept:
        model = DiagnosisModel(
            id=f"diagnosis-{uuid4().hex[:12]}",
            run_id=run.id,
            organization_id=run.organization_id,
            shop_id=draft.get("shop_id") or "shop-all",
            shop_name=draft.get("shop_name") or "全部店铺",
            product_id=draft.get("product_id"),
            kind=draft["kind"],
            severity=draft["severity"],
            title=draft["title"],
            detail=draft["detail"],
            evidence=draft["evidence"],
            confidence=draft.get("confidence", "high"),
            recommendation=draft["recommendation"],
            risk_level=draft.get("risk_level", "low"),
            status=draft.get("status", "pending"),
            is_demo=True,
            created_at=now,
        )
        db.add(model)
        models.append(model)
    db.commit()
    return models


def execute_run(run_id: str) -> str:
    """执行一次智能体运行。返回终态（succeeded / failed）。"""
    with session_scope() as db:
        run = db.get(AgentRunModel, run_id)
        if run is None:
            return AgentRunStatus.FAILED.value
        run.status = AgentRunStatus.RUNNING.value
        run.started_at = datetime.now(SHANGHAI)
        run.updated_at = datetime.now(SHANGHAI)
        db.commit()

        context: dict = {}
        supplement_rounds = 0
        try:
            # 计划内步骤按波次分组执行（同波次并行）
            steps = list(
                db.scalars(
                    select(AgentStepModel)
                    .where(AgentStepModel.run_id == run.id)
                    .order_by(AgentStepModel.sequence)
                ).all()
            )
            waves: dict[int, list[AgentStepModel]] = {}
            for step in steps:
                waves.setdefault(step.wave, []).append(step)

            for wave in sorted(waves):
                ok = _execute_wave(db, run, waves[wave], context)
                if not ok:
                    raise RuntimeError(f"第 {wave} 波次存在失败步骤，运行中止")

            # 反思闭环：信息不足时补采并重跑，最多 MAX_SUPPLEMENT_ROUNDS 轮
            while supplement_rounds < MAX_SUPPLEMENT_ROUNDS:
                supplement = context.get("supplement", {})
                if not (supplement.get("data") or supplement.get("competitor")):
                    break
                supplement_rounds += 1
                next_sequence = max(step.sequence for step in steps) + 1
                dynamic_kinds = []
                if supplement.get("competitor"):
                    dynamic_kinds.append(AgentStepKind.SUPPLEMENT_COMPETITOR)
                if supplement.get("data"):
                    dynamic_kinds.append(AgentStepKind.SUPPLEMENT_DATA)
                dynamic_kinds.append(AgentStepKind.REDIAGNOSIS)
                dynamic_steps = [
                    _create_dynamic_step(db, run, kind, next_sequence + index)
                    for index, kind in enumerate(dynamic_kinds)
                ]
                # 补采步骤并行，重跑诊断依赖补采结果故单独一波
                by_wave: dict[int, list[AgentStepModel]] = {}
                for step in dynamic_steps:
                    by_wave.setdefault(step.wave, []).append(step)
                for wave in sorted(by_wave):
                    if not _execute_wave(db, run, by_wave[wave], context):
                        raise RuntimeError(f"补采第 {wave} 波次存在失败步骤，运行中止")
                steps.extend(dynamic_steps)

            kept: list[dict] = context.get("kept", [])
            discarded_count = 0
            self_check_steps = [
                step
                for step in db.scalars(
                    select(AgentStepModel).where(
                        AgentStepModel.run_id == run.id,
                        AgentStepModel.kind == AgentStepKind.SELF_CHECK.value,
                    )
                ).all()
            ]
            if self_check_steps:
                discarded_count = int(self_check_steps[-1].output.get("discarded", 0))
            _persist_diagnoses(db, run, kept)

            all_steps = list(
                db.scalars(
                    select(AgentStepModel).where(AgentStepModel.run_id == run.id)
                ).all()
            )
            notes: list[str] = []
            for step in all_steps:
                if step.kind == AgentStepKind.SELF_CHECK.value:
                    notes.extend(step.output.get("notes", []))
            run.summary = AgentRunSummary(
                steps_total=len(all_steps),
                steps_succeeded=sum(
                    1 for step in all_steps if step.status == AgentStepStatus.SUCCEEDED.value
                ),
                diagnoses_total=len(kept),
                discarded_conclusions=discarded_count,
                supplement_rounds=supplement_rounds,
                high_risk_pending=sum(
                    1 for draft in kept if draft.get("risk_level") == "high"
                ),
                reflection_notes=notes,
            ).model_dump(mode="json")
            run.status = AgentRunStatus.SUCCEEDED.value
            run.completed_at = datetime.now(SHANGHAI)
            run.updated_at = run.completed_at
            db.commit()
            return AgentRunStatus.SUCCEEDED.value
        except Exception as exc:  # noqa: BLE001 - 运行失败必须落库
            run.status = AgentRunStatus.FAILED.value
            run.error_message = str(exc)[:500]
            run.completed_at = datetime.now(SHANGHAI)
            run.updated_at = run.completed_at
            db.commit()
            return AgentRunStatus.FAILED.value


# ---------------------------------------------------------------- 查询与决策


def _step_payload(model: AgentStepModel) -> AgentStep:
    return AgentStep(
        id=model.id,
        run_id=model.run_id,
        sequence=model.sequence,
        wave=model.wave,
        kind=AgentStepKind(model.kind),
        title=model.title,
        status=AgentStepStatus(model.status),
        input=model.input,
        output=model.output,
        error_message=model.error_message,
        duration_ms=model.duration_ms,
        created_at=model.created_at,
        started_at=model.started_at,
        completed_at=model.completed_at,
    )


def _diagnosis_payload(model: DiagnosisModel) -> Diagnosis:
    return Diagnosis(
        id=model.id,
        run_id=model.run_id,
        shop_id=model.shop_id,
        shop_name=model.shop_name,
        product_id=model.product_id,
        kind=model.kind,
        severity=model.severity,
        title=model.title,
        detail=model.detail,
        evidence=model.evidence,
        confidence=DiagnosisConfidence(model.confidence),
        recommendation=model.recommendation,
        risk_level=DiagnosisRiskLevel(model.risk_level),
        status=DiagnosisStatus(model.status),
        decided_by=model.decided_by,
        decision_note=model.decision_note,
        decided_at=model.decided_at,
        is_demo=model.is_demo,
        created_at=model.created_at,
    )


def get_run(db: Session, run_id: str) -> AgentRun | None:
    # expire_all：eager 任务在本 session 之外同步写完了运行状态，
    # 不清缓存的话 identity map 会返回创建时的 planning 旧值。
    db.expire_all()
    run = db.get(AgentRunModel, run_id)
    if run is None:
        return None
    steps = list(
        db.scalars(
            select(AgentStepModel)
            .where(AgentStepModel.run_id == run.id)
            .order_by(AgentStepModel.sequence)
        ).all()
    )
    diagnoses = list(
        db.scalars(
            select(DiagnosisModel)
            .where(DiagnosisModel.run_id == run.id)
            .order_by(DiagnosisModel.created_at)
        ).all()
    )
    return AgentRun(
        id=run.id,
        goal=run.goal,
        shop_ids=list(run.shop_ids),
        status=AgentRunStatus(run.status),
        plan=[AgentPlanStep(**item) for item in run.plan],
        summary=AgentRunSummary(**run.summary) if run.summary else AgentRunSummary(),
        steps=[_step_payload(step) for step in steps],
        diagnoses=[_diagnosis_payload(item) for item in diagnoses],
        error_message=run.error_message,
        is_demo=run.is_demo,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def list_runs(db: Session, organization_id: str, limit: int = 20) -> list[AgentRunListItem]:
    runs = list(
        db.scalars(
            select(AgentRunModel)
            .where(AgentRunModel.organization_id == organization_id)
            .order_by(desc(AgentRunModel.created_at))
            .limit(limit)
        ).all()
    )
    items = []
    for run in runs:
        diagnoses = list(
            db.scalars(select(DiagnosisModel).where(DiagnosisModel.run_id == run.id)).all()
        )
        items.append(
            AgentRunListItem(
                id=run.id,
                goal=run.goal,
                status=AgentRunStatus(run.status),
                shop_ids=list(run.shop_ids),
                diagnoses_total=len(diagnoses),
                high_risk_pending=sum(
                    1
                    for item in diagnoses
                    if item.risk_level == "high" and item.status == "pending"
                ),
                created_at=run.created_at,
                completed_at=run.completed_at,
                is_demo=run.is_demo,
            )
        )
    return items


def decide_diagnosis(
    db: Session,
    organization_id: str,
    diagnosis_id: str,
    *,
    decision: str,
    note: str | None,
    actor: str,
) -> Diagnosis | None:
    """人工确认或驳回一条高风险结论。

    这是写操作建议进入后续流程的唯一入口；确认动作本身只记录决策，
    仍然不触发任何平台写入。
    """
    model = db.get(DiagnosisModel, diagnosis_id)
    if model is None or model.organization_id != organization_id:
        return None
    if model.status != DiagnosisStatus.PENDING.value:
        raise ValueError("该结论已完成人工决策，不能重复操作")
    now = datetime.now(SHANGHAI)
    model.status = (
        DiagnosisStatus.APPROVED.value if decision == "approve" else DiagnosisStatus.REJECTED.value
    )
    model.decided_by = actor
    model.decision_note = note
    model.decided_at = now
    db.commit()
    return _diagnosis_payload(model)
