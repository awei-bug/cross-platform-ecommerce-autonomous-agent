from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.identity import PRODUCT_READ, PRODUCT_WRITE, require_action
from app.db.models import ProductModel, ShopModel
from app.db.session import get_db
from app.schemas.auth import UserProfile
from app.schemas.common import Platform
from app.schemas.products import (
    BatchActionRequest,
    BatchJob,
    HubBindingRequest,
    HubProductPreview,
    ProductDetail,
    ProductListResponse,
    ProductRisk,
    ProductStatus,
)
from app.services.hub_client import HubError, _request, hub_enabled
from app.services.product_repository import (
    create_batch_job,
    get_batch_job,
    get_product,
    list_products,
    retry_batch_job,
)

router = APIRouter(prefix="/products", tags=["products"])
# 读操作与写操作分别校验云购动作码，不再依赖固定演示令牌。
ProductReader = Annotated[UserProfile, Depends(require_action(PRODUCT_READ))]
ProductWriter = Annotated[UserProfile, Depends(require_action(PRODUCT_WRITE))]


def _scoped_product(db: Session, product_id: str, organization_id: str) -> ProductModel:
    product = db.scalar(
        select(ProductModel).where(
            ProductModel.id == product_id,
            ProductModel.organization_id == organization_id,
        )
    )
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    shop = db.scalar(
        select(ShopModel).where(
            ShopModel.id == product.shop_id,
            ShopModel.organization_id == organization_id,
        )
    )
    if shop is None or shop.data_source != "seeded":
        raise HTTPException(
            status_code=403, detail="当前仅支持演示店铺绑定，真实店铺需要正式权限和租户隔离"
        )
    return product


def _preview_hub_product(external_id: str) -> HubProductPreview:
    external_id = external_id.strip()
    if (
        not external_id
        or external_id in {".", ".."}
        or len(external_id) > 128
        or "/" in external_id
        or "\\" in external_id
    ):
        raise HTTPException(status_code=422, detail="请输入有效的商品数据中心 ID")
    if not hub_enabled():
        raise HTTPException(status_code=503, detail="商品数据中心未配置")
    from app.core.config import get_settings

    tenant = get_settings().data_hub_tenant_slug
    try:
        payload = _request(
            "GET", f"/hub/products/{quote(tenant, safe='')}/{quote(external_id, safe='')}"
        )
    except HubError as exc:
        if str(exc).startswith("data-hub 返回 404:"):
            raise HTTPException(status_code=404, detail="数据中心中没有该商品") from exc
        raise HTTPException(status_code=503, detail="商品数据中心不可用，请稍后重试") from exc
    item = payload.get("item")
    if (
        not isinstance(item, dict)
        or item.get("external_id") != external_id
        or not item.get("title")
    ):
        raise HTTPException(status_code=502, detail="商品数据中心返回的数据无效")
    if item.get("status") == "archived":
        raise HTTPException(status_code=409, detail="该商品已归档，不能绑定")
    return HubProductPreview(
        external_id=external_id,
        title=item["title"],
        status=item.get("status") or "",
        selling_points=item.get("selling_points") or [],
    )


@router.get("/{product_id}/hub-preview", response_model=HubProductPreview)
def preview_hub_product(
    product_id: str,
    external_id: Annotated[str, Query(min_length=1, max_length=128)],
    user: ProductReader,
    db: Annotated[Session, Depends(get_db)],
) -> HubProductPreview:
    _scoped_product(db, product_id, user.organization_id)
    return _preview_hub_product(external_id)


@router.put("/{product_id}/hub-binding")
def update_hub_binding(
    product_id: str,
    request: HubBindingRequest,
    user: ProductWriter,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    organization_id = user.organization_id
    product = _scoped_product(db, product_id, organization_id)
    target = request.hub_product_id.strip() if request.hub_product_id is not None else None
    if target is not None:
        _preview_hub_product(target)
    result = db.execute(
        update(ProductModel)
        .where(
            ProductModel.id == product.id,
            ProductModel.organization_id == organization_id,
            ProductModel.hub_product_id == request.expected_hub_product_id,
        )
        .values(hub_product_id=target)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="绑定已被其他操作修改，请刷新后重试")
    db.commit()
    return {"hub_product_id": target}


@router.get("", response_model=ProductListResponse)
def products(
    user: ProductReader,
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
        organization_id=user.organization_id,
    )


@router.get("/{product_id}", response_model=ProductDetail)
def product_detail(
    product_id: str,
    user: ProductReader,
    db: Annotated[Session, Depends(get_db)],
) -> ProductDetail:
    product = get_product(db, product_id, organization_id=user.organization_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return product


@router.post("/batch-actions", response_model=BatchJob, status_code=status.HTTP_202_ACCEPTED)
def batch_action(
    request: BatchActionRequest,
    user: ProductWriter,
    db: Annotated[Session, Depends(get_db)],
) -> BatchJob:
    return create_batch_job(db, request, organization_id=user.organization_id)


@router.get("/jobs/{job_id}", response_model=BatchJob)
def batch_job(
    job_id: str,
    user: ProductReader,
    db: Annotated[Session, Depends(get_db)],
) -> BatchJob:
    job = get_batch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批量任务不存在")
    return job


@router.post("/jobs/{job_id}/retry", response_model=BatchJob)
def retry_job(
    job_id: str,
    user: ProductWriter,
    db: Annotated[Session, Depends(get_db)],
) -> BatchJob:
    job = retry_batch_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批量任务不存在")
    return job
