"""Opt-in administration for explicitly provisioned merchant mappings."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import MerchantAccessAuditModel, MerchantOrganizationMappingModel
from app.db.session import get_db
from app.services.merchant_access_management import (
    AccessManagementError,
    set_mapping_active,
    set_product_read_permission,
    set_shop_grant_active,
)
from app.services.merchant_session import (
    MerchantSession,
    MerchantSessionError,
    validate_merchant_session,
    validate_merchant_staff,
)

router = APIRouter(prefix="/merchant-access", tags=["merchant-access"])
bearer = HTTPBearer(auto_error=False)


class ChangeState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: StrictBool


def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> tuple[MerchantSession, str, str]:
    settings = get_settings()
    if not settings.merchant_access_admin_enabled:
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
    if not merchant.is_super:
        raise HTTPException(status_code=403, detail="需要商家管理员权限")
    return merchant, credentials.credentials, settings.merchant_identity_url


def require_postgres(db: Session) -> None:
    if db.get_bind().dialect.name != "postgresql":
        raise HTTPException(status_code=503, detail="授权管理需要支持行锁的 PostgreSQL 数据库")


Admin = Annotated[tuple[MerchantSession, str, str], Depends(require_admin)]
Database = Annotated[Session, Depends(get_db)]


def verify_target(admin: tuple[MerchantSession, str, str], staff_id: int) -> None:
    merchant, token, identity_url = admin
    try:
        validate_merchant_staff(identity_url, token, merchant.tenant_id, staff_id)
        latest = validate_merchant_session(identity_url, token)
    except MerchantSessionError:
        raise HTTPException(status_code=403, detail="无法验证目标员工归属") from None
    if (
        not latest.is_super
        or latest.tenant_id != merchant.tenant_id
        or latest.staff_id != merchant.staff_id
    ):
        raise HTTPException(status_code=403, detail="管理员权限已变化，请重新登录")


@router.get("/mapping")
def get_mapping(admin: Admin, db: Database) -> dict:
    merchant, _, _ = admin
    mapping = db.get(MerchantOrganizationMappingModel, merchant.tenant_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="商家组织关联不存在")
    return {"organization_id": mapping.organization_id, "active": mapping.is_active}


@router.put("/mapping")
def change_mapping(body: ChangeState, admin: Admin, db: Database) -> dict:
    require_postgres(db)
    merchant, _, _ = admin
    try:
        set_mapping_active(
            db,
            merchant.tenant_id,
            body.active,
            actor=f"merchant:{merchant.tenant_id}:{merchant.staff_id}",
        )
        db.commit()
    except AccessManagementError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception:
        db.rollback()
        raise
    return {"active": body.active}


@router.put("/shops/{shop_id}/staff/{staff_id}")
def change_shop_grant(
    shop_id: str, staff_id: int, body: ChangeState, admin: Admin, db: Database
) -> dict:
    require_postgres(db)
    merchant, _, _ = admin
    if staff_id <= 0 or not shop_id or len(shop_id) > 64:
        raise HTTPException(status_code=422, detail="员工或店铺无效")
    if body.active:
        verify_target(admin, staff_id)
    try:
        set_shop_grant_active(
            db,
            merchant.tenant_id,
            staff_id,
            shop_id,
            body.active,
            actor=f"merchant:{merchant.tenant_id}:{merchant.staff_id}",
        )
        db.commit()
    except AccessManagementError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception:
        db.rollback()
        raise
    return {"staff_id": staff_id, "shop_id": shop_id, "active": body.active}


@router.put("/shops/{shop_id}/staff/{staff_id}/product-read")
def change_product_read(
    shop_id: str, staff_id: int, body: ChangeState, admin: Admin, db: Database
) -> dict:
    require_postgres(db)
    merchant, _, _ = admin
    if staff_id <= 0 or not shop_id or len(shop_id) > 64:
        raise HTTPException(status_code=422, detail="员工或店铺无效")
    if body.active:
        verify_target(admin, staff_id)
    try:
        set_product_read_permission(
            db,
            merchant.tenant_id,
            staff_id,
            shop_id,
            body.active,
            actor=f"merchant:{merchant.tenant_id}:{merchant.staff_id}",
        )
        db.commit()
    except AccessManagementError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception:
        db.rollback()
        raise
    return {"staff_id": staff_id, "shop_id": shop_id, "product_read": body.active}


@router.get("/audit")
def get_access_audit(admin: Admin, db: Database) -> list[dict]:
    merchant, _, _ = admin
    rows = db.scalars(
        select(MerchantAccessAuditModel)
        .where(MerchantAccessAuditModel.tenant_id == merchant.tenant_id)
        .order_by(MerchantAccessAuditModel.created_at.desc(), MerchantAccessAuditModel.id.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": row.id,
            "actor": row.actor,
            "action": row.action,
            "staff_id": row.target_staff_id,
            "shop_id": row.target_shop_id,
            "before": row.before,
            "after": row.after,
            "created_at": row.created_at,
        }
        for row in rows
    ]
