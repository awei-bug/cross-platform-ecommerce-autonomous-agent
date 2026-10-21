from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import require_demo_user
from app.db.session import get_db
from app.integrations.taobao import TaobaokeApiError, TaobaokeNotConfigured
from app.schemas.agent import (
    AgentRun,
    AgentRunCreate,
    AgentRunListItem,
    CompetitorCreate,
    CompetitorImportRequest,
    CompetitorImportResult,
    CompetitorItem,
    Diagnosis,
    DiagnosisDecision,
)
from app.schemas.auth import UserProfile
from app.services.agent_orchestrator import (
    create_run,
    decide_diagnosis,
    get_run,
    list_runs,
)
from app.services.competitor_repository import (
    create_competitor,
    import_taobaoke_competitors,
    list_competitors,
)
from app.workers.tasks import execute_agent_run

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/runs", response_model=AgentRun, status_code=201)
def create_agent_run(
    payload: AgentRunCreate,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentRun:
    """提交自然语言目标，创建并执行一次智能体复盘运行。"""
    run = create_run(
        db, user.organization_id, goal=payload.goal, shop_ids=payload.shop_ids
    )
    execute_agent_run.delay(run.id)
    result = get_run(db, run.id)
    if result is None:  # pragma: no cover - 防御性分支
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="运行创建后无法读取状态",
        )
    return result


@router.get("/runs", response_model=list[AgentRunListItem])
def list_agent_runs(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AgentRunListItem]:
    return list_runs(db, user.organization_id, limit=limit)


@router.get("/runs/{run_id}", response_model=AgentRun)
def get_agent_run(
    run_id: str,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentRun:
    result = get_run(db, run_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体运行不存在")
    return result


@router.post(
    "/runs/{run_id}/diagnoses/{diagnosis_id}/decision",
    response_model=Diagnosis,
)
def decide_diagnosis_route(
    run_id: str,
    diagnosis_id: str,
    payload: DiagnosisDecision,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Diagnosis:
    """高风险结论的人工确认入口。确认只记录决策，不触发任何平台写入。"""
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体运行不存在")
    try:
        result = decide_diagnosis(
            db,
            user.organization_id,
            diagnosis_id,
            decision=payload.decision,
            note=payload.note,
            actor=user.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if result is None or result.run_id != run_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="诊断结论不存在")
    return result


@router.get("/competitors", response_model=list[CompetitorItem])
def list_competitor_items(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
    category: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
) -> list[CompetitorItem]:
    items = list_competitors(db, user.organization_id, category=category)
    if q:
        keyword = q.strip().lower()
        items = [
            item
            for item in items
            if keyword in item["title"].lower()
            or any(keyword in point.lower() for point in item["selling_points"])
            or any(keyword in point.lower() for point in item["review_pain_points"])
        ]
    return [CompetitorItem(**item) for item in items]


@router.post("/competitors", response_model=CompetitorItem, status_code=201)
def create_competitor_item(
    payload: CompetitorCreate,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CompetitorItem:
    item = create_competitor(
        db,
        user.organization_id,
        category=payload.category,
        title=payload.title,
        price=payload.price,
        selling_points=payload.selling_points,
        review_pain_points=payload.review_pain_points,
        platform_label=payload.platform_label,
    )
    return CompetitorItem(**item)


@router.post(
    "/competitors/import-taobaoke",
    response_model=CompetitorImportResult,
    status_code=200,
)
def import_taobaoke_competitors_route(
    payload: CompetitorImportRequest,
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CompetitorImportResult:
    """从淘宝客公开商品接口导入真实竞品。

    - 凭证缺失 → 409，并在 detail 中给出配置路径，不做任何伪造；
    - 平台接口异常 → 502，带 retryable 标记供前端判断重试。
    """
    try:
        result = import_taobaoke_competitors(
            db,
            user.organization_id,
            keyword=payload.keyword,
            category=payload.category,
            limit=payload.limit,
        )
    except TaobaokeNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "taobaoke_credentials_required",
                "message": str(exc),
            },
        ) from exc
    except TaobaokeApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "taobaoke_api_error",
                "message": str(exc),
                "retryable": exc.retryable,
            },
        ) from exc
    return CompetitorImportResult(**result)
