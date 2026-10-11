"""抖店连接的持久化与状态机：复用平台无关的 OAuth state，单独保存加密 Token 与店铺身份。"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import PlatformConnectionModel
from app.integrations.douyin import DouyinToken, SellerIdentity
from app.schemas.common import Platform
from app.schemas.integrations import ConnectorState
from app.services.oauth_state import (
    consume_oauth_state as _consume_oauth_state,
)
from app.services.oauth_state import (
    create_oauth_state as _create_oauth_state,
)
from app.services.token_cipher import TokenCipher

DOUYIN_READ_SCOPES = ["shop.order", "shop.product"]


def utc_now() -> datetime:
    return datetime.now(UTC)


def missing_douyin_configuration(settings: Settings) -> list[str]:
    values = {
        "DOUYIN_APP_KEY": settings.douyin_app_key,
        "DOUYIN_APP_SECRET": settings.douyin_app_secret,
        "DOUYIN_REDIRECT_URI": settings.douyin_redirect_uri,
        "TOKEN_ENCRYPTION_KEYS": settings.token_encryption_keys,
    }
    return [name for name, value in values.items() if not value]


def create_oauth_state(
    db: Session,
    *,
    organization_id: str,
    user_id: str,
    redirect_uri: str,
    ttl_seconds: int,
) -> tuple[str, datetime]:
    return _create_oauth_state(
        db,
        platform=Platform.DOUYIN,
        organization_id=organization_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        ttl_seconds=ttl_seconds,
    )


def consume_oauth_state(db: Session, raw_state: str):
    return _consume_oauth_state(db, Platform.DOUYIN, raw_state)


def get_douyin_connection(db: Session, organization_id: str) -> PlatformConnectionModel | None:
    return db.scalar(
        select(PlatformConnectionModel).where(
            PlatformConnectionModel.organization_id == organization_id,
            PlatformConnectionModel.platform == Platform.DOUYIN.value,
        )
    )


def save_authorized_connection(
    db: Session,
    *,
    organization_id: str,
    app_key: str,
    token: DouyinToken,
    identity: SellerIdentity,
    cipher: TokenCipher,
) -> PlatformConnectionModel:
    now = utc_now()
    connection = get_douyin_connection(db, organization_id)
    if connection is None:
        connection = PlatformConnectionModel(
            id=f"conn-{uuid4().hex}",
            organization_id=organization_id,
            platform=Platform.DOUYIN.value,
            created_at=now,
            scopes=[],
        )
        db.add(connection)
    connection.state = ConnectorState.READY.value
    connection.app_key_reference = f"…{app_key[-6:]}" if len(app_key) > 6 else app_key
    connection.encrypted_access_token = cipher.encrypt(token.access_token)
    connection.encrypted_refresh_token = (
        cipher.encrypt(token.refresh_token) if token.refresh_token else None
    )
    connection.access_token_expires_at = token.access_token_expires_at
    connection.refresh_token_expires_at = token.refresh_token_expires_at
    connection.platform_user_id = identity.user_id
    connection.platform_user_name = identity.user_name
    connection.platform_shop_id = identity.shop_id
    connection.platform_shop_name = identity.shop_name
    connection.scopes = token.scopes or DOUYIN_READ_SCOPES
    connection.last_error = None
    connection.authorized_at = now
    connection.revoked_at = None
    connection.updated_at = now
    db.commit()
    db.refresh(connection)
    return connection


def save_connection_error(db: Session, organization_id: str, message: str) -> None:
    now = utc_now()
    connection = get_douyin_connection(db, organization_id)
    if connection is None:
        connection = PlatformConnectionModel(
            id=f"conn-{uuid4().hex}",
            organization_id=organization_id,
            platform=Platform.DOUYIN.value,
            state=ConnectorState.ERROR.value,
            scopes=[],
            created_at=now,
            updated_at=now,
        )
        db.add(connection)
    connection.state = ConnectorState.ERROR.value
    connection.last_error = message[:1000]
    connection.updated_at = now
    db.commit()


def disconnect_douyin(db: Session, organization_id: str) -> datetime:
    now = utc_now()
    connection = get_douyin_connection(db, organization_id)
    if connection is None:
        connection = PlatformConnectionModel(
            id=f"conn-{uuid4().hex}",
            organization_id=organization_id,
            platform=Platform.DOUYIN.value,
            state=ConnectorState.REVOKED.value,
            scopes=[],
            created_at=now,
            updated_at=now,
        )
        db.add(connection)
    connection.state = ConnectorState.REVOKED.value
    connection.encrypted_access_token = None
    connection.encrypted_refresh_token = None
    connection.access_token_expires_at = None
    connection.refresh_token_expires_at = None
    connection.last_error = None
    connection.revoked_at = now
    connection.updated_at = now
    db.commit()
    return now
