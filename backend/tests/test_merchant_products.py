from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import merchant_products
from app.db.models import (
    Base,
    MerchantOrganizationMappingModel,
    MerchantShopGrantModel,
    ProductModel,
    ShopModel,
)
from app.db.session import get_db
from app.services.merchant_access_management import (
    set_product_read_permission,
    set_shop_grant_active,
)
from app.services.merchant_session import MerchantSession, MerchantSessionError


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.add_all(
            [
                MerchantOrganizationMappingModel(
                    tenant_id=1, organization_id="org-a", is_active=True
                ),
                MerchantOrganizationMappingModel(
                    tenant_id=2, organization_id="org-b", is_active=True
                ),
                ShopModel(
                    id="a",
                    organization_id="org-a",
                    platform="douyin",
                    platform_label="演示",
                    name="A",
                    data_source="seeded",
                ),
                ShopModel(
                    id="b",
                    organization_id="org-b",
                    platform="douyin",
                    platform_label="演示",
                    name="B",
                    data_source="seeded",
                ),
                ShopModel(
                    id="live",
                    organization_id="org-a",
                    platform="douyin",
                    platform_label="真实",
                    name="L",
                    data_source="live",
                ),
                MerchantShopGrantModel(
                    tenant_id=1, staff_id=7, shop_id="a", is_active=True, can_read_products=True
                ),
                MerchantShopGrantModel(
                    tenant_id=2, staff_id=8, shop_id="b", is_active=True, can_read_products=True
                ),
                MerchantShopGrantModel(
                    tenant_id=1, staff_id=7, shop_id="live", is_active=True, can_read_products=True
                ),
            ]
        )
        for id_, org, shop in [
            ("p-a", "org-a", "a"),
            ("p-b", "org-b", "b"),
            ("bad", "org-b", "a"),
            ("p-live", "org-a", "live"),
        ]:
            db.add(
                ProductModel(
                    id=id_,
                    organization_id=org,
                    shop_id=shop,
                    sku="SKU",
                    title=id_,
                    platform="douyin",
                    platform_label="测试",
                    shop_name=shop,
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
        merchant_product_read_enabled=True, merchant_identity_url="http://127.0.0.1:5000"
    )
    monkeypatch.setattr(merchant_products, "get_settings", lambda: settings)

    def identity(_url, token):
        if token == "a":
            return MerchantSession(1, "a", 7, frozenset({"product:read"}), False)
        if token == "b":
            return MerchantSession(2, "b", 8, frozenset({"product:read"}), False)
        if token == "no-action":
            return MerchantSession(1, "a", 7, frozenset(), True)
        if token == "other-staff":
            return MerchantSession(1, "a", 9, frozenset({"product:read"}), False)
        raise MerchantSessionError("invalid")

    monkeypatch.setattr(merchant_products, "validate_merchant_session", identity)
    app = FastAPI()
    app.include_router(merchant_products.router)

    def get_test_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app) as api:
        yield api, settings, sessions
    engine.dispose()


def test_explicit_permission_and_tenant_scope(client):
    api, _, _ = client
    header = {"Authorization": "Bearer a"}
    response = api.get("/merchant-products/a", headers=header)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert [row["id"] for row in response.json()["items"]] == ["p-a"]
    assert api.get("/merchant-products/b", headers=header).status_code == 404
    assert api.get("/merchant-products/live", headers=header).status_code == 404
    assert api.get("/merchant-products/shop-all", headers=header).status_code == 404
    assert api.get("/merchant-products/a", headers={"Authorization": "Bearer b"}).status_code == 404
    assert (
        api.get("/merchant-products/a", headers={"Authorization": "Bearer other-staff"}).status_code
        == 404
    )
    assert (
        api.get("/merchant-products/a", headers={"Authorization": "Bearer no-action"}).status_code
        == 403
    )


def test_fail_closed_and_revoke(client):
    api, settings, sessions = client
    headers = {"Authorization": "Bearer a"}
    settings.merchant_product_read_enabled = False
    assert api.get("/merchant-products/a", headers=headers).status_code == 404
    settings.merchant_product_read_enabled = True
    assert api.get("/merchant-products/a").status_code == 401
    assert (
        api.get("/merchant-products/a", headers={"Authorization": "Bearer invalid"}).status_code
        == 401
    )
    with sessions.begin() as db:
        set_product_read_permission(db, 1, 7, "a", False, actor="admin")
    assert api.get("/merchant-products/a", headers=headers).status_code == 404
    with sessions.begin() as db:
        set_product_read_permission(db, 1, 7, "a", True, actor="admin")
        set_shop_grant_active(db, 1, 7, "a", False, actor="admin")
        set_shop_grant_active(db, 1, 7, "a", True, actor="admin")
    assert api.get("/merchant-products/a", headers=headers).status_code == 404
    with sessions() as db:
        assert db.get(MerchantShopGrantModel, (1, 7, "a")).can_read_products is False


def test_shop_list_respects_identity_and_revocation(client):
    api, settings, sessions = client
    a = {"Authorization": "Bearer a"}
    b = {"Authorization": "Bearer b"}
    response = api.get("/merchant-products/shops/list", headers=a)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert [item["id"] for item in response.json()["items"]] == ["a"]
    assert [
        item["id"] for item in api.get("/merchant-products/shops/list", headers=b).json()["items"]
    ] == ["b"]
    assert (
        api.get(
            "/merchant-products/shops/list", headers={"Authorization": "Bearer other-staff"}
        ).json()["items"]
        == []
    )
    assert (
        api.get(
            "/merchant-products/shops/list", headers={"Authorization": "Bearer no-action"}
        ).status_code
        == 403
    )
    assert api.get("/merchant-products/shops/list").status_code == 401
    assert api.get("/merchant-products/shops/list?after=a", headers=a).json()["items"] == []
    with sessions.begin() as db:
        set_product_read_permission(db, 1, 7, "a", False, actor="admin")
    assert api.get("/merchant-products/shops/list", headers=a).json()["items"] == []
    settings.merchant_product_read_enabled = False
    assert api.get("/merchant-products/shops/list", headers=a).status_code == 404


def test_shop_list_cursor_paginates_authorized_shops(client):
    api, _, sessions = client
    with sessions.begin() as db:
        for index in range(105):
            shop_id = f"z-{index:03}"
            db.add(
                ShopModel(
                    id=shop_id,
                    organization_id="org-a",
                    platform="douyin",
                    platform_label="演示",
                    name=shop_id,
                    data_source="seeded",
                )
            )
            db.add(
                MerchantShopGrantModel(
                    tenant_id=1, staff_id=7, shop_id=shop_id, is_active=True, can_read_products=True
                )
            )
    headers = {"Authorization": "Bearer a"}
    first = api.get("/merchant-products/shops/list", headers=headers).json()
    assert len(first["items"]) == 100
    second = api.get(
        "/merchant-products/shops/list", params={"after": first["next_after"]}, headers=headers
    ).json()
    ids = [item["id"] for item in first["items"] + second["items"]]
    assert len(ids) == len(set(ids)) == 106 and second["next_after"] is None
