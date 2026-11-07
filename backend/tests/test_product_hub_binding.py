from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import products
from app.db.models import Base, ProductModel, ShopModel
from app.db.session import get_db
from app.services.hub_client import HubError

HEADERS = {"Authorization": "Bearer demo-access-token"}


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as db:
        for shop_id, source, org in [
            ("demo", "seeded", "org-demo-001"),
            ("live", "live", "org-demo-001"),
            ("other", "seeded", "other-org"),
        ]:
            db.add(
                ShopModel(
                    id=shop_id,
                    organization_id=org,
                    platform="douyin",
                    platform_label="抖店",
                    name=shop_id,
                    data_source=source,
                )
            )
            db.add(
                ProductModel(
                    id=shop_id,
                    organization_id=org,
                    shop_id=shop_id,
                    sku="SKU",
                    external_id="dy-platform",
                    title="本地商品",
                    platform="douyin",
                    platform_label="抖店",
                    shop_name=shop_id,
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
    monkeypatch.setattr(products, "hub_enabled", lambda: True)
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: type("Settings", (), {"data_hub_tenant_slug": "demo"})(),
    )
    monkeypatch.setattr(
        products,
        "_request",
        lambda *args: {
            "item": {
                "external_id": "cc-1",
                "title": "内容商品",
                "status": "published",
                "selling_points": ["轻便"],
            }
        },
    )
    app = FastAPI()
    app.include_router(products.router, prefix="/api")

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client, sessions
    engine.dispose()


def test_preview_bind_conflict_unbind_and_platform_identity(client):
    test_client, sessions = client
    path = "/api/products/demo"
    assert test_client.get(path + "/hub-preview", params={"external_id": "cc-1"}).status_code == 401
    preview = test_client.get(
        path + "/hub-preview", params={"external_id": "cc-1"}, headers=HEADERS
    )
    assert preview.status_code == 200 and preview.json()["title"] == "内容商品"
    body = {"hub_product_id": "cc-1", "expected_hub_product_id": None}
    assert test_client.put(path + "/hub-binding", json=body, headers=HEADERS).status_code == 200
    assert test_client.put(path + "/hub-binding", json=body, headers=HEADERS).status_code == 409
    with sessions() as db:
        product = db.get(ProductModel, "demo")
        assert product.external_id == "dy-platform" and product.hub_product_id == "cc-1"
    assert (
        test_client.put(
            path + "/hub-binding",
            json={"hub_product_id": None, "expected_hub_product_id": "cc-1"},
            headers=HEADERS,
        ).status_code
        == 200
    )
    with sessions() as db:
        assert db.get(ProductModel, "demo").hub_product_id is None


def test_live_other_org_invalid_and_unavailable_are_rejected(client, monkeypatch):
    test_client, sessions = client
    body = {"hub_product_id": "cc-1", "expected_hub_product_id": None}
    assert (
        test_client.put("/api/products/live/hub-binding", json=body, headers=HEADERS).status_code
        == 403
    )
    assert (
        test_client.put("/api/products/other/hub-binding", json=body, headers=HEADERS).status_code
        == 404
    )
    assert (
        test_client.get(
            "/api/products/demo/hub-preview", params={"external_id": "../other"}, headers=HEADERS
        ).status_code
        == 422
    )

    def unavailable(*args):
        raise HubError("data-hub 连接失败")

    monkeypatch.setattr(products, "_request", unavailable)
    assert (
        test_client.put("/api/products/demo/hub-binding", json=body, headers=HEADERS).status_code
        == 503
    )
    with sessions() as db:
        assert db.get(ProductModel, "demo").hub_product_id is None
