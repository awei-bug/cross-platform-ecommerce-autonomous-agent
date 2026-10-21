"""Transactional event bus, DAG scheduler and layered authorization.

Database events are the durable source; Celery is only the delivery mechanism.
No external action is substituted with a simulated success.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.ecomops import OpsAudit, OpsConfiguration, OpsEvent, OpsRecord, OpsRun, OpsTask
from app.db.models import AlertModel
from app.db.session import session_scope
from app.schemas.ecomops import BusinessInput, ImportRequest, Intervention, Policy, RunCreate
from app.services.ecomops_ai import enrich
from app.services.ecomops_catalog import (
    AGENTS,
    EXTERNAL_STEPS,
    PLATFORMS,
    RETIRED_WORKFLOWS,
    WORKFLOWS,
)
from app.services.ecomops_specialists import Hold, content_for, costs, execute_tool, scan


def now() -> datetime:
    return datetime.now(UTC)


def uid() -> str:
    return uuid4().hex


def audit(
    db: Session, org: str, actor: str, action: str, note: str, run_id: str | None = None
) -> None:
    db.add(
        OpsAudit(
            id=uid(),
            organization_id=org,
            actor=actor,
            action=action,
            note=note,
            run_id=run_id,
            created_at=now(),
        )
    )


def configuration(db: Session, org: str) -> OpsConfiguration:
    row = db.get(OpsConfiguration, org)
    if row is None:
        row = OpsConfiguration(
            organization_id=org, version=1, payload=Policy().model_dump(), updated_at=now()
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = db.get(OpsConfiguration, org)
    return row


def update_configuration(db: Session, org: str, actor: str, version: int, policy: Policy):
    configuration(db, org)
    result = db.execute(
        update(OpsConfiguration)
        .where(
            OpsConfiguration.organization_id == org,
            OpsConfiguration.version == version,
        )
        .values(version=version + 1, payload=policy.model_dump(), updated_at=now())
    )
    if result.rowcount != 1:
        db.rollback()
        raise ValueError("规则版本已变化，请刷新后重新保存")
    audit(db, org, actor, "policy_update", f"规则版本 {version} → {version + 1}")
    db.commit()
    db.expire_all()
    return configuration(db, org)


def event(
    db: Session, run: OpsRun, topic: str, task_id: str | None = None, payload: dict | None = None
) -> None:
    db.add(
        OpsEvent(
            id=uid(),
            organization_id=run.organization_id,
            run_id=run.id,
            task_id=task_id,
            topic=topic,
            status="pending",
            payload=payload or {},
            created_at=now(),
        )
    )


def get_run(db: Session, org: str, run_id: str) -> OpsRun:
    row = db.get(OpsRun, run_id)
    if row is None or row.organization_id != org:
        raise LookupError("任务不存在")
    return row


def tasks_for(db: Session, run_id: str) -> list[OpsTask]:
    return list(db.scalars(select(OpsTask).where(OpsTask.run_id == run_id).order_by(OpsTask.id)))


def create_run(db: Session, org: str, actor: str, payload: RunCreate) -> OpsRun:
    previous = db.scalar(
        select(OpsRun).where(
            OpsRun.organization_id == org,
            OpsRun.idempotency_key == payload.idempotency_key,
        )
    )
    if previous:
        if (
            previous.workflow != payload.workflow
            or previous.input != payload.input.model_dump()
            or previous.title != payload.title
        ):
            raise ValueError("幂等键已用于其他请求，请使用新的幂等键")
        return previous
    config = configuration(db, org)
    run = OpsRun(
        id=uid(),
        organization_id=org,
        workflow=payload.workflow,
        title=payload.title,
        status="queued",
        priority=payload.priority,
        input=payload.input.model_dump(),
        idempotency_key=payload.idempotency_key,
        config_version=config.version,
        created_at=now(),
        updated_at=now(),
    )
    db.add(run)
    for position, (key, agent, title, deps) in enumerate(WORKFLOWS[payload.workflow][1]):
        db.add(
            OpsTask(
                id=f"{run.id}-{position:02}",
                run_id=run.id,
                organization_id=org,
                key=key,
                agent=agent,
                title=title,
                dependencies=deps,
                status="pending",
                output={},
                reason="",
                risk="none",
                attempts=0,
            )
        )
    event(db, run, "workflow.created")
    audit(db, org, actor, "create", payload.title, run.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = db.scalar(
            select(OpsRun).where(
                OpsRun.organization_id == org,
                OpsRun.idempotency_key == payload.idempotency_key,
            )
        )
        if not previous:
            raise
        if previous.input != payload.input.model_dump() or previous.workflow != payload.workflow:
            raise ValueError("幂等请求冲突") from None
        return previous
    return run


def summarize(db: Session, run: OpsRun) -> None:
    if run.status in {"cancelled", "terminated", "taken_over", "rejected"}:
        return
    tasks = tasks_for(db, run.id)
    states = {t.status for t in tasks}
    if states == {"succeeded"}:
        target = "succeeded"
    else:
        target = next(
            (
                s
                for s in [
                    "dead_letter",
                    "failed",
                    "waiting_review",
                    "waiting_integration",
                    "waiting_data",
                    "running",
                    "queued",
                ]
                if s in states
            ),
            "running",
        )
    set_active_state(db, run, target)


def set_active_state(db: Session, run: OpsRun, target: str) -> None:
    # Never overwrite another worker's emergency stop or human takeover.
    db.execute(
        update(OpsRun)
        .where(
            OpsRun.id == run.id,
            OpsRun.status.not_in(["cancelled", "terminated", "taken_over", "rejected"]),
        )
        .values(status=target, updated_at=now())
        .execution_options(synchronize_session=False)
    )
    db.refresh(run)


def risk_gate(db: Session, run: OpsRun, task: OpsTask, policy: Policy, version: int) -> None:
    data = BusinessInput(**run.input)
    _, matches = scan(content_for(db, run), policy)
    high = [r for r in matches if r["level"] == "high"]
    if high:
        raise Hold("terminated", "高风险规则命中，立即终止并要求管理员处理", {"rules": high})
    if run.workflow == "marketing" and data.ad_spend > data.budget_after:
        raise Hold("terminated", "广告消耗快照已超过预算，停止本地任务并告警；请人工处理平台投放")
    reasons = []
    facts = [
        {"label": "业务对象", "value": data.order_key or data.sku or "未提供"},
        {"label": "平台 / 站点", "value": f"{data.platform} / {data.country}"},
        {"label": "规则版本", "value": version},
    ]
    if any(r["level"] == "medium" for r in matches):
        reasons.append("疑似侵权或宣传违规，需人工核验")
    if task.key == "evaluate" and costs(data)["stock_amount_usd"] > policy.stock_amount_limit:
        reasons.append("单款备货金额超过 USD 权限阈值")
        amount = costs(data)["stock_amount_usd"]
        facts.extend(
            [
                {"label": "采购单价（原币）", "value": f"{data.procurement} {data.currency}"},
                {"label": "备货数量", "value": data.quantity},
                {"label": "备货金额 USD", "value": amount},
                {"label": "备货阈值 USD", "value": policy.stock_amount_limit},
                {"label": "超出金额 USD", "value": round(amount - policy.stock_amount_limit, 2)},
            ]
        )
    if task.key in {"marketing_plan", "warmup", "ad_execute"}:
        if (not data.budget_before and data.budget_after > 0) or (
            data.budget_before
            and abs(data.budget_after - data.budget_before) / data.budget_before * 100
            > policy.budget_change_limit_pct
        ):
            reasons.append("单日预算调整幅度超过授权阈值")
            change = (
                round(abs(data.budget_after - data.budget_before) / data.budget_before * 100, 2)
                if data.budget_before
                else "零基数新增预算"
            )
            facts.extend(
                [
                    {"label": "原日预算", "value": f"{data.budget_before} {data.currency}"},
                    {"label": "拟调整日预算", "value": f"{data.budget_after} {data.currency}"},
                    {"label": "变动幅度 %", "value": change},
                    {"label": "允许变动 %", "value": policy.budget_change_limit_pct},
                ]
            )
    if task.key in {"service_decide", "service_execute"}:
        if (
            data.service_intent == "refund"
            and data.refund_amount * data.exchange_rate_to_usd > policy.refund_limit
        ):
            reasons.append("退款金额超过 USD 自动处理上限")
            amount = round(data.refund_amount * data.exchange_rate_to_usd, 2)
            facts.extend(
                [
                    {"label": "申请退款", "value": f"{data.refund_amount} {data.currency}"},
                    {"label": "退款金额 USD", "value": amount},
                    {"label": "退款阈值 USD", "value": policy.refund_limit},
                    {"label": "超出金额 USD", "value": round(amount - policy.refund_limit, 2)},
                    {"label": "换算汇率", "value": data.exchange_rate_to_usd},
                ]
            )
    if reasons and task.approval_version != version:
        raise Hold(
            "waiting_review",
            "；".join(reasons),
            {"rules": matches, "policy_version": version, "review_facts": facts},
        )


def retire_unsupported_run(db: Session, run: OpsRun) -> bool:
    """Keep old results readable without executing removed placeholder tools."""
    if run.status in {"succeeded", "terminated", "cancelled", "rejected"}:
        return False
    tasks = tasks_for(db, run.id)
    supported = {step[0] for _, steps in WORKFLOWS.values() for step in steps} | EXTERNAL_STEPS
    if (
        run.workflow in WORKFLOWS
        and all(t.key in supported or t.status == "succeeded" for t in tasks)
    ):
        return False
    reason = "此流程包含已移除的占位功能，已停止调度；历史结果保留，请按当前流程重新建单"
    result = db.execute(
        update(OpsRun)
        .where(
            OpsRun.id == run.id,
            OpsRun.status.not_in(["succeeded", "terminated", "cancelled", "rejected"]),
        )
        .values(status="cancelled", updated_at=now())
    )
    if not result.rowcount:
        return True
    db.execute(
        update(OpsTask)
        .where(OpsTask.run_id == run.id, OpsTask.status != "succeeded")
        .values(status="cancelled", reason=reason)
    )
    audit(db, run.organization_id, "system", "workflow_retired", reason, run.id)
    return True


def dispatch_run(org: str, run_id: str) -> list[str]:
    """Consume committed events, atomically claim ready DAG nodes, then publish a group."""
    claimed = []
    with session_scope() as db:
        run = get_run(db, org, run_id)
        events = list(
            db.scalars(
                select(OpsEvent).where(
                    OpsEvent.run_id == run.id,
                    OpsEvent.status == "pending",
                )
            )
        )
        # Events describe durable changes; ready-state CAS prevents duplicate deliveries.
        for row in events:
            row.status = "delivered"
        if run.status in {"terminated", "cancelled", "taken_over", "rejected"}:
            return []
        if retire_unsupported_run(db, run):
            return []
        config = configuration(db, org)
        if run.workflow != "initialization":
            ready = db.scalar(
                select(OpsRun.id)
                .where(
                    OpsRun.organization_id == org,
                    OpsRun.workflow == "initialization",
                    OpsRun.status == "succeeded",
                )
                .limit(1)
            )
            if not ready:
                set_active_state(db, run, "waiting_initialization")
                return []
        run.config_version = config.version
        tasks = tasks_for(db, run.id)
        states = {t.key: t.status for t in tasks}
        # A review pauses the whole run; independent integration/data holds do not.
        if any(t.status == "waiting_review" for t in tasks):
            set_active_state(db, run, "waiting_review")
            return []
        for task in tasks:
            if task.status == "pending" and all(
                states.get(d) == "succeeded" for d in task.dependencies
            ):
                result = db.execute(
                    update(OpsTask)
                    .where(
                        OpsTask.id == task.id,
                        OpsTask.status == "pending",
                    )
                    .values(status="queued")
                )
                if result.rowcount == 1:
                    claimed.append(task.id)
        db.flush()
        summarize(db, run)
    if claimed:
        from celery import group

        from app.workers.tasks import execute_ecom_step

        group(execute_ecom_step.s(org, run_id, task_id) for task_id in claimed).apply_async()
    return claimed


def execute_step(org: str, run_id: str, task_id: str) -> None:
    with session_scope() as db:
        run = get_run(db, org, run_id)
        task = db.get(OpsTask, task_id)
        if task is None or task.run_id != run.id:
            return
        if run.status in {"terminated", "cancelled", "taken_over", "rejected"}:
            return
        if retire_unsupported_run(db, run):
            return
        if any(t.status == "waiting_review" for t in tasks_for(db, run_id)):
            if task.status == "queued":
                task.status = "pending"
            return
        result = db.execute(
            update(OpsTask)
            .where(
                OpsTask.id == task.id,
                OpsTask.status == "queued",
            )
            .values(status="running", attempts=OpsTask.attempts + 1, started_at=now())
        )
        if result.rowcount != 1:
            return
        db.flush()
        db.refresh(task)
        config = configuration(db, org)
        policy = Policy(**config.payload)
        run.config_version = config.version
        try:
            risk_gate(db, run, task, policy, config.version)
            # A prior explicit human review can clear a tool's manual evidence gate.
            try:
                if (
                    task.approval_version == config.version
                    and task.output.get("ai_status") == "generated"
                ):
                    # Review the exact persisted model candidate, never regenerate after approval.
                    _, matches = scan(str(task.output.get("model_draft", "")), policy)
                    if any(r["level"] == "high" for r in matches):
                        raise Hold("terminated", "已审核候选命中新版高风险规则", task.output)
                    task.output = {**task.output, "human_verified": True}
                else:
                    task.output = enrich(db, run, task, execute_tool(db, run, task, policy), policy)
            except Hold as hold:
                if hold.status == "waiting_review" and task.approval_version == config.version:
                    task.output = {
                        **hold.output,
                        "human_verified": True,
                        "review_scope": task.reason,
                        "platform_write": False,
                    }
                else:
                    raise
            task.status, task.reason = "succeeded", ""
            task.completed_at = now()
            _, matches = scan(content_for(db, run), policy)
            task.risk = "low" if any(r["level"] == "low" for r in matches) else "none"
            event(db, run, "task.succeeded", task.id)
        except Hold as hold:
            task.status, task.reason, task.output = hold.status, hold.reason, hold.output
            if hold.status == "waiting_review":
                task.output = {**task.output, "policy_version": config.version}
            task.risk = "high" if hold.status == "terminated" else "medium"
            if hold.status in {"terminated", "waiting_review"}:
                alert_id = f"ecom-{task.id}-{hold.status}"
                alert_label = "熔断" if hold.status == "terminated" else "待审核"
                if db.get(AlertModel, alert_id) is None:
                    db.add(
                        AlertModel(
                            id=alert_id,
                            organization_id=org,
                            title=f"跨境任务{alert_label}：{run.title}"[:200],
                            description=f"{hold.reason}。请到跨境智能体中枢处理，任务 {run.id}"[
                                :500
                            ],
                            severity="critical" if hold.status == "terminated" else "warning",
                            shop_id=f"ecomops-{run.input['platform']}",
                            shop_name=f"{run.input['platform']} · 跨境任务",
                            created_at=now(),
                        )
                    )
            if hold.status in {"terminated", "rejected"}:
                run.status = hold.status
                for sibling in tasks_for(db, run.id):
                    if sibling.id != task.id and sibling.status in {"pending", "queued"}:
                        sibling.status = "cancelled"
                audit(db, org, "compliance", hold.status, hold.reason, run.id)
            event(db, run, f"task.{hold.status}", task.id, {"reason": hold.reason})
        except Exception as exc:
            task.status = "dead_letter" if task.attempts >= policy.max_attempts else "failed"
            # Do not expose adapter exceptions containing payloads or credentials.
            task.reason = f"执行失败（{type(exc).__name__}），请检查服务端日志后重试"
            event(db, run, f"task.{task.status}", task.id)
        db.flush()
        summarize(db, run)
    dispatch_run(org, run_id)


def intervene(db: Session, org: str, actor: str, run_id: str, payload: Intervention) -> OpsRun:
    # Versioned CAS serializes interventions against the same run, including SQLite.
    run = get_run(db, org, run_id)
    touched = db.execute(
        update(OpsRun)
        .where(
            OpsRun.id == run.id,
            OpsRun.updated_at == run.updated_at,
        )
        .values(updated_at=now())
    )
    if touched.rowcount != 1:
        db.rollback()
        raise ValueError("任务状态已变化，请刷新后重试")
    config = configuration(db, org)
    task = db.get(OpsTask, payload.task_id) if payload.task_id else None
    if task and task.run_id != run.id:
        raise LookupError("步骤不存在")
    if payload.task_id and not task:
        raise LookupError("步骤不存在")
    action = payload.action
    terminal = run.status in {"succeeded", "cancelled", "terminated", "rejected"}
    if terminal:
        raise ValueError("终态任务不能修改；请修正规则或数据后发起新任务")
    if action in {"approve", "reject"}:
        if task is None or task.status != "waiting_review":
            raise ValueError("只能审批等待人工审核的步骤")
        if action == "approve" and (
            payload.review_version != config.version
            or task.output.get("policy_version") != config.version
        ):
            raise ValueError("规则已变化或缺少审核版本，请先重新评估规则并查看最新依据")
        task.approval_version = config.version if action == "approve" else None
        task.status = "pending" if action == "approve" else "rejected"
        if action == "reject":
            run.status = "rejected"
            for other in tasks_for(db, run.id):
                if other.status in {"pending", "queued"}:
                    other.status = "cancelled"
    elif action == "takeover":
        run.status = "taken_over"
    elif action == "resume":
        if run.status != "taken_over":
            raise ValueError("只有人工接管的任务可以恢复")
        run.status = "queued"
    elif action == "cancel":
        run.status = "cancelled"
        for other in tasks_for(db, run.id):
            if other.status != "succeeded":
                other.status = "cancelled"
    elif action == "priority":
        run.priority = payload.priority
    elif action == "reevaluate":
        if task is None or task.status != "waiting_review":
            raise ValueError("只能重新评估待审核的步骤")
        task.status, task.reason, task.approval_version = "pending", "", None
    elif action == "retry":
        if task is None or task.status not in {"failed", "waiting_data", "waiting_integration"}:
            raise ValueError("只能重试失败、待数据或待接入步骤；死信需修复后新建运行")
        if task.status == "failed" and task.attempts >= Policy(**config.payload).max_attempts:
            raise ValueError("重试次数耗尽")
        task.status, task.reason = "pending", ""
        task.approval_version = None
    audit(db, org, actor, action, payload.note, run.id)
    event(db, run, f"human.{action}", payload.task_id, {"actor": actor, "note": payload.note})
    db.commit()
    return run


def import_records(db: Session, org: str, actor: str, payload: ImportRequest) -> dict:
    seen, inserted, updated = set(), 0, 0
    # Validate the whole batch before writing any row.
    normalized = []
    numeric = {
        "revenue",
        "cost",
        "ad_spend",
        "orders",
        "customers",
        "repeat_customers",
        "refunds",
        "visits",
        "conversions",
    }
    for item in payload.records:
        key = item.key.strip().upper() if item.kind == "product" else item.key.strip()
        if not key:
            raise ValueError("标准化后编码不能为空")
        data = dict(item.data)
        if item.kind == "metric":
            if data.get("currency", "USD") != "USD":
                raise ValueError("指标导入要求先显式换算为 USD，并保留汇率来源")
            for field in numeric:
                value = data.get(field, 0)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not __import__("math").isfinite(value)
                    or value < 0
                ):
                    raise ValueError(f"指标 {field} 必须是有限非负数字")
        if (item.kind, key) in seen:
            continue
        seen.add((item.kind, key))
        normalized.append((item, key, data))
    for item, key, data in normalized:
        row = db.scalar(
            select(OpsRecord).where(
                OpsRecord.organization_id == org, OpsRecord.kind == item.kind, OpsRecord.key == key
            )
        )
        if row:
            row.payload, row.source, row.is_demo, row.updated_at = (
                data,
                item.source,
                item.is_demo,
                now(),
            )
            updated += 1
        else:
            db.add(
                OpsRecord(
                    id=uid(),
                    organization_id=org,
                    kind=item.kind,
                    key=key,
                    payload=data,
                    source=item.source,
                    is_demo=item.is_demo,
                    updated_at=now(),
                )
            )
            inserted += 1
    audit(
        db,
        org,
        actor,
        "data_import",
        f"新增 {inserted}，更新 {updated}，同批去重 {len(payload.records) - len(seen)}",
    )
    db.commit()
    return {
        "inserted": inserted,
        "updated": updated,
        "deduplicated": len(payload.records) - len(seen),
    }


def serialize(row) -> dict:
    result = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    # SQLite returns naive datetimes; every persisted domain timestamp is UTC.
    return {
        key: value.replace(tzinfo=UTC)
        if isinstance(value, datetime) and value.tzinfo is None
        else value
        for key, value in result.items()
    }


def public_record(row: OpsRecord) -> dict:
    result = serialize(row)
    if row.kind in {"customer", "order"}:
        result["payload"] = redact(result["payload"])
    return result


def redact(value):
    sensitive = {
        "name",
        "phone",
        "mobile",
        "email",
        "address",
        "destination_address",
        "buyer_name",
        "customer_name",
        "recipient",
        "token",
        "api_key",
        "password",
    }
    if isinstance(value, dict):
        return {k: "***" if k.casefold() in sensitive else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def run_detail(db: Session, org: str, run_id: str) -> dict:
    run = get_run(db, org, run_id)
    serialized = serialize(run)
    serialized["input"] = redact(serialized["input"])
    return {
        **serialized,
        "tasks": [serialize(t) for t in tasks_for(db, run.id)],
        "events": [
            serialize(e)
            for e in db.scalars(
                select(OpsEvent)
                .where(
                    OpsEvent.run_id == run.id,
                    OpsEvent.organization_id == org,
                )
                .order_by(OpsEvent.created_at)
                .limit(300)
            )
        ],
        "audits": [
            serialize(a)
            for a in db.scalars(
                select(OpsAudit)
                .where(
                    OpsAudit.run_id == run.id,
                    OpsAudit.organization_id == org,
                )
                .order_by(OpsAudit.created_at)
                .limit(300)
            )
        ],
    }


def overview(db: Session, org: str) -> dict:
    config = configuration(db, org)
    runs = list(
        db.scalars(
            select(OpsRun)
            .where(OpsRun.organization_id == org)
            .order_by(OpsRun.created_at.desc())
            .limit(100)
        )
    )
    return {
        "configuration": serialize(config),
        "platforms": PLATFORMS,
        "agents": [{"id": a, "name": n, "responsibility": r} for a, n, r in AGENTS],
        "workflows": [
            {
                "id": k,
                "name": v[0],
                "steps": [
                    {"key": key, "agent": agent, "title": title, "dependencies": deps}
                    for key, agent, title, deps in v[1]
                ],
            }
            for k, v in WORKFLOWS.items()
        ],
        "runs": [{k: v for k, v in serialize(r).items() if k != "input"} for r in runs],
        "mode": "sandbox",
        "initialization_ready": any(
            r.workflow == "initialization" and r.status == "succeeded"
            for r in db.scalars(select(OpsRun).where(OpsRun.organization_id == org))
        ),
        "production_ready": False,
        "limitations": [
            "跨境平台官方连接器未实现，六类双向实时同步不可用",
            "本地规则与草稿可执行；可选模型生成需配置与开关，图片处理和平台写入需单独验证",
            "规则为可配置示例，完整知识产权、税务和贸易管制需人工核验",
        ],
        "data_counts": {
            kind: len(
                list(
                    db.scalars(
                        select(OpsRecord.id).where(
                            OpsRecord.organization_id == org,
                            OpsRecord.kind == kind,
                        )
                    )
                )
            )
            for kind in ["product", "supplier", "customer", "competitor", "order", "metric", "term"]
        },
    }


def recover_and_tick(organization_id: str | None = None) -> dict:
    """Celery Beat entry: recover delivery gaps/stale claims and trigger due schedules."""
    from app.db.ecomops import OpsSchedule
    from app.workers.tasks import dispatch_ecom_run

    targets = set()
    triggered = 0
    with session_scope() as db:

        def scope(statement, model):
            return (
                statement.where(model.organization_id == organization_id)
                if organization_id
                else statement
            )

        for schedule in db.scalars(
            scope(
                select(OpsSchedule).where(
                    OpsSchedule.enabled.is_(True),
                    OpsSchedule.workflow.in_(RETIRED_WORKFLOWS),
                ),
                OpsSchedule,
            )
        ):
            schedule.enabled = False
            audit(db, schedule.organization_id, "system", "schedule_retired", schedule.id)
        for run in db.scalars(
            scope(
                select(OpsRun).where(
                    OpsRun.workflow.in_(RETIRED_WORKFLOWS),
                    OpsRun.status.notin_(["succeeded", "terminated", "cancelled", "rejected"]),
                ),
                OpsRun,
            )
        ):
            retire_unsupported_run(db, run)
        pending = db.scalars(scope(select(OpsEvent).where(OpsEvent.status == "pending"), OpsEvent))
        targets.update((e.organization_id, e.run_id) for e in pending)
        for task in db.scalars(
            scope(select(OpsTask).where(OpsTask.status.in_(["running", "queued"])), OpsTask)
        ):
            run = db.get(OpsRun, task.run_id)
            stale = (task.started_at or run.updated_at).replace(tzinfo=UTC) < now() - timedelta(
                minutes=15
            )
            if stale and run.status not in {"terminated", "cancelled", "taken_over", "rejected"}:
                limit = Policy(**configuration(db, task.organization_id).payload).max_attempts
                task.status = "dead_letter" if task.attempts >= limit else "failed"
                task.reason = "步骤超过 15 分钟未完成，请检查后重试"
                event(db, run, "task.timeout", task.id)
                targets.add((task.organization_id, task.run_id))
                db.flush()
                summarize(db, run)
        db.commit()
        for schedule in list(
            db.scalars(
                scope(
                    select(OpsSchedule).where(
                        OpsSchedule.enabled.is_(True),
                        OpsSchedule.next_run_at <= now(),
                    ),
                    OpsSchedule,
                )
            )
        ):
            due = schedule.next_run_at.replace(tzinfo=UTC)
            # Catch up once, then advance to the next future slot, never flood overdue runs.
            periods = int((now() - due).total_seconds() // (schedule.interval_hours * 3600)) + 1
            run = create_run(
                db,
                schedule.organization_id,
                "scheduler",
                RunCreate(
                    workflow=schedule.workflow,
                    title=f"定时 {WORKFLOWS[schedule.workflow][0]}",
                    idempotency_key=f"{schedule.id}:{due.isoformat()}",
                    input=BusinessInput(**schedule.input),
                ),
            )
            schedule.next_run_at = due + timedelta(hours=schedule.interval_hours * periods)
            db.commit()
            triggered += 1
            targets.add((run.organization_id, run.id))
        # Initialization completion can release runs created earlier.
        for run in db.scalars(
            scope(select(OpsRun).where(OpsRun.status == "waiting_initialization"), OpsRun)
        ):
            targets.add((run.organization_id, run.id))
    with session_scope() as db:
        priorities = {
            r.id: r.priority
            for r in db.scalars(
                select(OpsRun).where(
                    OpsRun.id.in_([run_id for _, run_id in targets]),
                )
            )
        }
    for org, run_id in sorted(targets, key=lambda target: priorities.get(target[1], 5)):
        dispatch_ecom_run.delay(org, run_id)
    return {"triggered_schedules": triggered, "dispatched_runs": len(targets)}
