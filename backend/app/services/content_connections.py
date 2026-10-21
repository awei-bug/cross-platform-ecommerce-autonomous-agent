"""抖音内容投稿连接的持久化与状态机。

复用平台无关的 OAuth state（open.douyin.com 用户授权），把用户 access_token 加密存入
PlatformConnectionModel（platform=douyin_content）。与抖店电商连接（platform=douyin）独立，
互不干扰：一个负责店铺商品读写，一个负责代替用户发布内容。
"""
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import PlatformConnectionModel
from app.integrations.douyin_content import DouyinContentToken
from app.schemas.common import Platform
from app.schemas.integrations import ConnectorState
from app.services.oauth_state import (
    consume_oauth_state as _consume_oauth_state,
)
from app.services.oauth_state import (
    create_oauth_state as _create_oauth_state,
)
from app.services.token_cipher import TokenCipher

DOUYIN_CONTENT_SCOPES = ["video.create", "renew_refresh_token"]


def utc_now() -> datetime:
    return datetime.now(UTC)


def missing_content_configuration(settings: Settings) -> list[str]:
    values = {
        "DOUYIN_CONTENT_CLIENT_KEY": settings.douyin_content_client_key,
        "DOUYIN_CONTENT_CLIENT_SECRET": settings.douyin_content_client_secret,
        "DOUYIN_CONTENT_REDIRECT_URI": settings.douyin_content_redirect_uri,
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
        platform=Platform.DOUYIN_CONTENT,
        organization_id=organization_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        ttl_seconds=ttl_seconds,
    )


def consume_oauth_state(db: Session, raw_state: str):
    return _consume_oauth_state(db, Platform.DOUYIN_CONTENT, raw_state)


def get_content_connection(
    db: Session, organization_id: str
) -> PlatformConnectionModel | None:
    return db.scalar(
        select(PlatformConnectionModel).where(
            PlatformConnectionModel.organization_id == organization_id,
            PlatformConnectionModel.platform == Platform.DOUYIN_CONTENT.value,
        )
    )


def save_authorized_connection(
    db: Session,
    *,
    organization_id: str,
    client_key: str,
    token: DouyinContentToken,
    cipher: TokenCipher,
) -> PlatformConnectionModel:
    now = utc_now()
    connection = get_content_connection(db, organization_id)
    if connection is None:
        connection = PlatformConnectionModel(
            id=f"conn-{uuid4().hex}",
            organization_id=organization_id,
            platform=Platform.DOUYIN_CONTENT.value,
            created_at=now,
            scopes=[],
        )
        db.add(connection)
    connection.state = ConnectorState.READY.value
    connection.app_key_reference = f"…{client_key[-6:]}" if len(client_key) > 6 else client_key
    connection.encrypted_access_token = cipher.encrypt(token.access_token)
    connection.encrypted_refresh_token = (
        cipher.encrypt(token.refresh_token) if token.refresh_token else None
    )
    connection.access_token_expires_at = token.access_token_expires_at
    connection.refresh_token_expires_at = token.refresh_token_expires_at
    connection.platform_user_id = token.open_id
    connection.platform_user_name = token.open_id
    connection.scopes = token.scopes or DOUYIN_CONTENT_SCOPES
    connection.last_error = None
    connection.authorized_at = now
    connection.revoked_at = None
    connection.updated_at = now
    db.commit()
    db.refresh(connection)
    return connection


def save_connection_error(db: Session, organization_id: str, message: str) -> None:
    now = utc_now()
    connection = get_content_connection(db, organization_id)
    if connection is None:
        connection = PlatformConnectionModel(
            id=f"conn-{uuid4().hex}",
            organization_id=organization_id,
            platform=Platform.DOUYIN_CONTENT.value,
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


def disconnect_content(db: Session, organization_id: str) -> datetime:
    now = utc_now()
    connection = get_content_connection(db, organization_id)
    if connection is None:
        connection = PlatformConnectionModel(
            id=f"conn-{uuid4().hex}",
            organization_id=organization_id,
            platform=Platform.DOUYIN_CONTENT.value,
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
    connection.authorized_at = None
    connection.last_error = None
    connection.revoked_at = now
    connection.updated_at = now
    db.commit()
    return now
