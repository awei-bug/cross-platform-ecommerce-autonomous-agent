from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import require_demo_user
from app.db.session import get_db
from app.schemas.common import Platform
from app.schemas.products import (
    BatchActionRequest,
    BatchJob,
    ProductDetail,
    ProductListResponse,
    ProductRisk,
    ProductStatus,
)
from app.services.product_repository import (
    create_batch_job,
    get_batch_job,
    get_product,
    list_products,
    retry_batch_job,
)

router = APIRouter(
    prefix="/products",
    tags=["products"],
    dependencies=[Depends(require_demo_user)],
)


@router.get("", response_model=ProductListResponse)
def products(
    db: Annotated[Session, Depends(get_db)],
    shop_id: Annotated[str, Query()] = "shop-all",
    platform: Annotated[Platform, Query()] = Platform.ALL,
    q: Annotated[str, Query(max_length=100)] = "",
    product_status: Annotated[ProductStatus | None, Query(alias="status")] = None,
    risk: Annotated[ProductRisk | None, Query()] = None,
    sort_by: Annotated[str, Query()] = "risk",
    sort_order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> ProductListResponse:
    return list_products(
        db,
        shop_id=shop_id,
        platform=platform,
        q=q,
        status=product_status,
        risk=risk,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get("/{product_id}", response_model=ProductDetail)
def product_detail(
    product_id: str, db: Annotated[Session, Depends(get_db)]
) -> ProductDetail:
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return product


@router.post("/batch-actions", response_model=BatchJob, status_code=status.HTTP_202_ACCEPTED)
def batch_action(
    request: BatchActionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> BatchJob:
    return create_batch_job(db, request)


@router.get("/jobs/{job_id}", response_model=BatchJob)
def batch_job(job_id: str, db: Annotated[Session, Depends(get_db)]) -> BatchJob:
    job = get_batch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批量任务不存在")
    return job


@router.post("/jobs/{job_id}/retry", response_model=BatchJob)
def retry_job(job_id: str, db: Annotated[Session, Depends(get_db)]) -> BatchJob:
    job = retry_batch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批量任务不存在")
    return job
