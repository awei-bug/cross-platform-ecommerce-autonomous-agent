"""End-to-end identity check against a real (local) 云购 identity stub.

Unlike test_identity_session.py this does NOT monkeypatch the validator: the app
performs a real HTTP GET to ``/user/me/`` on an ephemeral local port, so the
network path, response parsing and action enforcement are all exercised.
"""

import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import products
from app.core import identity
from app.db.models import Base, MerchantOrganizationMappingModel, ProductModel, ShopModel
from app.db.session import get_db
from app.services.merchant_session import MerchantIdentityUnavailable

TENANT, STAFF, ORG = 42, 4242, "org-tenant-42"

# token -> (status_code, payload) the stub will answer with
RESPONSES = {
    "reader": (200, {
        "status": 200,
        "data": {
            "user": {"id": STAFF, "tenant_id": TENANT, "name": "张三", "role_name": "运营"},
            "tenant": {"id": TENANT, "slug": "tenant-42", "status": 1},
            "permissions": {"is_super": False, "actions": ["product:read"]},
        },
    }),
    "writer": (200, {
        "status": 200,
        "data": {
            "user": {"id": STAFF, "tenant_id": TENANT, "name": "张三", "role_name": "运营"},
            "tenant": {"id": TENANT, "slug": "tenant-42", "status": 1},
            "permissions": {"is_super": False, "actions": ["product:read", "product:write"]},
        },
    }),
    "readonly-no-write": (200, {
        "status": 200,
        "data": {
            "user": {"id": STAFF, "tenant_id": TENANT, "name": "张三", "role_name": "运营"},
            "tenant": {"id": TENANT, "slug": "tenant-42", "status": 1},
            "permissions": {"is_super": False, "actions": ["product:read"]},
        },
    }),
    "suspended": (200, {
        "status": 200,
        "data": {
            "user": {"id": STAFF, "tenant_id": TENANT, "name": "张三", "role_name": "运营"},
            "tenant": {"id": TENANT, "slug": "tenant-42", "status": 0},
            "permissions": {"is_super": False, "actions": ["product:read"]},
        },
    }),
}


@pytest.fixture
def identity_stub():
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib naming
            token = self.headers.get("token", "")
            seen.append((self.path, token))
            status, payload = RESPONSES.get(token, (401, {"status": 401}))
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # silence stderr noise
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def api(identity_stub, monkeypatch):
    base_url, _seen = identity_stub
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.add(
            MerchantOrganizationMappingModel(
                tenant_id=TENANT, organization_id=ORG, is_active=True
            )
        )
        db.add(
            ShopModel(
                id="shop-42",
                organization_id=ORG,
                platform="douyin",
                platform_label="演示",
                name="租户42店铺",
                data_source="seeded",
                last_synced_at=datetime.now(UTC),
            )
        )
        db.add(
            ProductModel(
                id="p-42",
                organization_id=ORG,
                shop_id="shop-42",
                sku="SKU-42",
                title="租户42商品",
                platform="douyin",
                platform_label="演示",
                shop_name="租户42店铺",
                status="online",
                risk="normal",
                price=10,
                cost=5,
                stock=3,
                sales_7d=0,
                revenue_7d=0,
                conversion_rate=0,
                updated_at=datetime.now(UTC),
            )
        )
    settings = SimpleNamespace(
        merchant_identity_url=base_url,
        demo_identity_fallback_enabled=False,
        environment="test",
    )
    monkeypatch.setattr(identity, "get_settings", lambda: settings)
    app = FastAPI()
    app.include_router(products.router)

    def get_test_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app) as client:
        yield client
    engine.dispose()


def test_read_allowed_for_verified_session(api, identity_stub):
    _base, seen = identity_stub
    response = api.get("/products", headers={"Authorization": "Bearer reader"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == ["p-42"]
    # 真实网络调用发生了，且打到云购 /user/me/ 并带上 token 头。
    assert seen and seen[-1] == ("/user/me/", "reader")


def test_upstream_outage_is_503_not_logout(api, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise MerchantIdentityUnavailable("云购不可达")

    monkeypatch.setattr(identity, "validate_merchant_session", unavailable)
    response = api.get("/products", headers={"Authorization": "Bearer reader"})
    assert response.status_code == 503
    assert "不可用" in response.json()["detail"]


def test_no_session_is_401(api):
    assert api.get("/products").status_code == 401


def test_fixed_demo_token_is_401(api):
    assert (
        api.get("/products", headers={"Authorization": "Bearer demo-access-token"}).status_code
        == 401
    )


def test_suspended_tenant_is_401(api):
    assert api.get("/products", headers={"Authorization": "Bearer suspended"}).status_code == 401


def test_write_allowed_only_with_write_action(api):
    body = {"action": "sync", "product_ids": ["p-42"], "idempotency_key": "k-e2e-42"}
    denied = api.post(
        "/products/batch-actions", json=body, headers={"Authorization": "Bearer readonly-no-write"}
    )
    assert denied.status_code == 403
    allowed = api.post(
        "/products/batch-actions", json=body, headers={"Authorization": "Bearer writer"}
    )
    assert allowed.status_code == 202
