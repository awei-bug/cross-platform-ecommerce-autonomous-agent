from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import require_demo_user
from app.db.session import get_db
from app.schemas.common import Platform
from app.schemas.orders import (
    AfterSaleStatus,
    OrderActionJob,
    OrderActionRequest,
    OrderAuditEntry,
    OrderDetail,
    OrderListResponse,
    OrderRisk,
    OrderStatus,
)
from app.services.order_repository import (
    create_action_job,
    get_action_job,
    get_order,
    list_audit_entries,
    list_orders,
)

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
    dependencies=[Depends(require_demo_user)],
)


@router.get("", response_model=OrderListResponse)
def orders(
    shop_id: Annotated[str, Query()] = "shop-all",
    platform: Annotated[Platform, Query()] = Platform.ALL,
    q: Annotated[str, Query(max_length=100)] = "",
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
    after_sale_status: Annotated[AfterSaleStatus | None, Query()] = None,
    risk: Annotated[OrderRisk | None, Query()] = None,
    sla: Annotated[str, Query(pattern="^(|overdue|two_hours|today)$")] = "",
    sort_by: Annotated[str, Query()] = "risk",
    sort_order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> OrderListResponse:
    return list_orders(
        shop_id=shop_id,
        platform=platform,
        q=q,
        order_status=order_status,
        after_sale_status=after_sale_status,
        risk=risk,
        sla=sla,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.post("/actions", response_model=OrderActionJob, status_code=status.HTTP_202_ACCEPTED)
def order_action(
    request: OrderActionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> OrderActionJob:
    job = create_action_job(db, request)
    if job.total == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有找到可处理订单")
    return job


@router.get("/jobs/{job_id}", response_model=OrderActionJob)
def action_job(job_id: str, db: Annotated[Session, Depends(get_db)]) -> OrderActionJob:
    job = get_action_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单任务不存在")
    return job


@router.get("/audit", response_model=list[OrderAuditEntry])
def audit_entries(
    db: Annotated[Session, Depends(get_db)],
    order_id: Annotated[str | None, Query()] = None,
) -> list[OrderAuditEntry]:
    return list_audit_entries(db, order_id)


@router.get("/{order_id}", response_model=OrderDetail)
def order_detail(order_id: str, db: Annotated[Session, Depends(get_db)]) -> OrderDetail:
    order = get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return order
