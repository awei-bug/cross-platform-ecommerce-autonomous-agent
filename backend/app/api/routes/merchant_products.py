"""Read-only product access for explicitly authorized demo merchant shops."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    MerchantOrganizationMappingModel,
    MerchantShopGrantModel,
    ProductModel,
    ShopModel,
)
from app.db.session import get_db
from app.services.merchant_session import (
    MerchantSession,
    MerchantSessionError,
    validate_merchant_session,
)

router = APIRouter(prefix="/merchant-products", tags=["merchant-products"])
bearer = HTTPBearer(auto_error=False)


def require_product_reader(
    response: Response,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> MerchantSession:
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    if not settings.merchant_product_read_enabled:
        raise HTTPException(status_code=404, detail="功能未启用")
    if not settings.merchant_identity_url:
        raise HTTPException(status_code=503, detail="商家身份服务未配置")
    if credentials is None:
        raise HTTPException(status_code=401, detail="请使用商家账号登录")
    try:
        merchant = validate_merchant_session(
            settings.merchant_identity_url, credentials.credentials
        )
    except MerchantSessionError:
        raise HTTPException(status_code=401, detail="商家会话无效或无法验证") from None
    if "product:read" not in merchant.actions:
        raise HTTPException(status_code=403, detail="没有商品查看权限")
    return merchant


def authorized_shops(merchant: MerchantSession):
    grant, mapping = MerchantShopGrantModel, MerchantOrganizationMappingModel
    return (
        select(ShopModel.id, ShopModel.name, ShopModel.platform_label)
        .join(mapping, mapping.organization_id == ShopModel.organization_id)
        .join(grant, and_(grant.tenant_id == mapping.tenant_id, grant.shop_id == ShopModel.id))
        .where(
            ShopModel.data_source == "seeded",
            mapping.tenant_id == merchant.tenant_id,
            mapping.is_active.is_(True),
            grant.staff_id == merchant.staff_id,
            grant.is_active.is_(True),
            grant.can_read_products.is_(True),
        )
    )


@router.get("/shops/list")
def list_merchant_shops(
    db: Annotated[Session, Depends(get_db)],
    merchant: Annotated[MerchantSession, Depends(require_product_reader)],
    after: Annotated[str, Query(max_length=64)] = "",
) -> dict:
    rows = db.execute(
        authorized_shops(merchant).where(ShopModel.id > after).order_by(ShopModel.id).limit(101)
    ).all()
    items = [{"id": row.id, "name": row.name, "platform": row.platform_label} for row in rows[:100]]
    return {"items": items, "next_after": items[-1]["id"] if len(rows) > 100 else None}


@router.get("/{shop_id}")
def list_merchant_products(
    shop_id: str,
    db: Annotated[Session, Depends(get_db)],
    merchant: Annotated[MerchantSession, Depends(require_product_reader)],
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    if not shop_id or len(shop_id) > 64:
        raise HTTPException(status_code=404, detail="店铺不可用")

    grant, mapping = MerchantShopGrantModel, MerchantOrganizationMappingModel
    if db.execute(authorized_shops(merchant).where(ShopModel.id == shop_id)).first() is None:
        raise HTTPException(status_code=404, detail="店铺不可用")
    # Repeat all grant conditions inside the product query: revocation between
    # the scope check and the read must not return newly unauthorized rows.
    rows = db.scalars(
        select(ProductModel)
        .join(
            ShopModel,
            and_(
                ShopModel.id == ProductModel.shop_id,
                ShopModel.organization_id == ProductModel.organization_id,
            ),
        )
        .join(mapping, mapping.organization_id == ShopModel.organization_id)
        .join(grant, and_(grant.tenant_id == mapping.tenant_id, grant.shop_id == ShopModel.id))
        .where(
            ShopModel.id == shop_id,
            ShopModel.data_source == "seeded",
            mapping.tenant_id == merchant.tenant_id,
            mapping.is_active.is_(True),
            grant.staff_id == merchant.staff_id,
            grant.is_active.is_(True),
            grant.can_read_products.is_(True),
        )
        .order_by(ProductModel.id)
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
    ).all()
    return {
        "items": [
            {
                "id": item.id,
                "sku": item.sku,
                "title": item.title,
                "price": item.price,
                "stock": item.stock,
                "status": item.status,
                "updated_at": item.updated_at,
            }
            for item in rows[:page_size]
        ],
        "page": page,
        "has_more": len(rows) > page_size,
        "is_demo": True,
    }
