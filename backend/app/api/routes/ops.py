from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import require_demo_user
from app.db.session import get_db
from app.schemas.auth import UserProfile
from app.schemas.ops import OpsMetrics, OpsSweepResult, OpsTask
from app.services.ops_task_service import (
    TASK_KINDS,
    discard_task,
    get_metrics,
    list_tasks,
    retry_task,
    sweep_stale_tasks,
)

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/metrics", response_model=OpsMetrics)
def ops_metrics(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OpsMetrics:
    """任务监控指标：状态分布、失败率、平均耗时与最近失败。"""
    return OpsMetrics(**get_metrics(db))


@router.get("/tasks", response_model=list[OpsTask])
def ops_tasks(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    kind: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[OpsTask]:
    """统一任务视图：操作任务 / 素材生成 / 智能体运行。"""
    if kind is not None and kind not in TASK_KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="未知任务类型",
        )
    return [OpsTask(**item) for item in list_tasks(db, kind=kind, status_filter=status_filter)]


@router.post("/tasks/sweep", response_model=OpsSweepResult)
def ops_sweep(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OpsSweepResult:
    """超时巡检：标记卡死任务为失败，并推进重试耗尽的任务进入死信。

    生产模式下由调度器周期调用（Celery 入口 `ops.sweep_stale_tasks`）。
    """
    return OpsSweepResult(**sweep_stale_tasks(db))


@router.post("/tasks/{kind}/{task_id}/retry", response_model=OpsTask)
def ops_retry(
    kind: str,
    task_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OpsTask:
    """重试失败任务；重试次数耗尽的进入死信，拒绝继续重试。"""
    try:
        result = retry_task(db, kind, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return OpsTask(**result)


@router.post("/tasks/{kind}/{task_id}/discard", response_model=OpsTask)
def ops_discard(
    kind: str,
    task_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OpsTask:
    """丢弃失败或死信任务（保留记录，不再重试）。"""
    try:
        result = discard_task(db, kind, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return OpsTask(**result)
