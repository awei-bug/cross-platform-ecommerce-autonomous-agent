"""Transactional primitives for access administration, not public endpoints.

The caller must authenticate/authorize the administrator and validate staff
membership independently. The caller owns the transaction and must roll back
on any error. PostgreSQL row locks serialize changes to the same mapping.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    MerchantAccessAuditModel,
    MerchantOrganizationMappingModel,
    MerchantShopGrantModel,
    ShopModel,
)


class AccessManagementError(ValueError):
    pass


def _actor(actor: str) -> str:
    if not isinstance(actor, str) or not actor.strip() or len(actor.strip()) > 128:
        raise AccessManagementError("缺少有效的操作人")
    return actor.strip()


def _locked_mapping(db: Session, tenant_id: int) -> MerchantOrganizationMappingModel:
    mapping = db.scalar(
        select(MerchantOrganizationMappingModel)
        .where(MerchantOrganizationMappingModel.tenant_id == tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if mapping is None:
        raise AccessManagementError("商家组织关联不存在")
    return mapping


def _audit(db, tenant_id, actor, action, before, after, staff_id=None, shop_id=None):
    db.add(
        MerchantAccessAuditModel(
            id=str(uuid4()),
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            target_staff_id=staff_id,
            target_shop_id=shop_id,
            before=before,
            after=after,
            created_at=datetime.now(UTC),
        )
    )


def provision_mapping(
    db: Session, tenant_id: int, shop_id: str, *, actor: str
) -> MerchantOrganizationMappingModel:
    """Create a disabled mapping after a trusted operator has verified ownership.

    Shop existence establishes only that an organization exists. The caller
    must independently verify that the merchant is entitled to this shop.
    """
    actor = _actor(actor)
    if type(tenant_id) is not int or tenant_id <= 0 or not isinstance(shop_id, str) or not shop_id:
        raise AccessManagementError("租户或店铺无效")
    shop = db.scalar(
        select(ShopModel)
        .where(ShopModel.id == shop_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if shop is None or not shop.organization_id.strip():
        raise AccessManagementError("店铺或组织不存在")
    if db.get(MerchantOrganizationMappingModel, tenant_id) is not None:
        raise AccessManagementError("商家组织关联已存在")
    if (
        db.scalar(
            select(MerchantOrganizationMappingModel.tenant_id).where(
                MerchantOrganizationMappingModel.organization_id == shop.organization_id
            )
        )
        is not None
    ):
        raise AccessManagementError("该组织已有商家关联")
    mapping = MerchantOrganizationMappingModel(
        tenant_id=tenant_id, organization_id=shop.organization_id, is_active=False
    )
    db.add(mapping)
    _audit(
        db,
        tenant_id,
        actor,
        "mapping_create",
        {},
        {"organization_id": shop.organization_id, "active": False, "method": "local_operator"},
        shop_id=shop.id,
    )
    db.flush()
    return mapping


def set_mapping_active(db: Session, tenant_id: int, active: bool, *, actor: str) -> None:
    """Change an existing mapping and revoke every active shop grant on transition."""
    actor = _actor(actor)
    if type(active) is not bool:
        raise AccessManagementError("状态无效")
    mapping = _locked_mapping(db, tenant_id)
    if mapping.is_active == active:
        return
    grants = db.scalars(
        select(MerchantShopGrantModel)
        .where(
            MerchantShopGrantModel.tenant_id == tenant_id,
            MerchantShopGrantModel.is_active.is_(True),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    for grant in grants:
        before_read = grant.can_read_products
        grant.is_active = False
        grant.can_read_products = False
        _audit(
            db,
            tenant_id,
            actor,
            "grant_revoke",
            {"active": True, "can_read_products": before_read},
            {"active": False, "can_read_products": False},
            grant.staff_id,
            grant.shop_id,
        )
    _audit(db, tenant_id, actor, "mapping_state", {"active": mapping.is_active}, {"active": active})
    mapping.is_active = active
    db.flush()


def set_shop_grant_active(
    db: Session, tenant_id: int, staff_id: int, shop_id: str, active: bool, *, actor: str
) -> None:
    """Change one employee's shop membership after the caller verifies that employee."""
    actor = _actor(actor)
    if type(staff_id) is not int or staff_id <= 0 or type(active) is not bool or not shop_id:
        raise AccessManagementError("授权参数无效")
    mapping = _locked_mapping(db, tenant_id)
    if active and not mapping.is_active:
        raise AccessManagementError("商家组织关联未启用")
    if (
        active
        and db.scalar(
            select(ShopModel.id).where(
                ShopModel.id == shop_id, ShopModel.organization_id == mapping.organization_id
            )
        )
        is None
    ):
        raise AccessManagementError("店铺不属于关联组织")
    grant = db.scalar(
        select(MerchantShopGrantModel)
        .where(
            MerchantShopGrantModel.tenant_id == tenant_id,
            MerchantShopGrantModel.staff_id == staff_id,
            MerchantShopGrantModel.shop_id == shop_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if grant is None:
        if not active:
            return
        grant = MerchantShopGrantModel(
            tenant_id=tenant_id,
            staff_id=staff_id,
            shop_id=shop_id,
            is_active=False,
            can_read_products=False,
        )
        db.add(grant)
    if grant.is_active == active:
        return
    previous_read = grant.can_read_products
    _audit(
        db,
        tenant_id,
        actor,
        "grant_state",
        {"active": grant.is_active, "can_read_products": previous_read},
        {"active": active, "can_read_products": False},
        staff_id,
        shop_id,
    )
    grant.is_active = active
    grant.can_read_products = False
    db.flush()


def set_product_read_permission(
    db: Session, tenant_id: int, staff_id: int, shop_id: str, allowed: bool, *, actor: str
) -> None:
    """Explicit product read permission on an already active shop membership."""
    actor = _actor(actor)
    if type(staff_id) is not int or staff_id <= 0 or type(allowed) is not bool or not shop_id:
        raise AccessManagementError("授权参数无效")
    mapping = _locked_mapping(db, tenant_id)
    grant = db.scalar(
        select(MerchantShopGrantModel)
        .where(
            MerchantShopGrantModel.tenant_id == tenant_id,
            MerchantShopGrantModel.staff_id == staff_id,
            MerchantShopGrantModel.shop_id == shop_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if grant is None or not grant.is_active:
        raise AccessManagementError("员工没有启用的店铺授权")
    if allowed:
        shop = db.scalar(select(ShopModel).where(ShopModel.id == shop_id))
        if not mapping.is_active or shop is None or shop.organization_id != mapping.organization_id:
            raise AccessManagementError("商家组织关联或店铺不可用")
        if shop.data_source != "seeded":
            raise AccessManagementError("当前仅支持演示店铺商品权限")
    if grant.can_read_products == allowed:
        return
    _audit(
        db,
        tenant_id,
        actor,
        "product_read",
        {"allowed": grant.can_read_products},
        {"allowed": allowed},
        staff_id,
        shop_id,
    )
    grant.can_read_products = allowed
    db.flush()
