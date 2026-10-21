"""任务运维：超时巡检、重试、死信与监控指标。

单进程 `eager` 模式下没有独立 broker 与 worker 进程，本模块按同一套语义
覆盖三类真实任务：操作任务（`operation_jobs`）、素材生成（`generation_jobs`）、
智能体运行（`agent_runs`）。三条规则：

- **超时**：处于 running 且超过阈值（按任务类型）的视为卡死，由 `sweep_stale_tasks`
  标记为 failed 并写明原因；生产模式下该巡检由调度器周期调用
  （`ops.sweep_stale_tasks` 任务入口），不再依赖"任务一定不会卡"的乐观假设；
- **重试**：failed 任务可重试，`attempts` 递增，重新走原 Celery 入口；
- **死信**：失败且 `attempts >= max_attempts` 的任务进入 `dead_letter` 状态，
  只能查看或丢弃，防止无限重试掩盖系统性问题。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import AgentRunModel, GenerationJobModel, OperationJobModel

SHANGHAI = ZoneInfo("Asia/Shanghai")

KIND_OPERATION = "operation_job"
KIND_GENERATION = "generation_job"
KIND_AGENT = "agent_run"
TASK_KINDS = (KIND_OPERATION, KIND_GENERATION, KIND_AGENT)

STATUS_DEAD_LETTER = "dead_letter"
STATUS_DISMISSED = "dismissed"
STATUS_FAILED = "failed"
STATUS_RUNNING = "running"

# running 超过阈值视为卡死（按任务类型）
STALE_TIMEOUTS: dict[str, timedelta] = {
    KIND_OPERATION: timedelta(minutes=15),
    KIND_GENERATION: timedelta(minutes=10),
    KIND_AGENT: timedelta(minutes=10),
}

SUCCESS_STATUSES = {"succeeded", "partial"}


def _operation_title(model: OperationJobModel) -> str:
    label = {"product": "商品批量任务", "order": "订单处置任务"}.get(model.kind, "操作任务")
    return f"{label} · {model.action}"


def _generation_title(model: GenerationJobModel) -> str:
    label = {
        "copy": "文案",
        "image": "图片",
        "video": "视频",
        "video_script": "脚本",
        "template": "模板",
    }.get(model.asset_type, model.asset_type)
    return f"素材生成 · {label}"


def _agent_title(model: AgentRunModel) -> str:
    goal = model.goal if len(model.goal) <= 40 else model.goal[:40] + "…"
    return f"智能体复盘 · {goal}"


def _to_task(kind: str, model: Any) -> dict:
    return {
        "kind": kind,
        "id": model.id,
        "title": {
            KIND_OPERATION: _operation_title,
            KIND_GENERATION: _generation_title,
            KIND_AGENT: _agent_title,
        }[kind](model),
        "status": model.status,
        "progress": getattr(model, "progress", 0),
        "attempts": getattr(model, "attempts", 1),
        "max_attempts": getattr(model, "max_attempts", 3),
        "error": getattr(model, "last_error", None) or getattr(model, "error_message", None),
        "created_at": model.created_at,
        "started_at": getattr(model, "started_at", None),
        "updated_at": model.updated_at,
        "completed_at": getattr(model, "completed_at", None),
        "is_demo": model.is_demo,
    }


def _fetch(db: Session, kind: str, limit: int = 200) -> list[Any]:
    model = {
        KIND_OPERATION: OperationJobModel,
        KIND_GENERATION: GenerationJobModel,
        KIND_AGENT: AgentRunModel,
    }[kind]
    return list(db.scalars(select(model).order_by(desc(model.created_at)).limit(limit)).all())


def list_tasks(
    db: Session,
    *,
    kind: str | None = None,
    status_filter: str | None = None,
    limit: int = 100,
) -> list[dict]:
    kinds = (kind,) if kind in TASK_KINDS else TASK_KINDS
    tasks: list[dict] = []
    for item_kind in kinds:
        tasks.extend(_to_task(item_kind, row) for row in _fetch(db, item_kind))
    if status_filter:
        tasks = [task for task in tasks if task["status"] == status_filter]
    tasks.sort(key=lambda task: task["created_at"], reverse=True)
    return tasks[:limit]


def get_metrics(db: Session) -> dict:
    """监控指标：状态分布、失败率、平均耗时与最近失败。"""
    all_tasks: list[dict] = []
    by_kind: dict[str, dict[str, int]] = {}
    for item_kind in TASK_KINDS:
        rows = [_to_task(item_kind, row) for row in _fetch(db, item_kind)]
        all_tasks.extend(rows)
        statuses: dict[str, int] = {}
        for task in rows:
            statuses[task["status"]] = statuses.get(task["status"], 0) + 1
        by_kind[item_kind] = statuses

    total = len(all_tasks)
    failed = sum(
        1 for task in all_tasks if task["status"] in {STATUS_FAILED, STATUS_DEAD_LETTER}
    )
    durations = [
        (task["completed_at"] or task["updated_at"]) - task["created_at"]
        for task in all_tasks
        if task["status"] in SUCCESS_STATUSES or task["completed_at"]
    ]
    avg_duration = (
        round(sum(item.total_seconds() for item in durations) / len(durations), 2)
        if durations
        else 0.0
    )
    recent_failures = sorted(
        (task for task in all_tasks if task["status"] in {STATUS_FAILED, STATUS_DEAD_LETTER}),
        key=lambda task: task["updated_at"],
        reverse=True,
    )[:10]
    return {
        "generated_at": datetime.now(SHANGHAI),
        "totals": {
            "total": total,
            "succeeded": sum(1 for task in all_tasks if task["status"] in SUCCESS_STATUSES),
            "running": sum(1 for task in all_tasks if task["status"] == STATUS_RUNNING),
            "failed": failed,
            "dead_letter": sum(
                1 for task in all_tasks if task["status"] == STATUS_DEAD_LETTER
            ),
            "dismissed": sum(
                1 for task in all_tasks if task["status"] == STATUS_DISMISSED
            ),
        },
        "failure_rate": round(failed / total, 4) if total else 0.0,
        "avg_duration_seconds": avg_duration,
        "by_kind": by_kind,
        "recent_failures": [
            {
                "kind": task["kind"],
                "id": task["id"],
                "title": task["title"],
                "error": task["error"],
                "attempts": task["attempts"],
                "updated_at": task["updated_at"],
            }
            for task in recent_failures
        ],
    }


def sweep_stale_tasks(db: Session) -> dict:
    """超时巡检 + 死信判定。返回处理明细。"""
    now = datetime.now(SHANGHAI)
    timed_out: list[dict] = []
    dead_lettered: list[dict] = []

    for kind, timeout in STALE_TIMEOUTS.items():
        for row in _fetch(db, kind):
            if row.status == STATUS_RUNNING:
                anchor = getattr(row, "started_at", None) or row.created_at
                # SQLite 读回的 datetime 可能无时区标记，按本地时区补齐后再比较
                if anchor.tzinfo is None:
                    anchor = anchor.replace(tzinfo=SHANGHAI)
                if now - anchor > timeout:
                    message = (
                        f"执行超时（超过 {int(timeout.total_seconds() // 60)} 分钟未完成），"
                        "已由巡检标记为失败"
                    )
                    if kind == KIND_OPERATION:
                        row.last_error = message
                    else:
                        row.error_message = message
                    row.status = STATUS_FAILED
                    row.updated_at = now
                    timed_out.append({"kind": kind, "id": row.id, "reason": message})
            if row.status == STATUS_FAILED:
                attempts = getattr(row, "attempts", 1)
                max_attempts = getattr(row, "max_attempts", 3)
                if attempts >= max_attempts:
                    row.status = STATUS_DEAD_LETTER
                    row.dead_letter_at = now
                    row.updated_at = now
                    dead_lettered.append(
                        {"kind": kind, "id": row.id, "attempts": attempts}
                    )
    db.commit()
    return {
        "checked_at": now,
        "timed_out": timed_out,
        "dead_lettered": dead_lettered,
    }


def _get_task(db: Session, kind: str, task_id: str) -> Any | None:
    model = {
        KIND_OPERATION: OperationJobModel,
        KIND_GENERATION: GenerationJobModel,
        KIND_AGENT: AgentRunModel,
    }.get(kind)
    if model is None:
        return None
    return db.get(model, task_id)


def retry_task(db: Session, kind: str, task_id: str) -> dict | None:
    """重试失败任务。达到重试上限或已进死信的拒绝重试。"""
    row = _get_task(db, kind, task_id)
    if row is None:
        return None
    if row.status not in {STATUS_FAILED, STATUS_DEAD_LETTER}:
        raise ValueError("只有失败或死信状态的任务可以重试")
    attempts = getattr(row, "attempts", 1)
    max_attempts = getattr(row, "max_attempts", 3)
    if row.status == STATUS_DEAD_LETTER or attempts >= max_attempts:
        raise ValueError("重试次数已达上限，任务处于死信状态，只能丢弃")

    row.attempts = attempts + 1
    # 各任务域的待执行状态词汇不同
    row.status = "planning" if kind == KIND_AGENT else "queued"
    row.progress = 0
    row.started_at = None
    if kind == KIND_OPERATION:
        row.last_error = None
    else:
        row.error_message = None
    row.updated_at = datetime.now(SHANGHAI)
    db.commit()

    # 重新派发到原 Celery 入口（eager 模式下同步执行）
    from app.workers.tasks import (
        execute_agent_run,
        process_generation_job,
        process_order_action,
        process_product_batch,
    )

    if kind == KIND_OPERATION:
        if getattr(row, "kind", None) == "order":
            process_order_action.delay(row.id)
        else:
            process_product_batch.delay(row.id)
    elif kind == KIND_GENERATION:
        process_generation_job.delay(row.id)
    else:
        execute_agent_run.delay(row.id)

    db.expire(row)
    return _to_task(kind, row)


def discard_task(db: Session, kind: str, task_id: str) -> dict | None:
    """丢弃失败/死信任务（保留记录，不再重试）。"""
    row = _get_task(db, kind, task_id)
    if row is None:
        return None
    if row.status not in {STATUS_FAILED, STATUS_DEAD_LETTER}:
        raise ValueError("只有失败或死信状态的任务可以丢弃")
    row.status = STATUS_DISMISSED
    row.updated_at = datetime.now(SHANGHAI)
    db.commit()
    return _to_task(kind, row)
