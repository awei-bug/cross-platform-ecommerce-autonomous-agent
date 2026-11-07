"""Validate a merchant session against the configured commerce service.

The commerce (云购) account is the single source of identity: tenant, staff and
action codes come from a freshly verified session, never from a request body.
Organization scope still requires an explicit, active tenant->organization
mapping (see app.services.merchant_scope).
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


class MerchantSessionError(Exception):
    """A session is invalid or cannot be verified; never contains credentials."""


@dataclass(frozen=True)
class MerchantSession:
    tenant_id: int
    tenant_slug: str
    staff_id: int
    actions: frozenset[str]
    is_super: bool
    # 展示与审计用的身份标签，同样只来自已验证响应；缺失时由调用方派生。
    staff_name: str | None = None
    role_name: str | None = None


def _validate_url(base_url: str) -> str:
    try:
        parsed = urlsplit(base_url.strip())
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise MerchantSessionError("商家身份服务地址无效") from exc
    if (
        not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or parsed.scheme not in ("http", "https")
        or (parsed.scheme == "http" and host not in ("127.0.0.1", "::1", "localhost"))
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise MerchantSessionError("商家身份服务地址无效")
    return base_url.strip().rstrip("/")


def validate_merchant_session(
    base_url: str, token: str, *, transport: httpx.BaseTransport | None = None
) -> MerchantSession:
    """Fetch a fresh session; reject malformed, denied and unavailable results."""
    url = _validate_url(base_url)
    if (
        not isinstance(token, str)
        or not token
        or len(token) > 4096
        or any(ord(char) < 33 or ord(char) > 126 for char in token)
    ):
        raise MerchantSessionError("商家会话无效")
    try:
        with httpx.Client(
            timeout=3.0, follow_redirects=False, trust_env=False, transport=transport
        ) as client:
            response = client.get(
                f"{url}/user/me/", headers={"token": token, "Accept": "application/json"}
            )
        if response.status_code != 200:
            raise MerchantSessionError("商家身份服务拒绝或无法验证会话")
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        raise MerchantSessionError("商家身份服务不可用或响应无效") from None

    if not isinstance(payload, dict) or payload.get("status") != 200:
        raise MerchantSessionError("商家身份服务拒绝或无法验证会话")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise MerchantSessionError("商家身份服务响应无效")
    user, tenant, permissions = data.get("user"), data.get("tenant"), data.get("permissions")
    if not all(isinstance(value, dict) for value in (user, tenant, permissions)):
        raise MerchantSessionError("商家身份服务响应无效")
    staff_id, tenant_id = user.get("id"), tenant.get("id")
    slug, actions, is_super = (
        tenant.get("slug"),
        permissions.get("actions"),
        permissions.get("is_super"),
    )
    if (
        type(staff_id) is not int
        or staff_id <= 0
        or type(tenant_id) is not int
        or tenant_id <= 0
        or type(user.get("tenant_id")) is not int
        or user["tenant_id"] != tenant_id
        or type(tenant.get("status")) is not int
        or tenant["status"] != 1
        or not isinstance(slug, str)
        or not slug.strip()
        or not isinstance(actions, list)
        or any(not isinstance(action, str) or not action for action in actions)
        or type(is_super) is not bool
    ):
        raise MerchantSessionError("商家身份服务响应无效")
    return MerchantSession(
        tenant_id,
        slug,
        staff_id,
        frozenset(actions),
        is_super,
        _display(user.get("nick_name")) or _display(user.get("name")),
        _display(user.get("role_name")),
    )


def _display(value: object) -> str | None:
    """Keep only short printable labels; never echo arbitrary response content."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 64:
        return None
    return cleaned


def validate_merchant_staff(
    base_url: str,
    token: str,
    tenant_id: int,
    staff_id: int,
    *,
    transport: httpx.BaseTransport | None = None,
) -> None:
    """Verify target staff via the merchant's tenant-scoped, authenticated API."""
    url = _validate_url(base_url)
    if (
        type(staff_id) is not int
        or staff_id <= 0
        or type(tenant_id) is not int
        or tenant_id <= 0
        or not isinstance(token, str)
        or not token
        or len(token) > 4096
        or any(ord(char) < 33 or ord(char) > 126 for char in token)
    ):
        raise MerchantSessionError("商家员工信息无效")
    try:
        with httpx.Client(
            timeout=3.0, follow_redirects=False, trust_env=False, transport=transport
        ) as client:
            response = client.get(
                f"{url}/user/user/{staff_id}/",
                headers={"token": token, "Accept": "application/json"},
            )
        if response.status_code != 200:
            raise MerchantSessionError("无法验证目标员工")
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        raise MerchantSessionError("商家身份服务不可用或响应无效") from None
    if not isinstance(payload, dict) or payload.get("status") != 200:
        raise MerchantSessionError("无法验证目标员工")
    data = payload.get("data")
    if (
        not isinstance(data, dict)
        or type(data.get("id")) is not int
        or data["id"] != staff_id
        or type(data.get("tenant_id")) is not int
        or data["tenant_id"] != tenant_id
    ):
        raise MerchantSessionError("无法验证目标员工")
