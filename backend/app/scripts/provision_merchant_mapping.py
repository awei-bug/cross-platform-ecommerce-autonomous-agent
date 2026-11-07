"""Local operator tool: preview or create a disabled merchant/organization mapping.

The operator must independently verify the merchant's entitlement to the shop.
This command does not expose a network endpoint or initialize the database.
"""

import argparse
import getpass
import json
import sys

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import MerchantOrganizationMappingModel, ShopModel
from app.db.session import get_engine
from app.services.merchant_access_management import AccessManagementError, provision_mapping
from app.services.merchant_session import MerchantSessionError, validate_merchant_session


def _is_postgres(engine) -> bool:
    return engine.dialect.name == "postgresql"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="核对商家和店铺，创建默认停用的组织关联")
    parser.add_argument("--shop-id", required=True, help="已核实归属的跨境店铺 ID")
    parser.add_argument("--apply", action="store_true", help="实际写入；缺省只预览")
    parser.add_argument("--confirm-organization", help="写入时必须与预览的组织 ID 一致")
    args = parser.parse_args(argv)
    if not args.shop_id.strip() or len(args.shop_id) > 64:
        parser.error("店铺 ID 无效")
    if args.apply and not args.confirm_organization:
        parser.error("写入时必须提供预览得到的 --confirm-organization")
    settings = get_settings()
    if not settings.merchant_identity_url:
        print("未配置 MERCHANT_IDENTITY_URL", file=sys.stderr)
        return 1
    token = (
        getpass.getpass("云购管理员令牌：") if sys.stdin.isatty() else sys.stdin.readline().strip()
    )
    try:
        merchant = validate_merchant_session(settings.merchant_identity_url, token)
    except MerchantSessionError:
        print("无法验证商家会话", file=sys.stderr)
        return 1
    if not merchant.is_super:
        print("需要云购商家管理员权限", file=sys.stderr)
        return 1
    try:
        engine = get_engine()
        if not _is_postgres(engine):
            print("映射管理需要 PostgreSQL", file=sys.stderr)
            return 1
        with Session(engine) as db:
            try:
                shop = db.scalar(select(ShopModel).where(ShopModel.id == args.shop_id))
                if shop is None:
                    raise AccessManagementError("店铺不存在")
                existing = db.get(MerchantOrganizationMappingModel, merchant.tenant_id)
                owner = db.scalar(
                    select(MerchantOrganizationMappingModel.tenant_id).where(
                        MerchantOrganizationMappingModel.organization_id == shop.organization_id
                    )
                )
                if existing or owner is not None:
                    raise AccessManagementError("商家或组织已有映射，不能覆盖")
                organization_id = shop.organization_id
                if args.apply:
                    if args.confirm_organization != organization_id:
                        raise AccessManagementError("确认的组织 ID 与当前店铺不一致")
                    mapping = provision_mapping(
                        db,
                        merchant.tenant_id,
                        shop.id,
                        actor=f"merchant:{merchant.tenant_id}:{merchant.staff_id}",
                    )
                    # Recheck under the shop lock to prevent stale preview changes.
                    if mapping.organization_id != args.confirm_organization:
                        raise AccessManagementError("店铺组织已变化，请重新预览")
                    try:
                        latest = validate_merchant_session(settings.merchant_identity_url, token)
                    except MerchantSessionError:
                        raise AccessManagementError("无法重新验证商家管理员身份") from None
                    if not latest.is_super or (latest.tenant_id, latest.staff_id) != (
                        merchant.tenant_id,
                        merchant.staff_id,
                    ):
                        raise AccessManagementError("商家管理员身份已变化")
                    db.commit()
                else:
                    db.rollback()
                print(
                    json.dumps(
                        {
                            "mode": "created" if args.apply else "preview",
                            "tenant_id": merchant.tenant_id,
                            "tenant_slug": merchant.tenant_slug,
                            "shop_id": args.shop_id,
                            "organization_id": organization_id,
                            "mapping_active": False,
                            "notice": "操作员须独立核实商家对该店铺的归属；系统未验证店铺所有权。",
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
            except (AccessManagementError, SQLAlchemyError) as exc:
                db.rollback()
                print(
                    str(exc)
                    if isinstance(exc, AccessManagementError)
                    else "数据库操作失败或映射冲突",
                    file=sys.stderr,
                )
                return 1
    except SQLAlchemyError:
        print("数据库连接失败", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
