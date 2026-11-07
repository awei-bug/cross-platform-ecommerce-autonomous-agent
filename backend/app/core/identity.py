"""Single identity source: a freshly verified 云购 (commerce) session.

Every protected business route depends on :func:`require_action` (or
:func:`require_session`). Tenant, operator and organization are derived from the
verified session plus an explicit active tenant->organization mapping; nothing
is accepted from the request body.

Fail-closed rules:
- identity service not configured        -> 503 (cannot verify, do not guess)
- identity service unreachable / 5xx     -> 503 (not a logout signal)
- missing / malformed / rejected session -> 401
- session valid but lacking the action   -> 403
- session valid but no active mapping    -> 403 (no tenant boundary, no data)

The only exception is :data:`Settings.demo_identity_fallback_enabled`, an
explicit local-development switch that is OFF by default and additionally
ignored whenever ``environment == "production"``. It exists so the pre-existing
pytest suite can keep exercising business logic without standing up a 云购
instance; it never grants action-scoped access.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.auth import UserProfile
from app.services.merchant_scope import (
    MerchantScope,
    MerchantScopeError,
    resolve_merchant_scope,
)
from app.services.merchant_session import (
    MerchantIdentityUnavailable,
    MerchantSession,
    MerchantSessionError,
    validate_merchant_session,
)

bearer = HTTPBearer(auto_error=False)

DEMO_ACCESS_TOKEN = "demo-access-token"

# 云购动作码（对齐云购 rbac.ALL_ACTION_CODES）。只引用云购真实下发的码，
# 不在本地另造权限名，避免出现第二套权限真相。
PRODUCT_READ = "product:read"
PRODUCT_WRITE = "product:write"
ORDER_SHIP = "order:ship"


@dataclass(frozen=True)
class ResolvedIdentity:
    profile: UserProfile
    # True only for the explicit local-development shortcut.
    is_dev_fallback: bool


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _dev_fallback_enabled() -> bool:
    settings = get_settings()
    return (
        settings.demo_identity_fallback_enabled
        and settings.environment.strip().lower() != "production"
    )


def _profile(session: MerchantSession, scope: MerchantScope) -> UserProfile:
    return UserProfile(
        id=f"staff-{session.tenant_id}-{session.staff_id}",
        name=session.staff_name or f"云购员工 {session.staff_id}",
        role_name=session.role_name or ("超级管理员" if session.is_super else "云购员工"),
        organization_id=scope.organization_id,
        permissions=sorted(session.actions),
        is_super=session.is_super,
    )


def _scope_for(db: Session, session: MerchantSession) -> MerchantScope:
    try:
        return resolve_merchant_scope(db, session)
    except MerchantScopeError:
        # No active tenant->organization mapping: refuse rather than fall back to
        # a default organization, which would leak another tenant's data.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="商家组织关联未启用，请联系管理员开通",
        ) from None


def resolve_identity(
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> ResolvedIdentity:
    if (
        _dev_fallback_enabled()
        and credentials is not None
        and credentials.credentials == DEMO_ACCESS_TOKEN
    ):
        from app.services.mock_repository import DEMO_USER

        return ResolvedIdentity(DEMO_USER, True)

    settings = get_settings()
    if credentials is None or not credentials.credentials:
        raise _unauthorized("请使用云购账号登录")
    if not settings.merchant_identity_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="商家身份服务未配置",
        )
    try:
        session = validate_merchant_session(
            settings.merchant_identity_url, credentials.credentials
        )
    except MerchantIdentityUnavailable:
        # 上游挂了不等于登录过期。返回 503，前端不得据此清空本地令牌。
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="云购身份服务暂时不可用，请稍后重试",
        ) from None
    except MerchantSessionError:
        raise _unauthorized("云购会话无效或无法验证") from None
    return ResolvedIdentity(_profile(session, _scope_for(db, session)), False)


def _check_action(identity: ResolvedIdentity, action: str) -> None:
    if identity.is_dev_fallback:
        return
    profile = identity.profile
    if profile.is_super or action in profile.permissions:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"没有 {action} 权限",
    )


def require_action(action: str) -> Callable[..., UserProfile]:
    """Build a dependency that enforces one 云购 action code."""

    def dependency(
        response: Response,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        db: Annotated[Session, Depends(get_db)],
    ) -> UserProfile:
        response.headers["Cache-Control"] = "no-store"
        identity = resolve_identity(credentials, db)
        _check_action(identity, action)
        return identity.profile

    return dependency


def require_session(
    response: Response,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> UserProfile:
    """Authenticated identity without an action check (e.g. /auth/me)."""
    response.headers["Cache-Control"] = "no-store"
    return resolve_identity(credentials, db).profile

