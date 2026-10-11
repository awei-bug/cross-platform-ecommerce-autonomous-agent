from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import require_demo_user
from app.db.session import get_db
from app.integrations.douyin import DouyinApiError, DouyinClient
from app.schemas.auth import UserProfile
from app.schemas.common import Platform
from app.schemas.integrations import (
    ConnectorState,
    ConnectorStatus,
    DisconnectResponse,
    OAuthAuthorizationResponse,
    OAuthCallbackResponse,
    ProductSyncResponse,
)
from app.services.connector_registry import connector_statuses, douyin_status
from app.services.douyin_connections import (
    consume_oauth_state as consume_douyin_oauth_state,
)
from app.services.douyin_connections import (
    create_oauth_state as create_douyin_oauth_state,
)
from app.services.douyin_connections import (
    disconnect_douyin,
    missing_douyin_configuration,
)
from app.services.douyin_connections import (
    save_authorized_connection as save_douyin_connection,
)
from app.services.douyin_connections import (
    save_connection_error as save_douyin_error,
)
from app.services.oauth_state import OAuthStateError
from app.services.platform_sync import ProductSyncError, sync_douyin_products
from app.services.token_cipher import TokenCipher, TokenEncryptionConfigurationError

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _require_cipher(settings: Settings) -> TokenCipher:
    try:
        return TokenCipher(settings.token_encryption_keys or "")
    except TokenEncryptionConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _configured_douyin_client(settings: Settings) -> DouyinClient:
    missing = missing_douyin_configuration(settings)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "douyin_credentials_required",
                "message": "抖店开放平台服务端配置不完整",
                "missing": missing,
            },
        )
    return DouyinClient(
        app_key=settings.douyin_app_key or "",
        app_secret=settings.douyin_app_secret or "",
        redirect_uri=settings.douyin_redirect_uri or "",
        auth_base_url=settings.douyin_auth_base_url,
        token_base_url=settings.douyin_token_base_url,
        api_base_url=settings.douyin_api_base_url,
        timeout_seconds=settings.douyin_http_timeout_seconds,
        max_attempts=settings.douyin_http_max_attempts,
    )


@router.get("/connectors", response_model=list[ConnectorStatus])
def connectors(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ConnectorStatus]:
    return connector_statuses(db, user.organization_id)


# --------------------------------------------------------------------------- 抖店
@router.get("/douyin/status", response_model=ConnectorStatus)
def get_douyin_status(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ConnectorStatus:
    return douyin_status(db, user.organization_id)


@router.post("/douyin/authorize", response_model=OAuthAuthorizationResponse)
def authorize_douyin(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OAuthAuthorizationResponse:
    settings = get_settings()
    client = _configured_douyin_client(settings)
    _require_cipher(settings)
    raw_state, expires_at = create_douyin_oauth_state(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        redirect_uri=settings.douyin_redirect_uri or "",
        ttl_seconds=settings.oauth_state_ttl_seconds,
    )
    return OAuthAuthorizationResponse(
        platform=Platform.DOUYIN,
        authorization_url=client.build_authorization_url(raw_state),
        expires_at=expires_at,
    )


@router.get("/douyin/callback", response_model=OAuthCallbackResponse)
async def douyin_callback(
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[str | None, Query(min_length=1, max_length=2000)] = None,
    oauth_state: Annotated[str | None, Query(alias="state", min_length=32, max_length=500)] = None,
    error: Annotated[str | None, Query(max_length=200)] = None,
    error_description: Annotated[str | None, Query(max_length=1000)] = None,
) -> OAuthCallbackResponse:
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_description or error
        )
    if not code or not oauth_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="抖店 OAuth 回调缺少 code 或 state"
        )

    try:
        state_record = consume_douyin_oauth_state(db, oauth_state)
    except OAuthStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    settings = get_settings()
    client = _configured_douyin_client(settings)
    client.redirect_uri = state_record.redirect_uri
    try:
        cipher = _require_cipher(settings)
        token = await client.exchange_code(code)
        identity = await client.fetch_seller_identity(token.access_token)
        connection = save_douyin_connection(
            db,
            organization_id=state_record.organization_id,
            app_key=settings.douyin_app_key or "",
            token=token,
            identity=identity,
            cipher=cipher,
        )
    except (DouyinApiError, TokenEncryptionConfigurationError) as exc:
        save_douyin_error(db, state_record.organization_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="抖店授权或店铺身份校验失败，请重新发起授权",
        ) from exc

    return OAuthCallbackResponse(
        platform=Platform.DOUYIN,
        state=ConnectorState.READY,
        platform_user_name=connection.platform_user_name or identity.user_name,
        platform_shop_id=connection.platform_shop_id,
        platform_shop_name=connection.platform_shop_name,
        authorized_at=connection.authorized_at or connection.updated_at,
        message="抖店授权成功，已完成店铺身份校验。",
    )


@router.post("/douyin/disconnect", response_model=DisconnectResponse)
def disconnect_douyin_connection(
    user: Annotated[UserProfile, Depends(require_demo_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DisconnectResponse:
    disconnected_at = disconnect_douyin(db, user.organization_id)
    return DisconnectResponse(platform=Platform.DOUYIN, disconnected_at=disconnected_at)


@router.post("/douyin/sync", response_model=ProductSyncResponse)
def sync_douyin_products_endpoint(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProductSyncResponse:
    """把抖店授权店铺的真实商品同步到本地，并将该店铺切换为 live 数据源。

    同步成功后店铺的改价/上下架会真实调用平台 API（见 platform_write）。
    未授权或缺少服务端凭证时返回 409，不做任何降级伪造。
    """
    try:
        return sync_douyin_products(db, settings=settings)
    except ProductSyncError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
