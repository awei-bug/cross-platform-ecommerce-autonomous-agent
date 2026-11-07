import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import (
    MerchantAccessAuditModel,
    MerchantOrganizationMappingModel,
    MerchantShopGrantModel,
    ShopModel,
)
from app.services.merchant_access_management import (
    AccessManagementError,
    provision_mapping,
    set_mapping_active,
    set_shop_grant_active,
)
from app.services.merchant_scope import has_merchant_shop_grant
from app.services.merchant_session import MerchantSession


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for model in (
        MerchantOrganizationMappingModel,
        ShopModel,
        MerchantShopGrantModel,
        MerchantAccessAuditModel,
    ):
        model.__table__.create(engine)
    with Session(engine) as session:
        session.add_all(
            [
                MerchantOrganizationMappingModel(
                    tenant_id=1, organization_id="org-a", is_active=True
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
        session.commit()
        yield session
    engine.dispose()


def test_disable_and_reenable_never_restore_old_grants_and_audit_each_change(db):
    user = MerchantSession(1, "shop", 7, frozenset(), False)
    set_shop_grant_active(db, 1, 7, "a", True, actor="operator-1")
    db.commit()
    assert has_merchant_shop_grant(db, user, "a")
    set_mapping_active(db, 1, False, actor="operator-1")
    db.commit()
    set_mapping_active(db, 1, True, actor="operator-1")
    db.commit()
    assert not has_merchant_shop_grant(db, user, "a")
    records = db.scalars(select(MerchantAccessAuditModel)).all()
    assert [r.action for r in records].count("grant_revoke") == 1
    assert [r.action for r in records].count("mapping_state") == 2
    assert all(r.actor == "operator-1" and r.tenant_id == 1 for r in records)
    revoked = next(r for r in records if r.action == "grant_revoke")
    assert (revoked.target_staff_id, revoked.target_shop_id, revoked.before, revoked.after) == (
        7,
        "a",
        {"active": True, "can_read_products": False},
        {"active": False, "can_read_products": False},
    )


def test_enabling_preexisting_disabled_mapping_clears_legacy_active_grants(db):
    mapping = db.get(MerchantOrganizationMappingModel, 1)
    mapping.is_active = False
    db.add(MerchantShopGrantModel(tenant_id=1, staff_id=7, shop_id="a", is_active=True))
    db.commit()
    set_mapping_active(db, 1, True, actor="operator")
    db.commit()
    assert not db.get(MerchantShopGrantModel, (1, 7, "a")).is_active


def test_rejects_invalid_actor_cross_organization_and_disabled_mapping(db):
    for actor, shop_id in [("", "a"), ("operator", "b")]:
        with pytest.raises(AccessManagementError):
            set_shop_grant_active(db, 1, 7, shop_id, True, actor=actor)
        db.rollback()
    set_mapping_active(db, 1, False, actor="operator")
    db.commit()
    with pytest.raises(AccessManagementError):
        set_shop_grant_active(db, 1, 7, "a", True, actor="operator")
    db.rollback()
    assert db.get(MerchantShopGrantModel, (1, 7, "a")) is None


def test_audit_failure_rolls_back_grant_and_mapping(db, monkeypatch):
    set_shop_grant_active(db, 1, 7, "a", True, actor="operator")
    db.commit()
    before = len(db.scalars(select(MerchantAccessAuditModel)).all())
    import app.services.merchant_access_management as management

    original = management._audit

    def broken_audit(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("audit failed")

    monkeypatch.setattr(management, "_audit", broken_audit)
    with pytest.raises(RuntimeError):
        set_mapping_active(db, 1, False, actor="operator")
    db.rollback()
    assert db.get(MerchantOrganizationMappingModel, 1).is_active
    assert db.get(MerchantShopGrantModel, (1, 7, "a")).is_active
    assert len(db.scalars(select(MerchantAccessAuditModel)).all()) == before


def test_noop_does_not_add_audit_entries(db):
    set_mapping_active(db, 1, True, actor="operator")
    set_shop_grant_active(db, 1, 7, "a", False, actor="operator")
    db.commit()
    assert db.scalars(select(MerchantAccessAuditModel)).all() == []


def test_provision_is_disabled_explicit_and_audited(db):
    mapping = provision_mapping(db, 3, "b", actor="merchant:3:10")
    db.commit()
    assert mapping.organization_id == "org-b" and mapping.is_active is False
    audit = db.scalars(select(MerchantAccessAuditModel)).one()
    assert audit.action == "mapping_create" and audit.actor == "merchant:3:10"
    assert audit.target_shop_id == "b"
    assert audit.after == {"organization_id": "org-b", "active": False, "method": "local_operator"}
    for tenant_id, shop_id in [(3, "b"), (4, "b"), (4, "missing"), (0, "a")]:
        with pytest.raises(AccessManagementError):
            provision_mapping(db, tenant_id, shop_id, actor="operator")
        db.rollback()


def test_provision_and_audit_are_rolled_back_together(db):
    provision_mapping(db, 3, "b", actor="operator")
    db.rollback()
    assert db.get(MerchantOrganizationMappingModel, 3) is None
    assert db.scalars(select(MerchantAccessAuditModel)).all() == []


def test_cli_preview_and_explicit_apply(db, monkeypatch, capsys):
    import io
    import json
    import sys
    from types import SimpleNamespace

    from app.scripts import provision_merchant_mapping as cli

    monkeypatch.setattr(
        cli, "get_settings", lambda: SimpleNamespace(merchant_identity_url="http://127.0.0.1:5000")
    )
    monkeypatch.setattr(cli, "get_engine", lambda: db.get_bind())
    monkeypatch.setattr(cli, "_is_postgres", lambda _engine: True)
    merchant = MerchantSession(3, "demo", 10, frozenset(), True)
    monkeypatch.setattr(cli, "validate_merchant_session", lambda _url, _token: merchant)
    monkeypatch.setattr(sys, "stdin", io.StringIO("sensitive-token\n"))
    assert cli.main(["--shop-id", "b"]) == 0
    output = capsys.readouterr().out
    assert "sensitive-token" not in output and json.loads(output)["mode"] == "preview"
    db.expire_all()
    assert db.get(MerchantOrganizationMappingModel, 3) is None
    monkeypatch.setattr(sys, "stdin", io.StringIO("sensitive-token\n"))
    assert cli.main(["--shop-id", "b", "--apply", "--confirm-organization", "wrong"]) == 1
    assert "sensitive-token" not in capsys.readouterr().err
    monkeypatch.setattr(sys, "stdin", io.StringIO("sensitive-token\n"))
    assert cli.main(["--shop-id", "b", "--apply", "--confirm-organization", "org-b"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "created"
    db.expire_all()
    assert db.get(MerchantOrganizationMappingModel, 3).is_active is False


def test_cli_rolls_back_if_admin_loses_access(db, monkeypatch, capsys):
    import io
    import sys
    from types import SimpleNamespace

    from app.scripts import provision_merchant_mapping as cli

    monkeypatch.setattr(
        cli, "get_settings", lambda: SimpleNamespace(merchant_identity_url="http://127.0.0.1:5000")
    )
    monkeypatch.setattr(cli, "get_engine", lambda: db.get_bind())
    monkeypatch.setattr(cli, "_is_postgres", lambda _engine: True)
    calls = []

    def session(_url, _token):
        calls.append(True)
        return MerchantSession(3, "demo", 10, frozenset(), len(calls) == 1)

    monkeypatch.setattr(cli, "validate_merchant_session", session)
    monkeypatch.setattr(sys, "stdin", io.StringIO("token\n"))
    assert cli.main(["--shop-id", "b", "--apply", "--confirm-organization", "org-b"]) == 1
    assert len(calls) == 2
    db.expire_all()
    assert db.get(MerchantOrganizationMappingModel, 3) is None
    assert db.scalars(select(MerchantAccessAuditModel)).all() == []
