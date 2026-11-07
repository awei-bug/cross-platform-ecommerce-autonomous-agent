import os
import shutil
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Event

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import MerchantOrganizationMappingModel, MerchantShopGrantModel, ShopModel
from app.services.merchant_access_management import (
    AccessManagementError,
    set_mapping_active,
    set_shop_grant_active,
)
from app.services.merchant_scope import (
    MerchantScopeError,
    has_merchant_shop_grant,
    resolve_merchant_scope,
    shop_belongs_to_scope,
)
from app.services.merchant_session import MerchantSession


@pytest.fixture
def database():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    MerchantOrganizationMappingModel.__table__.create(engine)
    ShopModel.__table__.create(engine)
    MerchantShopGrantModel.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def merchant(tenant_id):
    return MerchantSession(tenant_id, "example", 7, frozenset({"product:read"}), False)


def test_mapping_is_explicit_inactive_by_default_and_revocable(database):
    with pytest.raises(MerchantScopeError):
        resolve_merchant_scope(database, merchant(1))
    mapping = MerchantOrganizationMappingModel(tenant_id=1, organization_id="org-a")
    database.add(mapping)
    database.commit()
    with pytest.raises(MerchantScopeError):
        resolve_merchant_scope(database, merchant(1))
    mapping.is_active = True
    database.commit()
    assert resolve_merchant_scope(database, merchant(1)).organization_id == "org-a"
    with pytest.raises(MerchantScopeError):
        resolve_merchant_scope(database, merchant(2))
    mapping.is_active = False
    database.commit()
    with pytest.raises(MerchantScopeError):
        resolve_merchant_scope(database, merchant(1))


def test_shop_organization_boundary(database):
    database.add(
        MerchantOrganizationMappingModel(tenant_id=1, organization_id="org-a", is_active=True)
    )
    database.add_all(
        [
            ShopModel(
                id="shop-a",
                organization_id="org-a",
                platform="demo",
                platform_label="demo",
                name="A",
            ),
            ShopModel(
                id="shop-b",
                organization_id="org-b",
                platform="demo",
                platform_label="demo",
                name="B",
            ),
        ]
    )
    database.commit()
    scope = resolve_merchant_scope(database, merchant(1))
    assert shop_belongs_to_scope(database, scope, "shop-a")
    assert not shop_belongs_to_scope(database, scope, "shop-b")
    assert not shop_belongs_to_scope(database, scope, "missing")


def test_grant_requires_employee_shop_and_active_mapping(database):
    mapping = MerchantOrganizationMappingModel(tenant_id=1, organization_id="org-a", is_active=True)
    shop_a = ShopModel(
        id="a", organization_id="org-a", platform="demo", platform_label="demo", name="A"
    )
    shop_b = ShopModel(
        id="b", organization_id="org-b", platform="demo", platform_label="demo", name="B"
    )
    database.add_all([mapping, shop_a, shop_b])
    database.commit()
    employee = merchant(1)
    assert not has_merchant_shop_grant(database, employee, "a")
    grant = MerchantShopGrantModel(tenant_id=1, staff_id=7, shop_id="a")
    database.add(grant)
    database.commit()
    assert not has_merchant_shop_grant(database, employee, "a")
    grant.is_active = True
    database.commit()
    assert has_merchant_shop_grant(database, employee, "a")
    other = MerchantSession(1, "example", 8, frozenset(), True)
    assert not has_merchant_shop_grant(database, other, "a")
    assert not has_merchant_shop_grant(database, merchant(2), "a")
    assert not has_merchant_shop_grant(database, employee, "b")
    shop_a.organization_id = "org-b"
    database.commit()
    assert not has_merchant_shop_grant(database, employee, "a")
    shop_a.organization_id = "org-a"
    mapping.is_active = False
    database.commit()
    assert not has_merchant_shop_grant(database, employee, "a")
    mapping.is_active = True
    grant.is_active = False
    database.commit()
    assert not has_merchant_shop_grant(database, employee, "a")


def test_grant_constraints_reject_invalid_relationships(database):
    mapping = MerchantOrganizationMappingModel(tenant_id=1, organization_id="org-a")
    shop = ShopModel(
        id="a", organization_id="org-a", platform="demo", platform_label="demo", name="A"
    )
    database.add_all([mapping, shop])
    database.commit()
    for tenant_id, staff_id, shop_id in [(2, 7, "a"), (1, 7, "missing"), (1, 0, "a")]:
        database.add(
            MerchantShopGrantModel(tenant_id=tenant_id, staff_id=staff_id, shop_id=shop_id)
        )
        with pytest.raises(IntegrityError):
            database.flush()
        database.rollback()
    database.add(MerchantShopGrantModel(tenant_id=1, staff_id=7, shop_id="a"))
    database.commit()
    database.add(MerchantShopGrantModel(tenant_id=1, staff_id=7, shop_id="a"))
    with pytest.raises(IntegrityError):
        database.flush()
    database.rollback()


def test_mapping_conflicts_and_invalid_values_are_rejected(database):
    database.add(MerchantOrganizationMappingModel(tenant_id=1, organization_id="org-a"))
    database.commit()
    for tenant_id, org in [(1, "org-b"), (2, "org-a"), (0, "org-c"), (3, " ")]:
        database.add(MerchantOrganizationMappingModel(tenant_id=tenant_id, organization_id=org))
        with pytest.raises(IntegrityError):
            database.flush()
        database.rollback()


def test_alembic_upgrade_and_downgrade_in_isolated_database(tmp_path):
    path = tmp_path / "migration.sqlite"
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite+pysqlite:///" + path.as_posix()
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, "-m", "alembic"]
    subprocess.run(
        command + ["upgrade", "head"], cwd=root, env=env, check=True, capture_output=True
    )
    engine = create_engine(env["DATABASE_URL"])
    assert "merchant_organization_mappings" in inspect(engine).get_table_names()
    assert "merchant_shop_grants" in inspect(engine).get_table_names()
    assert "merchant_access_audit" in inspect(engine).get_table_names()
    with engine.begin() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM merchant_organization_mappings")).scalar() == 0
        )
        assert conn.execute(text("SELECT count(*) FROM merchant_shop_grants")).scalar() == 0
    engine.dispose()
    subprocess.run(
        command + ["downgrade", "20261029_0019"], cwd=root, env=env, check=True, capture_output=True
    )
    engine = create_engine(env["DATABASE_URL"])
    assert "merchant_organization_mappings" not in inspect(engine).get_table_names()
    assert "merchant_shop_grants" not in inspect(engine).get_table_names()
    assert "merchant_access_audit" not in inspect(engine).get_table_names()
    engine.dispose()


@pytest.mark.skipif(
    not shutil.which("initdb") or not shutil.which("pg_ctl"),
    reason="PostgreSQL temporary cluster tools not installed",
)
def test_alembic_migration_on_temporary_postgres(tmp_path, monkeypatch, capsys):
    cluster = tmp_path / "cluster"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    subprocess.run(
        [
            "initdb",
            "-D",
            str(cluster),
            "-A",
            "trust",
            "-U",
            "postgres",
            "--no-locale",
            "--encoding=UTF8",
        ],
        check=True,
        capture_output=True,
    )
    pg_command = ["pg_ctl", "-D", str(cluster)]
    subprocess.run(
        pg_command
        + ["-l", str(tmp_path / "postgres.log"), "-o", f"-h 127.0.0.1 -p {port}", "-w", "start"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=40,
    )
    try:
        env = os.environ.copy()
        env["DATABASE_URL"] = f"postgresql+psycopg://postgres@127.0.0.1:{port}/postgres"
        root = Path(__file__).resolve().parents[1]
        command = [sys.executable, "-m", "alembic"]
        result = subprocess.run(
            command + ["upgrade", "head"], cwd=root, env=env, capture_output=True
        )
        assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
        engine = create_engine(env["DATABASE_URL"])
        assert "merchant_shop_grants" in inspect(engine).get_table_names()
        assert "merchant_access_audit" in inspect(engine).get_table_names()
        with engine.begin() as conn:
            assert conn.execute(text("SELECT count(*) FROM merchant_shop_grants")).scalar() == 0
        with Session(engine) as db:
            db.add_all(
                [
                    MerchantOrganizationMappingModel(
                        tenant_id=11, organization_id="org-a", is_active=True
                    ),
                    ShopModel(
                        id="shop-a",
                        organization_id="org-a",
                        platform="demo",
                        platform_label="demo",
                        name="A",
                    ),
                ]
            )
            db.commit()
        started = Event()

        def concurrent_grant():
            with Session(engine) as db:
                started.set()
                try:
                    set_shop_grant_active(db, 11, 7, "shop-a", True, actor="operator")
                    db.commit()
                    return "granted"
                except AccessManagementError:
                    db.rollback()
                    return "denied"

        with ThreadPoolExecutor(max_workers=1) as pool:
            with Session(engine) as db:
                set_mapping_active(db, 11, False, actor="operator")
                future = pool.submit(concurrent_grant)
                assert started.wait(5)
                with pytest.raises(TimeoutError):
                    future.result(timeout=0.3)
                db.commit()
            assert future.result(timeout=5) == "denied"
        from datetime import UTC, datetime
        from types import SimpleNamespace

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.routes import merchant_access, merchant_products
        from app.db.models import ProductModel
        from app.db.session import get_db

        monkeypatch.setattr(
            merchant_access,
            "get_settings",
            lambda: SimpleNamespace(
                merchant_access_admin_enabled=True, merchant_identity_url="http://127.0.0.1:5000"
            ),
        )
        monkeypatch.setattr(
            merchant_access,
            "validate_merchant_session",
            lambda _url, _token: MerchantSession(11, "demo", 1, frozenset(), True),
        )
        monkeypatch.setattr(merchant_access, "validate_merchant_staff", lambda *_args: None)
        monkeypatch.setattr(
            merchant_products,
            "get_settings",
            lambda: SimpleNamespace(
                merchant_product_read_enabled=True, merchant_identity_url="http://127.0.0.1:5000"
            ),
        )
        monkeypatch.setattr(
            merchant_products,
            "validate_merchant_session",
            lambda _url, _token: MerchantSession(11, "demo", 7, frozenset({"product:read"}), False),
        )
        with Session(engine) as db:
            db.add(
                ProductModel(
                    id="p-a",
                    organization_id="org-a",
                    shop_id="shop-a",
                    sku="SKU",
                    title="demo",
                    platform="douyin",
                    platform_label="demo",
                    shop_name="shop-a",
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
            db.commit()
        app = FastAPI()
        app.include_router(merchant_access.router)
        app.include_router(merchant_products.router)

        def test_db():
            with Session(engine) as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer test-token"}
            assert (
                client.put(
                    "/merchant-access/mapping", json={"active": True}, headers=headers
                ).status_code
                == 200
            )
            assert (
                client.put(
                    "/merchant-access/shops/shop-a/staff/7", json={"active": True}, headers=headers
                ).status_code
                == 200
            )
            assert client.get("/merchant-products/shop-a", headers=headers).status_code == 404
            assert (
                client.put(
                    "/merchant-access/shops/shop-a/staff/7/product-read",
                    json={"active": True},
                    headers=headers,
                ).status_code
                == 200
            )
            product_response = client.get("/merchant-products/shop-a", headers=headers)
            assert product_response.status_code == 200
            assert [item["id"] for item in product_response.json()["items"]] == ["p-a"]
            assert (
                client.put(
                    "/merchant-access/shops/shop-a/staff/7/product-read",
                    json={"active": False},
                    headers=headers,
                ).status_code
                == 200
            )
            assert client.get("/merchant-products/shop-a", headers=headers).status_code == 404
            audit = client.get("/merchant-access/audit", headers=headers).json()
            assert any(
                row["action"] == "grant_state" and row["actor"] == "merchant:11:1" for row in audit
            )
        import io

        from app.scripts import provision_merchant_mapping as cli

        with Session(engine) as db:
            db.add(
                ShopModel(
                    id="shop-b",
                    organization_id="org-b",
                    platform="demo",
                    platform_label="demo",
                    name="B",
                )
            )
            db.commit()
        monkeypatch.setattr(cli, "get_engine", lambda: engine)
        monkeypatch.setattr(
            cli,
            "get_settings",
            lambda: SimpleNamespace(merchant_identity_url="http://127.0.0.1:5000"),
        )
        monkeypatch.setattr(
            cli,
            "validate_merchant_session",
            lambda *_args: MerchantSession(12, "demo", 2, frozenset(), True),
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO("test-token\n"))
        assert cli.main(["--shop-id", "shop-b", "--apply", "--confirm-organization", "org-b"]) == 0
        assert "test-token" not in capsys.readouterr().out
        with Session(engine) as db:
            mapping = db.get(MerchantOrganizationMappingModel, 12)
            assert mapping.organization_id == "org-b" and mapping.is_active is False
        engine.dispose()
        subprocess.run(
            command + ["downgrade", "20261029_0019"],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
        )
        engine = create_engine(env["DATABASE_URL"])
        assert "merchant_shop_grants" not in inspect(engine).get_table_names()
        assert "merchant_access_audit" not in inspect(engine).get_table_names()
        assert "merchant_organization_mappings" not in inspect(engine).get_table_names()
        engine.dispose()
    finally:
        subprocess.run(
            pg_command + ["-m", "fast", "-w", "stop"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=40,
        )
