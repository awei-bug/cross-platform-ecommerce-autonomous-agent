from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import require_demo_user
from app.db.session import get_db
from app.schemas.auth import UserProfile
from app.schemas.automation import (
    AutomationMode,
    AutomationOverview,
    AutomationRule,
    AutomationRuleUpdate,
    AutomationRun,
    AutomationRunRequest,
    AutomationTask,
    AutomationTaskUpdate,
)
from app.services.automation_repository import list_overview, run_rule, update_rule, update_task

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("", response_model=AutomationOverview)
def overview(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AutomationOverview:
    return list_overview(db, user.organization_id)


@router.patch("/rules/{rule_id}", response_model=AutomationRule)
def patch_rule(
    rule_id: str,
    payload: AutomationRuleUpdate,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AutomationRule:
    if payload.mode == AutomationMode.AUTO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="演示数据不允许启用自动执行模式",
        )
    updated = update_rule(
        db,
        user.organization_id,
        rule_id,
        payload.model_dump(exclude_unset=True, mode="json"),
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="自动化规则不存在")
    return updated


@router.post("/rules/{rule_id}/runs", response_model=AutomationRun, status_code=201)
def execute_rule(
    rule_id: str,
    payload: AutomationRunRequest,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AutomationRun:
    try:
        run = run_rule(db, user.organization_id, rule_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="自动化规则不存在")
    return run


@router.patch("/tasks/{task_id}", response_model=AutomationTask)
def patch_task(
    task_id: str,
    payload: AutomationTaskUpdate,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AutomationTask:
    updated = update_task(
        db,
        user.organization_id,
        task_id,
        payload.model_dump(exclude_unset=True, mode="json"),
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="自动化任务不存在")
    return updated
