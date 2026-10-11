"""平台无关的一次性 OAuth state（防 CSRF / 重放）机器。

淘宝、抖店、拼多多的授权流程都依赖同一套 state 机制：授权发起时写入带
TTL 的随机 state，回调时消费并校验。为避免三套平台重复实现安全关键逻辑，
这里集中实现，各平台连接模块按自己的 Platform 复用。
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import OAuthStateModel
from app.schemas.common import Platform


class OAuthStateError(RuntimeError):
    pass


def state_digest(raw_state: str) -> str:
    return hashlib.sha256(raw_state.encode()).hexdigest()


def utc_now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def create_oauth_state(
    db: Session,
    *,
    platform: Platform,
    organization_id: str,
    user_id: str,
    redirect_uri: str,
    ttl_seconds: int,
) -> tuple[str, datetime]:
    raw_state = secrets.token_urlsafe(48)
    now = utc_now()
    expires_at = now + timedelta(seconds=ttl_seconds)
    db.add(
        OAuthStateModel(
            state_hash=state_digest(raw_state),
            platform=platform.value,
            organization_id=organization_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            created_at=now,
            expires_at=expires_at,
            consumed_at=None,
        )
    )
    db.commit()
    return raw_state, expires_at


def consume_oauth_state(db: Session, platform: Platform, raw_state: str) -> OAuthStateModel:
    digest = state_digest(raw_state)
    record = db.scalar(
        select(OAuthStateModel).where(
            OAuthStateModel.state_hash == digest,
            OAuthStateModel.platform == platform.value,
        )
    )
    now = utc_now()
    if record is None:
        raise OAuthStateError("OAuth state 无效")
    if record.consumed_at is not None:
        raise OAuthStateError("OAuth state 已使用，请重新发起授权")
    if _aware(record.expires_at) <= now:
        raise OAuthStateError("OAuth state 已过期，请重新发起授权")

    result = db.execute(
        update(OAuthStateModel)
        .where(
            OAuthStateModel.state_hash == digest,
            OAuthStateModel.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    if result.rowcount != 1:
        db.rollback()
        raise OAuthStateError("OAuth state 已使用，请重新发起授权")
    db.commit()
    record.consumed_at = now
    return record
