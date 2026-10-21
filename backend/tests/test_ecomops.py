"""Authorization, DAG handoff, event recovery and truthful platform boundaries."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.ecomops import OpsEvent, OpsRun, OpsSchedule, OpsTask
from app.db.session import session_scope
from app.main import app
from app.schemas.auth import UserProfile
from app.schemas.ecomops import BusinessInput
from app.services.ecomops_service import recover_and_tick
from app.services.ecomops_specialists import costs

HEADERS = {"Authorization": "Bearer demo-access-token"}
ROOT = "/api/v1/ecomops"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def create(client, workflow, **data):
    response = client.post(
        f"{ROOT}/runs",
        headers=HEADERS,
        json={
            "workflow": workflow,
            "title": f"test {workflow}",
            "idempotency_key": uuid4().hex,
            "input": data,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def intervene(client, run, action, task=None):
    return client.post(
        f"{ROOT}/runs/{run['id']}/intervene",
        headers=HEADERS,
        json={
            "action": action,
            "review_version": run["config_version"],
            "note": "已核验测试证据",
            "task_id": task["id"] if task else None,
        },
    )


def import_basics(client):
    response = client.post(
        f"{ROOT}/data/import",
        headers=HEADERS,
        json={
            "records": [
                {
                    "kind": "product",
                    "key": " test-sku ",
                    "data": {"title": "Storage box"},
                    "source": "test fixture",
                    "is_demo": True,
                },
                {
                    "kind": "product",
                    "key": "TEST-SKU",
                    "data": {},
                    "source": "test fixture",
                    "is_demo": True,
                },
                {"kind": "supplier", "key": "test-supplier", "data": {}, "source": "test fixture"},
                {
                    "kind": "competitor",
                    "key": "test-competitor",
                    "data": {"price": 30},
                    "source": "test fixture",
                    "is_demo": True,
                },
            ]
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["deduplicated"] == 1


@pytest.fixture
def initialized(client):
    import_basics(client)
    run = create(client, "initialization")
    assert run["status"] == "succeeded", run
    return client


def test_auth_and_validation(client):
    assert client.get(f"{ROOT}/overview").status_code == 401
    assert (
        client.post(
            f"{ROOT}/runs",
            headers=HEADERS,
            json={
                "workflow": "unknown",
                "title": "bad",
                "idempotency_key": uuid4().hex,
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{ROOT}/runs",
            headers=HEADERS,
            json={
                "workflow": "selection",
                "title": "bad",
                "idempotency_key": uuid4().hex,
                "input": {"commission_pct": 90, "ad_rate_pct": 20},
            },
        ).status_code
        == 422
    )


def test_import_atomic_validation(client):
    result = client.post(
        f"{ROOT}/data/import",
        headers=HEADERS,
        json={
            "records": [
                {"kind": "metric", "key": "bad", "source": "test", "data": {"revenue": "nan"}},
            ]
        },
    )
    assert result.status_code == 422
    result = client.post(
        f"{ROOT}/data/import",
        headers=HEADERS,
        json={
            "records": [
                {"kind": "metric", "key": "bad", "source": "test", "data": {"currency": "EUR"}},
            ]
        },
    )
    assert result.status_code == 422


def test_landed_cost_math():
    result = costs(
        BusinessInput(
            price=30, procurement=8, freight=2, tax=1, loss=1, commission_pct=15, ad_rate_pct=10
        )
    )
    assert result["landed_cost"] == 19.5
    assert result["break_even_price"] == 16
    assert result["margin_pct"] == 35


def test_selection_branches_and_idempotency(initialized):
    client = initialized
    body = {
        "workflow": "selection",
        "title": "launch",
        "idempotency_key": uuid4().hex,
        "input": {"sku": "TEST-SKU", "title": "Storage box", "price": 30, "procurement": 8},
    }
    first = client.post(f"{ROOT}/runs", headers=HEADERS, json=body).json()
    assert first["status"] == "succeeded", first
    handoff = next(t for t in first["tasks"] if t["key"] == "handoff")
    assert len(handoff["dependencies"]) == len(handoff["output"]["work_orders"]) == 3
    assert {t["owner"] for t in handoff["output"]["work_orders"]} == {
        "listing",
        "fulfillment",
        "marketing",
    }
    second = client.post(f"{ROOT}/runs", headers=HEADERS, json=body).json()
    assert second["id"] == first["id"]
    assert second["tasks"] == first["tasks"]
    body["input"]["price"] = 31
    assert client.post(f"{ROOT}/runs", headers=HEADERS, json=body).status_code == 409


def test_stock_review_resume_and_rejection(initialized):
    client = initialized
    run = create(client, "selection", price=30, procurement=8, quantity=2000)
    assert run["status"] == "waiting_review", run
    task = next(t for t in run["tasks"] if t["status"] == "waiting_review")
    assert "备货" in task["reason"]
    response = intervene(client, run, "approve", task)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "succeeded", response.text
    assert response.json()["audits"][-1]["action"] == "approve"
    run = create(client, "selection", price=30, procurement=8, quantity=2000)
    task = next(t for t in run["tasks"] if t["status"] == "waiting_review")
    response = intervene(client, run, "reject", task)
    assert response.json()["status"] == "rejected"
    assert all(
        t["status"] in {"succeeded", "cancelled", "rejected"} for t in response.json()["tasks"]
    )


@pytest.mark.parametrize(
    "workflow,data,reason",
    [
        ("marketing", {"budget_before": 100, "budget_after": 130}, "预算"),
        ("service", {"service_intent": "refund", "refund_amount": 60}, "退款"),
    ],
)
def test_forced_reviews(initialized, workflow, data, reason):
    run = create(initialized, workflow, **data)
    assert run["status"] == "waiting_review", run
    assert any(reason in t["reason"] for t in run["tasks"])
    review = next(t for t in run["tasks"] if t["status"] == "waiting_review")
    assert review["output"]["review_facts"]


def test_emergency_cannot_be_approved(initialized):
    run = create(initialized, "service", content="违禁品")
    assert run["status"] == "terminated"
    from app.db.models import AlertModel

    with session_scope() as db:
        alerts = list(
            db.scalars(select(AlertModel).where(AlertModel.description.contains(run["id"])))
        )
        assert alerts and alerts[0].severity == "critical"
    assert intervene(initialized, run, "resume").status_code == 409
    run = create(initialized, "marketing", ad_spend=101, budget_after=100)
    assert run["status"] == "terminated"


def test_listing_completes_reviewed_draft_without_fake_publishing(initialized):
    client = initialized
    run = create(client, "listing", title="全球第一 Storage box")
    copy = next(t for t in run["tasks"] if t["key"] == "listing_copy")
    assert "全球第一" not in copy["output"]["title"]
    assert copy["risk"] == "low"
    assert run["status"] == "waiting_review"
    task = next(t for t in run["tasks"] if t["status"] == "waiting_review")
    result = intervene(client, run, "approve", task).json()
    assert result["status"] == "succeeded", result
    assert all(t["output"]["platform_write"] is False for t in result["tasks"])
    assert {t["key"] for t in result["tasks"]} == {"listing_copy", "listing_check"}


def test_low_selection_returns_to_market(initialized):
    run = create(initialized, "selection", price=10, procurement=9)
    assert run["status"] == "rejected"
    task = next(t for t in run["tasks"] if t["key"] == "evaluate")
    assert task["output"]["return_to"] == "market"
    assert all(t["status"] == "cancelled" for t in run["tasks"] if "evaluate" in t["dependencies"])


def test_analytics_and_policy_versions(initialized):
    client = initialized
    result = client.post(
        f"{ROOT}/data/import",
        headers=HEADERS,
        json={
            "records": [
                {
                    "kind": "metric",
                    "key": "test-metrics",
                    "source": "fixture isolated period",
                    "data": {
                        "revenue": 1000,
                        "cost": 600,
                        "orders": 100,
                        "refunds": 20,
                        "ad_spend": 100,
                    },
                },
            ]
        },
    )
    assert result.status_code == 200
    run = create(client, "analytics")
    assert run["status"] == "succeeded"
    metrics = next(t for t in run["tasks"] if t["key"] == "aggregate")["output"]
    assert metrics["gmv"] >= 1000 and metrics["evidence"]
    config = client.get(f"{ROOT}/overview", headers=HEADERS).json()["configuration"]
    updated = client.put(
        f"{ROOT}/configuration",
        headers=HEADERS,
        json={
            "version": config["version"],
            "policy": config["payload"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == config["version"] + 1
    assert (
        client.put(
            f"{ROOT}/configuration",
            headers=HEADERS,
            json={
                "version": config["version"],
                "policy": config["payload"],
            },
        ).status_code
        == 409
    )


def test_takeover_recovery_and_schedule_dedupe(initialized):
    client = initialized
    run = create(client, "fulfillment")
    assert run["status"] == "waiting_data"
    assert intervene(client, run, "takeover").json()["status"] == "taken_over"
    assert intervene(client, run, "resume").json()["status"] == "waiting_data"
    schedule = client.post(
        f"{ROOT}/schedules",
        headers=HEADERS,
        json={
            "workflow": "analytics",
            "interval_hours": 24,
        },
    ).json()
    recover_and_tick()
    with session_scope() as db:
        row = db.get(OpsSchedule, schedule["id"])
        assert row.next_run_at.replace(tzinfo=UTC) > datetime.now(UTC)
        count = len(
            list(
                db.scalars(
                    select(OpsRun).where(
                        OpsRun.idempotency_key.startswith(schedule["id"]),
                    )
                )
            )
        )
    recover_and_tick()
    with session_scope() as db:
        assert (
            len(
                list(
                    db.scalars(
                        select(OpsRun).where(
                            OpsRun.idempotency_key.startswith(schedule["id"]),
                        )
                    )
                )
            )
            == count
            == 1
        )


def test_pending_outbox_recovery_and_stale_timeout(initialized):
    from app.schemas.ecomops import RunCreate
    from app.services.ecomops_service import create_run as create_run_service

    client = initialized
    overview = client.get(f"{ROOT}/overview", headers=HEADERS).json()
    org = overview["configuration"]["organization_id"]
    with session_scope() as db:
        row = create_run_service(
            db,
            org,
            "test",
            RunCreate(
                workflow="analytics",
                title="outbox recovery",
                idempotency_key=uuid4().hex,
            ),
        )
        run_id = row.id
    recover_and_tick(org)
    run = client.get(f"{ROOT}/runs/{run_id}", headers=HEADERS).json()
    assert run["status"] == "succeeded"
    run = create(client, "fulfillment")
    with session_scope() as db:
        task = db.scalar(select(OpsTask).where(OpsTask.run_id == run["id"]))
        task.status = "running"
        task.started_at = datetime.now(UTC) - timedelta(minutes=20)
    recover_and_tick(org)
    detail = client.get(f"{ROOT}/runs/{run['id']}", headers=HEADERS).json()
    assert any(t["status"] == "failed" and "15 分钟" in t["reason"] for t in detail["tasks"])


def test_organization_isolation_and_write_permission(initialized):
    from app.core.security import require_demo_user

    run = create(initialized, "analytics")
    other = UserProfile(
        id="other", name="other", role_name="viewer", organization_id="other-org", permissions=[]
    )
    app.dependency_overrides[require_demo_user] = lambda: other
    try:
        assert initialized.get(f"{ROOT}/runs/{run['id']}", headers=HEADERS).status_code == 404
        assert (
            initialized.post(
                f"{ROOT}/runs",
                headers=HEADERS,
                json={
                    "workflow": "analytics",
                    "title": "denied",
                    "idempotency_key": uuid4().hex,
                },
            ).status_code
            == 403
        )
        assert initialized.get(f"{ROOT}/data", headers=HEADERS).json() == []
    finally:
        app.dependency_overrides.clear()


def test_initialization_gate_for_new_org(initialized):
    from app.core.security import require_demo_user

    user = UserProfile(
        id="new",
        name="new",
        role_name="admin",
        organization_id=uuid4().hex,
        permissions=["automation:manage"],
    )
    app.dependency_overrides[require_demo_user] = lambda: user
    try:
        run = create(initialized, "analytics")
        assert run["status"] == "waiting_initialization"
        with session_scope() as db:
            assert not list(
                db.scalars(
                    select(OpsEvent).where(
                        OpsEvent.run_id == run["id"],
                        OpsEvent.topic == "task.succeeded",
                    )
                )
            )
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def ai_config(initialized, monkeypatch):
    from app.core.config import get_settings
    from app.db.models import AiConfigurationModel

    org = initialized.get(f"{ROOT}/overview", headers=HEADERS).json()["configuration"][
        "organization_id"
    ]
    config_id = uuid4().hex
    with session_scope() as db:
        db.add(
            AiConfigurationModel(
                id=config_id,
                organization_id=org,
                provider_id="ollama",
                display_name="test model",
                base_url="http://127.0.0.1:11434",
                selected_model="test-model",
                is_demo=False,
                is_enabled=True,
                status="ready",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    monkeypatch.setattr(get_settings(), "ai_live_generation_enabled", True)
    yield initialized
    with session_scope() as db:
        db.delete(db.get(AiConfigurationModel, config_id))


def test_model_output_scanned_and_review_keeps_exact_candidate(ai_config, monkeypatch):
    from app.services import ecomops_ai

    calls = []

    async def fake_generate(*args, **kwargs):
        calls.append(args)
        return "Storage box: 100% cure"

    monkeypatch.setattr(ecomops_ai, "generate_text", fake_generate)
    run = create(ai_config, "listing", title="Storage box", use_ai=True)
    assert run["status"] == "waiting_review"
    task = next(t for t in run["tasks"] if t["key"] == "listing_copy")
    assert task["status"] == "waiting_review"
    assert task["output"]["ai_status"] == "generated"
    response = intervene(ai_config, run, "approve", task)
    assert response.status_code == 200, response.text
    approved = next(t for t in response.json()["tasks"] if t["key"] == "listing_copy")
    assert approved["output"]["model_draft"] == "Storage box: 100% cure"
    assert approved["output"]["human_verified"] is True
    assert len(calls) == 1


def test_model_high_risk_and_failure_fallback(ai_config, monkeypatch):
    from app.services import ecomops_ai

    async def high_risk(*args, **kwargs):
        return "违禁品"

    monkeypatch.setattr(ecomops_ai, "generate_text", high_risk)
    run = create(ai_config, "listing", title="Storage box", use_ai=True)
    assert run["status"] == "terminated"

    async def failed(*args, **kwargs):
        raise RuntimeError("secret-api-key-must-not-leak")

    monkeypatch.setattr(ecomops_ai, "generate_text", failed)
    run = create(ai_config, "listing", title="Storage box", use_ai=True)
    task = next(t for t in run["tasks"] if t["key"] == "listing_copy")
    assert task["output"]["ai_status"] == "fallback"
    assert "secret-api-key" not in str(run)


def test_sensitive_data_masking(initialized):
    client = initialized
    response = client.post(
        f"{ROOT}/data/import",
        headers=HEADERS,
        json={
            "records": [
                {
                    "kind": "customer",
                    "key": "private",
                    "source": "test",
                    "data": {
                        "name": "Private Name",
                        "email": "private@example.com",
                        "nested": {"phone": "123456789"},
                    },
                },
            ]
        },
    )
    assert response.status_code == 200
    rows = client.get(f"{ROOT}/data?kind=customer", headers=HEADERS).json()
    assert rows[-1]["payload"]["name"] == "***"
    assert "private@example.com" not in str(rows)
    run = create(
        client,
        "fulfillment",
        destination_address="private street",
        order_key="test-order",
        sku="TEST-SKU",
        quantity=1,
    )
    assert run["input"]["destination_address"] == "***"


def test_frozen_input_has_explicit_recovery_path(initialized):
    run = create(initialized, "fulfillment")
    task = next(t for t in run["tasks"] if t["key"] == "order_check")
    assert task["status"] == "waiting_data"
    assert task["output"]["recovery"] == "new_run_required"


def test_late_summary_cannot_overwrite_stop(initialized):
    from sqlalchemy import update

    from app.services.ecomops_service import summarize

    run = create(initialized, "fulfillment")
    with session_scope() as db:
        cached = db.get(OpsRun, run["id"])
        db.execute(
            update(OpsRun)
            .where(OpsRun.id == cached.id)
            .values(
                status="terminated",
            )
            .execution_options(synchronize_session=False)
        )
        assert cached.status != "terminated"
        summarize(db, cached)
        assert cached.status == "terminated"


def test_rule_changes_require_fresh_review(initialized):
    client = initialized
    run = create(client, "marketing", budget_before=100, budget_after=150)
    task = next(t for t in run["tasks"] if t["status"] == "waiting_review")
    config = client.get(f"{ROOT}/overview", headers=HEADERS).json()["configuration"]
    result = client.put(
        f"{ROOT}/configuration",
        headers=HEADERS,
        json={
            "version": config["version"],
            "policy": config["payload"],
        },
    )
    assert result.status_code == 200
    assert intervene(client, run, "approve", task).status_code == 409
    updated = intervene(client, run, "reevaluate", task)
    assert updated.status_code == 200
    assert updated.json()["config_version"] == config["version"] + 1
    fresh = updated.json()
    fresh_task = next(t for t in fresh["tasks"] if t["status"] == "waiting_review")
    assert fresh_task["output"]["review_facts"][-1]["value"] == 20
    assert intervene(client, fresh, "approve", fresh_task).status_code == 200


@pytest.mark.parametrize("workflow", ["iteration", "expansion"])
def test_retired_workflows_cannot_be_created(client, workflow):
    response = client.post(
        f"{ROOT}/runs",
        headers=HEADERS,
        json={"workflow": workflow, "title": "retired", "idempotency_key": uuid4().hex},
    )
    assert response.status_code == 422
    assert (
        client.post(f"{ROOT}/schedules", headers=HEADERS, json={"workflow": workflow}).status_code
        == 422
    )


def test_marketing_snapshot_check_is_reachable_without_ad_adapter(initialized):
    run = create(initialized, "marketing", budget_before=100, budget_after=100, ad_spend=80)
    assert run["status"] == "succeeded", run
    monitor = next(t for t in run["tasks"] if t["key"] == "ad_monitor")
    assert monitor["output"]["spend"] == 80
    assert all(t["output"]["platform_write"] is False for t in run["tasks"])


def test_retired_run_and_schedule_keep_history_without_breaking_tick(initialized):
    run = create(initialized, "analytics")
    schedule_id = uuid4().hex
    with session_scope() as db:
        row = db.get(OpsRun, run["id"])
        row.workflow, row.status = "iteration", "queued"
        db.add(
            OpsSchedule(
                id=schedule_id,
                organization_id=row.organization_id,
                workflow="iteration",
                interval_hours=24,
                input={},
                enabled=True,
                next_run_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
    recover_and_tick("org-demo-001")
    result = initialized.get(f"{ROOT}/runs/{run['id']}", headers=HEADERS).json()
    assert result["status"] == "cancelled"
    assert result["tasks"] and all(t["output"] for t in result["tasks"])
    assert any(a["action"] == "workflow_retired" for a in result["audits"])
    with session_scope() as db:
        assert db.get(OpsSchedule, schedule_id).enabled is False
    assert (
        initialized.patch(
            f"{ROOT}/schedules/{schedule_id}", headers=HEADERS, json={"enabled": True}
        ).status_code
        == 409
    )


def test_old_external_steps_still_cannot_perform_writes(initialized):
    from app.services.ecomops_service import execute_step

    run = create(initialized, "analytics")
    task_id = uuid4().hex
    with session_scope() as db:
        row = db.get(OpsRun, run["id"])
        row.status = "queued"
        db.add(
            OpsTask(
                id=task_id,
                run_id=row.id,
                organization_id=row.organization_id,
                key="publish",
                agent="listing",
                title="历史上架步骤",
                dependencies=[],
                status="queued",
                output={},
                reason="",
                risk="none",
                attempts=0,
            )
        )
    execute_step("org-demo-001", run["id"], task_id)
    result = initialized.get(f"{ROOT}/runs/{run['id']}", headers=HEADERS).json()
    task = next(t for t in result["tasks"] if t["id"] == task_id)
    assert task["status"] == "waiting_integration"
    assert task["output"]["platform_write"] is False
