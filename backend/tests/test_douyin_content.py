"""抖音内容投稿契约测试（OAuth + create_video + 草稿发布服务 + 路由准入）。

全部使用 httpx.MockTransport 拦截网络，无需真实开放应用或用户授权。
"""
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import ContentPublishModel, PlatformConnectionModel
from app.db.session import session_scope
from app.integrations.douyin_content import DouyinContentApiError, DouyinContentClient
from app.schemas.common import Platform
from app.schemas.integrations import ConnectorState
from app.services.content_publish_service import (
    ContentPublishError,
    create_draft,
    publish_content,
)
from app.services.token_cipher import TokenCipher

_SECRET_KEY = Fernet.generate_key().decode()
_VIDEO_BYTES = b"\x00\x01\x02mp4payload"


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(__import__("app.main", fromlist=["app"]).app) as test_client:
        yield test_client


def _build_client(handler) -> DouyinContentClient:
    return DouyinContentClient(
        client_key="dc-key",
        client_secret="dc-secret",
        redirect_uri="https://example.test/cb",
        api_base_url="https://open.douyin.com",
        transport=httpx.MockTransport(handler),
    )


def test_authorization_url_contains_state_and_scopes() -> None:
    client = DouyinContentClient(
        client_key="dc-key",
        client_secret="dc-secret",
        redirect_uri="https://example.test/cb",
    )
    url = client.build_authorization_url("state-xyz")
    assert "client_key=dc-key" in url
    assert "state=state-xyz" in url
    assert "video.create" in url


def test_exchange_code_returns_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "oauth/access_token" in request.url.path
        return httpx.Response(
            200,
            json={
                "access_token": "OPEN_TOKEN",
                "refresh_token": "OPEN_REFRESH",
                "open_id": "ou_abc",
                "expires_in": 7200,
                "scope": "video.create,renew_refresh_token",
            },
        )

    client = _build_client(handler)
    import asyncio

    token = asyncio.run(client.exchange_code("auth-code"))
    assert token.access_token == "OPEN_TOKEN"
    assert token.open_id == "ou_abc"
    assert token.access_token_expires_at is not None


def test_create_video_uploads_and_returns_item_id() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(
            200,
            json={"error_code": 0, "data": {"item_id": "i_998", "video_id": "v_998"}},
        )

    client = _build_client(handler)
    import asyncio

    result = asyncio.run(
        client.create_video("OPEN_TOKEN", title="标题", text="文案", video=_VIDEO_BYTES)
    )
    assert result["item_id"] == "i_998"
    assert "video/create_video" in captured["path"]


def test_create_video_surfaces_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"error_code": 2190008, "detail": "access_token invalid"}
        )

    client = _build_client(handler)
    import asyncio

    with pytest.raises(DouyinContentApiError):
        asyncio.run(
            client.create_video("BAD", title="t", text="x", video=_VIDEO_BYTES)
        )


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("DOUYIN_CONTENT_CLIENT_KEY", "dc-key")
    monkeypatch.setenv("DOUYIN_CONTENT_CLIENT_SECRET", "dc-secret")
    monkeypatch.setenv("DOUYIN_CONTENT_REDIRECT_URI", "https://example.test/cb")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEYS", _SECRET_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _prepare_connection(db, cipher: TokenCipher) -> None:
    connection = db.scalar(
        select(PlatformConnectionModel).where(
            PlatformConnectionModel.organization_id == "org-demo-001",
            PlatformConnectionModel.platform == Platform.DOUYIN_CONTENT.value,
        )
    )
    if connection is None:
        connection = PlatformConnectionModel(
            id=f"conn-{uuid4().hex}",
            organization_id="org-demo-001",
            platform=Platform.DOUYIN_CONTENT.value,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            scopes=[],
        )
        db.add(connection)
    connection.state = ConnectorState.READY.value
    connection.encrypted_access_token = cipher.encrypt("OPEN_TOKEN")
    connection.platform_user_id = "ou_abc"
    connection.platform_user_name = "ou_abc"
    connection.updated_at = datetime.now(UTC)
    db.commit()


def test_publish_draft_calls_douyin_and_marks_published(configured, client) -> None:
    cipher = TokenCipher(_SECRET_KEY)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/clip.mp4"):
            return httpx.Response(200, content=_VIDEO_BYTES)
        return httpx.Response(
            200, json={"error_code": 0, "data": {"item_id": "i_real", "video_id": "v_real"}}
        )

    with session_scope() as db:
        _prepare_connection(db, cipher)
        draft = create_draft(
            db,
            "org-demo-001",
            title="秋冬补水精华",
            text="好物分享 #护肤",
            video_url="https://video.test/clip.mp4",
        )
        draft_id = draft["id"]

    with session_scope() as db:
        result = publish_content(
            db, "org-demo-001", draft_id, transport=httpx.MockTransport(handler)
        )

    assert result["status"] == "published"
    assert result["is_demo"] is False
    assert result["external_id"] == "i_real"
    assert result["external_url"]

    with session_scope() as db:
        row = db.get(ContentPublishModel, draft_id)
        assert row.status == "published"
        assert row.is_demo is False


def test_publish_without_connection_fails_safe(configured, client) -> None:
    # 使用独立组织，确保不存在抖音内容账号连接。
    with session_scope() as db:
        draft = create_draft(
            db, "org-no-conn", title="未授权草稿", text="", video_url="https://video.test/clip.mp4"
        )
        draft_id = draft["id"]

    with session_scope() as db:
        with pytest.raises(ContentPublishError, match="尚未授权"):
            publish_content(
                db,
                "org-no-conn",
                draft_id,
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"")),
            )


def test_connect_status_requires_credentials(client) -> None:
    get_settings.cache_clear()
    response = client.get(
        "/api/v1/content-studio/connect/status",
        headers={"Authorization": "Bearer demo-access-token"},
    )
    assert response.status_code == 200
    assert response.json()["state"] == "credentials_required"
