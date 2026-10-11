from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import (
    AutomationRuleModel,
    AutomationRunModel,
    AutomationTaskModel,
    ProductModel,
)
from app.schemas.automation import (
    AutomationMatch,
    AutomationMode,
    AutomationOverview,
    AutomationRule,
    AutomationRuleType,
    AutomationRun,
    AutomationRunRequest,
    AutomationRunStatus,
    AutomationTask,
    AutomationTaskStatus,
)
from app.services.order_repository import ORDERS

SHANGHAI = ZoneInfo("Asia/Shanghai")
DATA_UPDATED_AT = datetime(2026, 9, 12, 13, 10, tzinfo=SHANGHAI)
DEFAULT_ORG = "org-demo-001"

DEFAULT_RULES = (
    {
        "name": "售后时效预警",
        "rule_type": AutomationRuleType.AFTER_SALE_SLA,
        "description": "发现 2 小时内需要处理的售后订单，创建待确认任务。",
        "mode": AutomationMode.APPROVAL_REQUIRED,
        "config": {"threshold_minutes": 120},
    },
    {
        "name": "库存安全线巡检",
        "rule_type": AutomationRuleType.INVENTORY_LOW,
        "description": "发现库存低于安全线的商品，生成补货建议，不直接改库存。",
        "mode": AutomationMode.SUGGEST,
        "config": {"stock_threshold": 25},
    },
    {
        "name": "商品质量异常",
        "rule_type": AutomationRuleType.PRODUCT_QUALITY,
        "description": "发现下架、草稿或带有风险标签的商品，生成整改任务。",
        "mode": AutomationMode.APPROVAL_REQUIRED,
        "config": {"include_warning": True},
    },
)


def _rule(model: AutomationRuleModel) -> AutomationRule:
    return AutomationRule(
        id=model.id,
        name=model.name,
        rule_type=AutomationRuleType(model.rule_type),
        description=model.description,
        mode=AutomationMode(model.mode),
        config=model.config,
        is_enabled=model.is_enabled,
        last_run_at=model.last_run_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
        is_demo=model.is_demo,
    )


def _run(model: AutomationRunModel, rule_name: str) -> AutomationRun:
    return AutomationRun(
        id=model.id,
        rule_id=model.rule_id,
        rule_name=rule_name,
        status=AutomationRunStatus(model.status),
        matched_count=model.matched_count,
        task_count=model.task_count,
        results=[AutomationMatch.model_validate(item) for item in model.results],
        error_message=model.error_message,
        created_at=model.created_at,
        completed_at=model.completed_at,
        is_demo=model.is_demo,
    )


def _task(model: AutomationTaskModel) -> AutomationTask:
    return AutomationTask(
        id=model.id,
        run_id=model.run_id,
        rule_id=model.rule_id,
        entity_id=model.entity_id,
        entity_type=model.entity_type,
        reference=model.reference,
        title=model.title,
        severity=model.severity,
        reason=model.reason,
        suggested_action=model.suggested_action,
        status=AutomationTaskStatus(model.status),
        assignee=model.assignee,
        due_at=model.due_at,
        completed_at=model.completed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
        is_demo=model.is_demo,
    )


def _ensure_default_rules(db: Session, organization_id: str) -> list[AutomationRuleModel]:
    existing = list(
        db.scalars(
            select(AutomationRuleModel).where(
                AutomationRuleModel.organization_id == organization_id
            )
        )
    )
    known = {item.rule_type for item in existing}
    now = datetime.now(SHANGHAI)
    for definition in DEFAULT_RULES:
        rule_type = definition["rule_type"].value
        if rule_type in known:
            continue
        model = AutomationRuleModel(
            id=f"automation-rule-{uuid4().hex[:10]}",
            organization_id=organization_id,
            name=definition["name"],
            rule_type=rule_type,
            description=definition["description"],
            mode=definition["mode"].value,
            config=definition["config"],
            is_enabled=True,
            created_at=now,
            updated_at=now,
            is_demo=True,
        )
        db.add(model)
        existing.append(model)
    if len(existing) != len(known):
        db.commit()
    return sorted(existing, key=lambda item: item.created_at)


def _matches(db: Session, rule: AutomationRuleModel) -> list[AutomationMatch]:
    if rule.rule_type == AutomationRuleType.AFTER_SALE_SLA.value:
        threshold = int(rule.config.get("threshold_minutes", 120))
        return [
            AutomationMatch(
                entity_id=item.id,
                entity_type="order",
                reference=item.order_no,
                title=item.item_title,
                severity=item.risk.value,
                reason=(
                    f"售后状态为 {item.after_sale_status.value}，剩余 "
                    f"{item.remaining_minutes} 分钟"
                ),
                suggested_action="创建售后处理任务并由运营确认回复或处置动作",
            )
            for item in ORDERS
            if item.after_sale_status.value in {"requested", "merchant_processing"}
            and item.remaining_minutes is not None
            and item.remaining_minutes <= threshold
        ]
    products = db.scalars(
        select(ProductModel).where(ProductModel.organization_id == DEFAULT_ORG)
    ).all()
    if rule.rule_type == AutomationRuleType.INVENTORY_LOW.value:
        threshold = int(rule.config.get("stock_threshold", 25))
        return [
            AutomationMatch(
                entity_id=item.id,
                entity_type="product",
                reference=item.sku,
                title=item.title,
                severity=item.risk,
                reason=f"当前库存 {item.stock} 件，低于安全线 {threshold} 件",
                suggested_action="创建补货建议并核对近 7 日销量，不直接修改线上库存",
            )
            for item in products
            if item.stock <= threshold
        ]
    include_warning = bool(rule.config.get("include_warning", True))
    return [
        AutomationMatch(
            entity_id=item.id,
            entity_type="product",
            reference=item.sku,
            title=item.title,
            severity=item.risk,
            reason="；".join(item.risk_labels) or f"商品状态为 {item.status}",
            suggested_action="创建商品整改任务，确认后再执行上下架或内容修正",
        )
        for item in products
        if item.status in {"offline", "draft"}
        or bool(item.risk_labels and (include_warning or item.risk == "critical"))
    ]


def list_overview(db: Session, organization_id: str) -> AutomationOverview:
    rules = _ensure_default_rules(db, organization_id)
    rule_names = {rule.id: rule.name for rule in rules}
    runs = db.scalars(
        select(AutomationRunModel)
        .where(AutomationRunModel.organization_id == organization_id)
        .order_by(desc(AutomationRunModel.created_at))
        .limit(20)
    )
    tasks = db.scalars(
        select(AutomationTaskModel)
        .where(AutomationTaskModel.organization_id == organization_id)
        .order_by(desc(AutomationTaskModel.created_at))
        .limit(50)
    )
    return AutomationOverview(
        rules=[_rule(rule) for rule in rules],
        runs=[_run(run, rule_names.get(run.rule_id, "自动化规则")) for run in runs],
        tasks=[_task(task) for task in tasks],
        data_updated_at=DATA_UPDATED_AT,
    )


def update_rule(
    db: Session, organization_id: str, rule_id: str, payload: dict[str, object]
) -> AutomationRule | None:
    rule = db.scalar(
        select(AutomationRuleModel).where(
            AutomationRuleModel.id == rule_id,
            AutomationRuleModel.organization_id == organization_id,
        )
    )
    if rule is None:
        return None
    if payload.get("is_enabled") is not None:
        rule.is_enabled = bool(payload["is_enabled"])
    if payload.get("mode") is not None:
        rule.mode = str(payload["mode"])
    if payload.get("config") is not None:
        rule.config = dict(payload["config"])  # type: ignore[arg-type]
    rule.updated_at = datetime.now(SHANGHAI)
    db.commit()
    return _rule(rule)


def update_task(
    db: Session,
    organization_id: str,
    task_id: str,
    payload: dict[str, object],
) -> AutomationTask | None:
    task = db.scalar(
        select(AutomationTaskModel).where(
            AutomationTaskModel.id == task_id,
            AutomationTaskModel.organization_id == organization_id,
        )
    )
    if task is None:
        return None

    now = datetime.now(SHANGHAI)
    if payload.get("status") is not None:
        task.status = str(payload["status"])
        task.completed_at = (
            now
            if task.status
            in {AutomationTaskStatus.COMPLETED.value, AutomationTaskStatus.DISMISSED.value}
            else None
        )
    if "assignee" in payload:
        task.assignee = str(payload["assignee"]) if payload["assignee"] else None
    task.updated_at = now
    db.commit()
    return _task(task)


def run_rule(
    db: Session,
    organization_id: str,
    rule_id: str,
    request: AutomationRunRequest,
) -> AutomationRun | None:
    rule = db.scalar(
        select(AutomationRuleModel).where(
            AutomationRuleModel.id == rule_id,
            AutomationRuleModel.organization_id == organization_id,
        )
    )
    if rule is None:
        return None
    if not rule.is_enabled:
        raise ValueError("规则已暂停，请先启用后再运行")
    if not request.confirm:
        raise ValueError("请确认扫描当前规则范围")
    if rule.mode == AutomationMode.AUTO.value:
        raise ValueError("演示数据不允许自动执行，请先使用建议或人工确认模式")
    now = datetime.now(SHANGHAI)
    matches = _matches(db, rule)
    run = AutomationRunModel(
        id=f"automation-run-{uuid4().hex[:10]}",
        organization_id=organization_id,
        rule_id=rule.id,
        status=AutomationRunStatus.SUCCEEDED.value,
        matched_count=len(matches),
        task_count=len(matches),
        results=[],
        created_at=now,
        completed_at=now,
        is_demo=True,
    )
    rule.last_run_at = now
    rule.updated_at = now
    db.add(run)
    db.flush()

    task_matches: list[AutomationMatch] = []
    for match in matches:
        dedupe_key = f"{rule.id}:{match.entity_id}:{now.date().isoformat()}"
        task = db.scalar(
            select(AutomationTaskModel).where(
                AutomationTaskModel.organization_id == organization_id,
                AutomationTaskModel.dedupe_key == dedupe_key,
            )
        )
        if task is None:
            due_at = next(
                (
                    item.sla_deadline
                    for item in ORDERS
                    if item.id == match.entity_id and item.sla_deadline is not None
                ),
                None,
            )
            task = AutomationTaskModel(
                id=f"automation-task-{uuid4().hex[:10]}",
                organization_id=organization_id,
                run_id=run.id,
                rule_id=rule.id,
                dedupe_key=dedupe_key,
                entity_id=match.entity_id,
                entity_type=match.entity_type,
                reference=match.reference,
                title=match.title,
                severity=match.severity,
                reason=match.reason,
                suggested_action=match.suggested_action,
                status=AutomationTaskStatus.PENDING.value,
                due_at=due_at,
                created_at=now,
                updated_at=now,
                is_demo=True,
            )
            db.add(task)
        else:
            task.run_id = run.id
            task.reason = match.reason
            task.suggested_action = match.suggested_action
            task.updated_at = now
        task_matches.append(match.model_copy(update={"task_id": task.id}))

    run.task_count = len(task_matches)
    run.results = [item.model_dump(mode="json") for item in task_matches]
    db.commit()
    return _run(run, rule.name)
