from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from app.schemas.common import Platform


class ConnectorState(StrEnum):
    CREDENTIALS_REQUIRED = "credentials_required"
    AUTHORIZATION_REQUIRED = "authorization_required"
    ADAPTER_PENDING = "adapter_pending"
    READY = "ready"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"


class ConnectorStatus(BaseModel):
    platform: Platform
    platform_label: str
    state: ConnectorState
    read_scopes: list[str]
    missing_secrets: list[str]
    message: str
    platform_user_name: str | None = None
    platform_shop_id: str | None = None
    platform_shop_name: str | None = None
    access_token_expires_at: datetime | None = None
    authorized_at: datetime | None = None
    last_error: str | None = None


class OAuthAuthorizationResponse(BaseModel):
    platform: Platform = Platform.DOUYIN
    authorization_url: str
    expires_at: datetime


class OAuthCallbackResponse(BaseModel):
    platform: Platform = Platform.DOUYIN
    state: ConnectorState
    platform_user_name: str
    platform_shop_id: str | None = None
    platform_shop_name: str | None = None
    authorized_at: datetime
    message: str = "抖店授权成功，已完成店铺身份校验。"


class DisconnectResponse(BaseModel):
    platform: Platform = Platform.DOUYIN
    state: ConnectorState = ConnectorState.REVOKED
    disconnected_at: datetime


class ProductSyncResponse(BaseModel):
    """平台商品真实同步结果。

    `is_live` 为 False 表示本次未真实调用平台 API（例如未授权），此时
    响应不得被描述成"已同步真实店铺数据"。
    """

    platform: Platform = Platform.DOUYIN
    shop_id: str | None = None
    shop_name: str | None = None
    data_source: str = "seeded"
    is_live: bool = False
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    total_fetched: int = 0
    warnings: list[str] = []
    synced_at: datetime