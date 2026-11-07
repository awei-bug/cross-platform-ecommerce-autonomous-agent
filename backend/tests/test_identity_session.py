"""Identity must come from a verified 云购 session, never from a fixed token.

These tests run with the local-development fallback DISABLED, so they exercise
the production path: a bearer token is verified against the configured identity
service, tenant/operator come from that response, and an active
tenant->organization mapping supplies the organization boundary.
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import automation, products, workspace
from app.core import identity
from app.db.models import (
    Base,
    MerchantOrganizationMappingModel,
    ProductModel,
    ShopModel,
    WorkspaceStatsModel,
)
from app.db.session import get_db
from app.services.merchant_session import MerchantSession, MerchantSessionError

TENANT = 11
STAFF = 21
ORG = "org-tenant-11"

# token -> 云购 /user/me/ 会返回的已验证会话
SESSIONS = {
    "reader": MerchantSession(TENANT, "shop-a", STAFF, frozenset({"product:read"}), False),
    "writer": MerchantSession(
        TENANT, "shop-a", STAFF, frozenset({"product:read", "product:write"}), False
    ),
    "nobody": MerchantSession(TENANT, "shop-a", STAFF, frozenset(), False),
    "unmapped": MerchantSession(99, "shop-z", 77, frozenset({"product:read"}), False),
}


@pytest.fixture
def api(monkeypatch):
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
                id="shop-a",
                organization_id=ORG,
                platform="douyin",
                platform_label="演示",
                name="A",
                data_source="seeded",
                last_synced_at=datetime.now(UTC),
            )
        )
        db.add(WorkspaceStatsModel(
            organization_id=ORG, today_sales=0, paid_orders=0, active_alerts=0,
            pending_tasks=0, updated_at=datetime.now(UTC),
        ))
        db.add(
            ProductModel(
                id="p-a",
                organization_id=ORG,
                shop_id="shop-a",
                sku="SKU-A",
                title="A",
                platform="douyin",
                platform_label="演示",
                shop_name="A",
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
        merchant_identity_url="http://127.0.0.1:59999",
        demo_identity_fallback_enabled=False,
        environment="test",
        merchant_product_read_enabled=True,
    )
    monkeypatch.setattr(identity, "get_settings", lambda: settings)

    def fake_validate(_url, token):
        session = SESSIONS.get(token)
        if session is None:
            raise MerchantSessionError("invalid")
        return session

    monkeypatch.setattr(identity, "validate_merchant_session", fake_validate)
    app = FastAPI()
    app.include_router(products.router)
    app.include_router(workspace.router)
    app.include_router(automation.router)

    def get_test_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app) as client:
        yield client
    engine.dispose()


def test_no_credentials_is_401(api):
    response = api.get("/products")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_fixed_demo_token_is_rejected(api):
    # 关键回归：固定演示令牌不再是身份来源。
    response = api.get("/products", headers={"Authorization": "Bearer demo-access-token"})
    assert response.status_code == 401


def test_unknown_token_is_401(api):
    response = api.get("/products", headers={"Authorization": "Bearer forged"})
    assert response.status_code == 401


def test_read_requires_product_read_action(api):
    assert api.get("/products", headers={"Authorization": "Bearer nobody"}).status_code == 403
    assert api.get("/products", headers={"Authorization": "Bearer reader"}).status_code == 200


def test_tenant_without_mapping_is_403(api):
    # 会话有效但无启用的租户→组织映射：拒绝，而不是退回默认组织。
    assert api.get("/products", headers={"Authorization": "Bearer unmapped"}).status_code == 403


def test_write_requires_product_write_action(api):
    body = {"action": "sync", "product_ids": ["p-a"], "idempotency_key": "k-identity-001"}
    assert (
        api.post(
            "/products/batch-actions", json=body, headers={"Authorization": "Bearer reader"}
        ).status_code
        == 403
    )
    assert (
        api.post(
            "/products/batch-actions", json=body, headers={"Authorization": "Bearer writer"}
        ).status_code
        == 202
    )


def test_operator_and_organization_come_from_session(api):
    payload = api.get("/products", headers={"Authorization": "Bearer reader"}).json()
    # 组织边界来自映射，不来自请求体；商品只属于该组织。
    assert {item["id"] for item in payload["items"]} == {"p-a"}
    me = api.get("/workspace/bootstrap", headers={"Authorization": "Bearer reader"})
    assert me.status_code == 200


def test_request_body_cannot_override_tenant(api):
    # 查询参数里塞入其他组织标识不会改变可见范围。
    payload = api.get(
        "/products",
        params={"organization_id": "org-demo-001", "shop_id": "shop-all"},
        headers={"Authorization": "Bearer reader"},
    ).json()
    assert {item["id"] for item in payload["items"]} == {"p-a"}


def test_automation_routes_enforce_action_codes(api):
    """自动化规则/执行记录同样只认云购动作码，不认固定令牌。"""
    assert api.get("/automation").status_code == 401
    assert api.get("/automation", headers={"Authorization": "Bearer nobody"}).status_code == 403
    assert api.get("/automation", headers={"Authorization": "Bearer reader"}).status_code == 200
    overview = api.get("/automation", headers={"Authorization": "Bearer reader"}).json()
    rule_id = overview["rules"][0]["id"]
    # 只有 product:read 的会话不能改规则
    patch = api.patch(
        f"/automation/rules/{rule_id}",
        json={"is_enabled": False},
        headers={"Authorization": "Bearer reader"},
    )
    assert patch.status_code == 403
    allowed = api.patch(
        f"/automation/rules/{rule_id}",
        json={"is_enabled": False},
        headers={"Authorization": "Bearer writer"},
    )
    assert allowed.status_code == 200
