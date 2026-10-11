from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.schemas.common import Platform
from app.schemas.integrations import ConnectorState, ConnectorStatus
from app.services.douyin_connections import (
    DOUYIN_READ_SCOPES,
    get_douyin_connection,
    missing_douyin_configuration,
)
from app.services.oauth_state import utc_now


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _status_for(
    *,
    platform: Platform,
    platform_label: str,
    read_scopes: list[str],
    missing_secrets: list[str],
    connection,
    messages: dict[str, str],
) -> ConnectorStatus:
    if missing_secrets:
        state = ConnectorState.CREDENTIALS_REQUIRED
        message = messages["no_config"]
    elif connection is None:
        state = ConnectorState.AUTHORIZATION_REQUIRED
        message = messages["unauthorized"]
    else:
        try:
            state = ConnectorState(connection.state)
        except ValueError:
            state = ConnectorState.ERROR
        if state == ConnectorState.READY:
            if connection.access_token_expires_at and (
                _aware(connection.access_token_expires_at) <= utc_now()
            ):
                state = ConnectorState.EXPIRED
                message = messages["expired"]
            else:
                message = messages["ready"]
        elif state == ConnectorState.ERROR:
            message = messages["error"]
        elif state == ConnectorState.REVOKED:
            message = messages["revoked"]
        else:
            message = messages["pending"]

    return ConnectorStatus(
        platform=platform,
        platform_label=platform_label,
        state=state,
        read_scopes=read_scopes,
        missing_secrets=missing_secrets,
        message=message,
        platform_user_name=connection.platform_user_name if connection else None,
        platform_shop_id=connection.platform_shop_id if connection else None,
        platform_shop_name=connection.platform_shop_name if connection else None,
        access_token_expires_at=connection.access_token_expires_at if connection else None,
        authorized_at=connection.authorized_at if connection else None,
        last_error=connection.last_error if connection else None,
    )


def _douyin_status(db: Session, organization_id: str, settings: Settings) -> ConnectorStatus:
    return _status_for(
        platform=Platform.DOUYIN,
        platform_label="抖店",
        read_scopes=DOUYIN_READ_SCOPES,
        missing_secrets=missing_douyin_configuration(settings),
        connection=get_douyin_connection(db, organization_id),
        messages={
            "no_config": "尚未配置抖店开放平台应用与 Token 加密密钥，真实授权功能不可用。",
            "unauthorized": "服务端配置已就绪，请由店铺管理员完成抖店 OAuth 授权。",
            "expired": "抖店 Access Token 已过期，需要刷新或重新授权。",
            "ready": "抖店店铺身份已通过官方 API 校验，只读连接可用。",
            "error": "抖店授权或身份校验失败，请重新发起授权并查看错误信息。",
            "revoked": "抖店连接已断开，服务端已清除保存的 Token。",
            "pending": "抖店连接尚未完成授权。",
        },
    )


def connector_statuses(
    db: Session,
    organization_id: str,
    settings: Settings | None = None,
) -> list[ConnectorStatus]:
    resolved_settings = settings or get_settings()
    return [
        _douyin_status(db, organization_id, resolved_settings),
    ]


def douyin_status(
    db: Session,
    organization_id: str,
    settings: Settings | None = None,
) -> ConnectorStatus:
    return _douyin_status(db, organization_id, settings or get_settings())
