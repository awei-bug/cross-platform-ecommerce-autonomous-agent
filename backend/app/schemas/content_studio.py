"""内容发布工作台（抖音内容投稿）请求/响应模型。"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.integrations import ConnectorState


class ContentConnectStatus(BaseModel):
    platform: str = "douyin_content"
    state: ConnectorState
    platform_user_name: str | None = None
    scopes: list[str] = Field(default_factory=list)
    authorized_at: datetime | None = None
    last_error: str | None = None
    message: str = ""


class ContentConnectAuthorize(BaseModel):
    authorization_url: str
    expires_at: datetime


class ContentConnectCallback(BaseModel):
    platform: str = "douyin_content"
    state: ConnectorState
    platform_user_name: str
    authorized_at: datetime
    message: str = "抖音内容账号已连接，可发布内容。"


class ContentDisconnect(BaseModel):
    platform: str = "douyin_content"
    state: ConnectorState = ConnectorState.REVOKED
    disconnected_at: datetime


class ContentPublishCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(default="", max_length=2000)
    video_url: str | None = Field(default=None, max_length=1000)
    cover_url: str | None = Field(default=None, max_length=1000)


class ContentPublish(BaseModel):
    id: str
    organization_id: str
    platform: str = "douyin"
    title: str
    text: str
    video_url: str | None = None
    cover_url: str | None = None
    status: str
    external_id: str | None = None
    external_url: str | None = None
    error_message: str | None = None
    is_demo: bool = False
    created_at: datetime
    updated_at: datetime


class ContentPublishList(BaseModel):
    items: list[ContentPublish]
