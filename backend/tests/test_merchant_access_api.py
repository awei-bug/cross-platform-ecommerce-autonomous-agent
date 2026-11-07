from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes import merchant_access
from app.api.routes.merchant_access import require_postgres as actual_postgres_guard
from app.db.models import (
    MerchantAccessAuditModel,
    MerchantOrganizationMappingModel,
    MerchantShopGrantModel,
    ShopModel,
)
from app.db.session import get_db
from app.services.merchant_session import MerchantSession, MerchantSessionError


@pytest.fixture
def setup_api(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (
        MerchantOrganizationMappingModel,
        ShopModel,
        MerchantShopGrantModel,
        MerchantAccessAuditModel,
    ):
        model.__table__.create(engine)
    with Session(engine) as db:
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
                    platform="demo",
                    platform_label="demo",
                    name="A",
                ),
                ShopModel(
                    id="b",
                    organization_id="org-b",
                    platform="demo",
                    platform_label="demo",
                    name="B",
                ),
            ]
        )
        db.commit()
    settings = SimpleNamespace(
        merchant_access_admin_enabled=True, merchant_identity_url="http://127.0.0.1:5000"
    )
    monkeypatch.setattr(merchant_access, "get_settings", lambda: settings)
    monkeypatch.setattr(merchant_access, "require_postgres", lambda db: None)

    def session_for(_url, token):
        if token == "admin":
            return MerchantSession(1, "a", 7, frozenset(), True)
        if token == "staff":
            return MerchantSession(1, "a", 8, frozenset(), False)
        if token == "other":
            return MerchantSession(2, "b", 9, frozenset(), True)
        raise MerchantSessionError("invalid")

    monkeypatch.setattr(merchant_access, "validate_merchant_session", session_for)

    def verify_staff(_url, _token, tenant_id, staff_id):
        if (tenant_id, staff_id) != (1, 8):
            raise MerchantSessionError("invalid target")

    monkeypatch.setattr(merchant_access, "validate_merchant_staff", verify_staff)
    app = FastAPI()
    app.include_router(merchant_access.router)

    def get_test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app) as client:
        yield client, settings, engine
    engine.dispose()


def test_default_disabled_and_admin_checks(setup_api):
    client, settings, _ = setup_api
    settings.merchant_access_admin_enabled = False
    assert client.get("/merchant-access/mapping").status_code == 404
    settings.merchant_access_admin_enabled = True
    assert client.get("/merchant-access/mapping").status_code == 401
    assert (
        client.get(
            "/merchant-access/mapping", headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/merchant-access/mapping", headers={"Authorization": "Bearer staff"}
        ).status_code
        == 403
    )
    assert (
        client.get("/merchant-access/mapping", headers={"Authorization": "Bearer admin"}).json()[
            "organization_id"
        ]
        == "org-a"
    )


def test_grants_are_tenant_scoped_audited_and_revocable(setup_api):
    client, _, _ = setup_api
    admin = {"Authorization": "Bearer admin"}
    assert client.put(
        "/merchant-access/shops/a/staff/8/product-read", json={"active": True}, headers=admin
    ).status_code == 409
    assert (
        client.put(
            "/merchant-access/shops/b/staff/8", json={"active": True}, headers=admin
        ).status_code
        == 409
    )
    assert (
        client.put(
            "/merchant-access/shops/a/staff/9", json={"active": True}, headers=admin
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/merchant-access/shops/a/staff/8", json={"active": True, "tenant_id": 2}, headers=admin
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/merchant-access/shops/a/staff/8", json={"active": "true"}, headers=admin
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/merchant-access/shops/a/staff/8", json={"active": True}, headers=admin
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/merchant-access/shops/a/staff/8/product-read", json={"active": True}, headers=admin
        ).status_code
        == 200
    )
    records = client.get("/merchant-access/audit", headers=admin).json()
    assert len(records) == 2 and all(item["actor"] == "merchant:1:7" for item in records)
    assert (
        client.get("/merchant-access/audit", headers={"Authorization": "Bearer other"}).json() == []
    )
    assert (
        client.put("/merchant-access/mapping", json={"active": False}, headers=admin).status_code
        == 200
    )
    assert (
        client.put("/merchant-access/mapping", json={"active": True}, headers=admin).status_code
        == 200
    )
    records = client.get("/merchant-access/audit", headers=admin).json()
    assert any(item["action"] == "grant_revoke" for item in records)
    assert (
        client.put(
            "/merchant-access/shops/a/staff/8", json={"active": False}, headers=admin
        ).status_code
        == 200
    )


def test_sqlite_rejected_for_mutation_without_test_override(setup_api, monkeypatch):
    client, _, _ = setup_api
    monkeypatch.setattr(merchant_access, "require_postgres", actual_postgres_guard)
    response = client.put(
        "/merchant-access/mapping",
        json={"active": False},
        headers={"Authorization": "Bearer admin"},
    )
    assert response.status_code == 503


def test_revoked_admin_cannot_grant_after_target_lookup(setup_api, monkeypatch):
    client, _, _ = setup_api
    calls = []

    def changing_session(_url, _token):
        calls.append(True)
        return MerchantSession(1, "a", 7, frozenset(), len(calls) == 1)

    monkeypatch.setattr(merchant_access, "validate_merchant_session", changing_session)
    response = client.put(
        "/merchant-access/shops/a/staff/8",
        json={"active": True},
        headers={"Authorization": "Bearer admin"},
    )
    assert response.status_code == 403
    assert len(calls) == 2
    with Session(setup_api[2]) as db:
        assert db.get(MerchantShopGrantModel, (1, 8, "a")) is None
