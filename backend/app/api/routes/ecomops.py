from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_demo_user
from app.db.ecomops import OpsRecord, OpsSchedule
from app.db.session import get_db
from app.schemas.auth import UserProfile
from app.schemas.ecomops import (
    ConfigurationUpdate,
    ImportRequest,
    Intervention,
    RunCreate,
    ScheduleCreate,
    ScheduleUpdate,
)
from app.schemas.research import ResearchAnalysis, ResearchBatch
from app.services import ecomops_service as service
from app.services.browser_research import analyze_research, import_research, list_collections
from app.services.ecomops_specialists import performance
from app.workers.tasks import dispatch_ecom_run, tick_ecomops

router = APIRouter(prefix="/ecomops", tags=["ecomops"], dependencies=[Depends(require_demo_user)])
DB = Annotated[Session, Depends(get_db)]
User = Annotated[UserProfile, Depends(require_demo_user)]


def check_admin(user: UserProfile) -> None:
    if "automation:manage" not in user.permissions:
        raise HTTPException(403, "需要自动化管理权限")


@router.get("/overview")
def overview(db: DB, user: User):
    return service.overview(db, user.organization_id)


@router.put("/configuration")
def configure(payload: ConfigurationUpdate, db: DB, user: User):
    check_admin(user)
    try:
        return service.serialize(
            service.update_configuration(
                db,
                user.organization_id,
                user.name,
                payload.version,
                payload.policy,
            )
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/data/import")
def import_data(payload: ImportRequest, db: DB, user: User):
    check_admin(user)
    try:
        return service.import_records(db, user.organization_id, user.name, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/data")
def list_data(
    db: DB, user: User, kind: str | None = None, limit: int = Query(default=100, ge=1, le=500)
):
    statement = select(OpsRecord).where(OpsRecord.organization_id == user.organization_id)
    if kind:
        statement = statement.where(OpsRecord.kind == kind)
    return [
        service.public_record(row)
        for row in db.scalars(
            statement.order_by(OpsRecord.updated_at.desc()).limit(limit),
        )
    ]


@router.post("/research/import")
def import_browser_research(payload: ResearchBatch, db: DB, user: User):
    check_admin(user)
    return import_research(db, user.organization_id, user.name, payload)


@router.post("/research/analyze")
def analyze_browser_research(payload: ResearchAnalysis, db: DB, user: User):
    return analyze_research(db, user.organization_id, payload)


@router.get("/research/collections")
def browser_research_collections(db: DB, user: User):
    return list_collections(db, user.organization_id)


@router.post("/runs", status_code=201)
def create_run(payload: RunCreate, db: DB, user: User):
    check_admin(user)
    try:
        run = service.create_run(db, user.organization_id, user.name, payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    dispatch_ecom_run.delay(user.organization_id, run.id)
    db.expire_all()
    return service.run_detail(db, user.organization_id, run.id)


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: DB, user: User):
    try:
        return service.run_detail(db, user.organization_id, run_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/runs/{run_id}/intervene")
def intervene(run_id: str, payload: Intervention, db: DB, user: User):
    check_admin(user)
    try:
        service.intervene(db, user.organization_id, user.name, run_id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    dispatch_ecom_run.delay(user.organization_id, run_id)
    db.expire_all()
    return service.run_detail(db, user.organization_id, run_id)


@router.get("/performance")
def get_performance(db: DB, user: User):
    return performance(db, user.organization_id)


@router.get("/schedules")
def list_schedules(db: DB, user: User):
    return [
        service.serialize(s)
        for s in db.scalars(
            select(OpsSchedule)
            .where(
                OpsSchedule.organization_id == user.organization_id,
            )
            .order_by(OpsSchedule.next_run_at)
        )
    ]


@router.post("/schedules", status_code=201)
def create_schedule(payload: ScheduleCreate, db: DB, user: User):
    check_admin(user)
    row = OpsSchedule(
        id=service.uid(),
        organization_id=user.organization_id,
        workflow=payload.workflow,
        interval_hours=payload.interval_hours,
        enabled=True,
        input=payload.input.model_dump(),
        next_run_at=service.now(),
    )
    db.add(row)
    service.audit(db, user.organization_id, user.name, "schedule_create", payload.workflow)
    db.commit()
    return service.serialize(row)


@router.patch("/schedules/{schedule_id}")
def update_schedule(schedule_id: str, payload: ScheduleUpdate, db: DB, user: User):
    check_admin(user)
    row = db.get(OpsSchedule, schedule_id)
    if row is None or row.organization_id != user.organization_id:
        raise HTTPException(404, "计划不存在")
    if payload.enabled and row.workflow not in service.WORKFLOWS:
        raise HTTPException(409, "该流程已移除，请创建当前支持的计划")
    row.enabled = payload.enabled
    service.audit(
        db, user.organization_id, user.name, "schedule_toggle", f"{row.id}: {row.enabled}"
    )
    db.commit()
    return service.serialize(row)


@router.post("/tick")
def tick(user: User):
    check_admin(user)
    # Global recovery belongs to the system worker; this endpoint must stay tenant scoped.
    tick_ecomops.delay(user.organization_id)
    return {"status": "submitted", "message": "已提交当前组织的计划扫描与事件恢复"}
