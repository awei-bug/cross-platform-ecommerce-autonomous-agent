"""Resolve explicit merchant mappings without granting business permissions.

Only call with a freshly verified MerchantSession. The result establishes an
organization boundary, not employee roles or access to every shop in that org.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MerchantOrganizationMappingModel, MerchantShopGrantModel, ShopModel
from app.services.merchant_session import MerchantSession


class MerchantScopeError(Exception):
    """No valid mapping or the requested shop is outside the mapped organization."""


@dataclass(frozen=True)
class MerchantScope:
    tenant_id: int
    staff_id: int
    organization_id: str


def resolve_merchant_scope(db: Session, merchant: MerchantSession) -> MerchantScope:
    mapping = db.scalar(
        select(MerchantOrganizationMappingModel)
        .where(
            MerchantOrganizationMappingModel.tenant_id == merchant.tenant_id,
            MerchantOrganizationMappingModel.is_active.is_(True),
        )
        .execution_options(populate_existing=True)
    )
    if mapping is None:
        raise MerchantScopeError("商家组织关联不可用")
    return MerchantScope(merchant.tenant_id, merchant.staff_id, mapping.organization_id)


def shop_belongs_to_scope(db: Session, scope: MerchantScope, shop_id: str) -> bool:
    """Check organization ownership only; caller must separately enforce permissions."""
    if not shop_id:
        return False
    return (
        db.scalar(
            select(ShopModel.id).where(
                ShopModel.id == shop_id,
                ShopModel.organization_id == scope.organization_id,
            )
        )
        is not None
    )


def has_merchant_shop_grant(db: Session, merchant: MerchantSession, shop_id: str) -> bool:
    """Check current membership and organization; caller still must authorize each action.

    The merchant must have been freshly verified by the identity service. This
    performs a new database query each time, without trusting a cached scope.
    """
    if not shop_id:
        return False
    grant = MerchantShopGrantModel
    mapping = MerchantOrganizationMappingModel
    return (
        db.scalar(
            select(grant.shop_id)
            .join(mapping, mapping.tenant_id == grant.tenant_id)
            .join(ShopModel, ShopModel.id == grant.shop_id)
            .where(
                grant.tenant_id == merchant.tenant_id,
                grant.staff_id == merchant.staff_id,
                grant.shop_id == shop_id,
                grant.is_active.is_(True),
                mapping.is_active.is_(True),
                ShopModel.organization_id == mapping.organization_id,
            )
        )
        is not None
    )
