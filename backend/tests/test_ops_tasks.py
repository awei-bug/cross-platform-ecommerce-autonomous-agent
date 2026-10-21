"""任务运维测试：超时巡检、重试、死信与监控指标。"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.models import GenerationJobModel, OperationJobModel
from app.db.session import session_scope
from app.main import app

SHANGHAI = ZoneInfo("Asia/Shanghai")
AUTH_HEADERS = {"Authorization": "Bearer demo-access-token"}


@pytest.fixture(scope="module")
def client(tmp_path_factory) -> TestClient:
    settings = get_settings()
    original_path = settings.asset_storage_local_path
    settings.asset_storage_local_path = str(tmp_path_factory.mktemp("assets"))
    with TestClient(app) as test_client:
        yield test_client
    settings.asset_storage_local_path = original_path


def _seed_stale_operation_job() -> str:
    """构造一个 running 且已超时的操作任务。"""
    now = datetime.now(SHANGHAI)
    job_id = f"op-job-stale-{now.strftime('%H%M%S%f')}"
    with session_scope() as db:
        db.add(
            OperationJobModel(
                id=job_id,
                kind="product",
                action="sync",
                idempotency_key=f"stale-{job_id}",
                status="running",
                progress=45,
                total=1,
                created_at=now - timedelta(minutes=40),
                started_at=now - timedelta(minutes=40),
                updated_at=now - timedelta(minutes=40),
                attempts=1,
                max_attempts=3,
            )
        )
    return job_id


def _seed_exhausted_failed_job() -> str:
    """构造一个失败且重试耗尽的生成任务。"""
    now = datetime.now(SHANGHAI)
    job_id = f"gen-job-dead-{now.strftime('%H%M%S%f')}"
    with session_scope() as db:
        db.add(
            GenerationJobModel(
                id=job_id,
                organization_id="org-demo-001",
                asset_id=None,
                configuration_id=None,
                asset_type="copy",
                prompt="按时效生成候选文案",
                model_id="demo-copy-v1",
                status="failed",
                progress=100,
                error_message="上游模型超时",
                attempts=3,
                max_attempts=3,
                created_at=now - timedelta(hours=1),
                updated_at=now - timedelta(hours=1),
            )
        )
    return job_id


def _seed_retryable_generation_job() -> str:
    """构造一个可重试的失败生成任务（无配置走演示分支，重试后会成功）。"""
    now = datetime.now(SHANGHAI)
    job_id = f"gen-job-retry-{now.strftime('%H%M%S%f')}"
    with session_scope() as db:
        db.add(
            GenerationJobModel(
                id=job_id,
                organization_id="org-demo-001",
                asset_id=None,
                configuration_id=None,
                asset_type="copy",
                prompt="重试后应成功的候选文案",
                model_id="demo-copy-v1",
                status="failed",
                progress=100,
                error_message="第一次执行失败",
                attempts=1,
                max_attempts=3,
                created_at=now - timedelta(minutes=20),
                updated_at=now - timedelta(minutes=20),
            )
        )
    return job_id


def test_metrics_cover_three_task_kinds(client: TestClient) -> None:
    # 先跑一次真实任务，让指标有数据
    client.post(
        "/api/v1/products/batch-actions",
        json={
            "action": "sync",
            "product_ids": ["product-10028"],
            "idempotency_key": "ops-metrics-1",
        },
        headers=AUTH_HEADERS,
    )
    metrics = client.get("/api/v1/ops/metrics", headers=AUTH_HEADERS)
    assert metrics.status_code == 200
    payload = metrics.json()
    assert set(payload["by_kind"]) == {"operation_job", "generation_job", "agent_run"}
    assert payload["totals"]["total"] >= 1
    assert 0 <= payload["failure_rate"] <= 1
    assert payload["avg_duration_seconds"] >= 0


def test_sweep_marks_stale_running_task_as_failed(client: TestClient) -> None:
    job_id = _seed_stale_operation_job()
    sweep = client.post("/api/v1/ops/tasks/sweep", headers=AUTH_HEADERS)
    assert sweep.status_code == 200
    timed_out_ids = {item["id"] for item in sweep.json()["timed_out"]}
    assert job_id in timed_out_ids

    tasks = client.get(
        "/api/v1/ops/tasks", params={"kind": "operation_job"}, headers=AUTH_HEADERS
    ).json()
    target = next(item for item in tasks if item["id"] == job_id)
    assert target["status"] == "failed"
    assert "超时" in (target["error"] or "")


def test_sweep_promotes_exhausted_failure_to_dead_letter(client: TestClient) -> None:
    job_id = _seed_exhausted_failed_job()
    sweep = client.post("/api/v1/ops/tasks/sweep", headers=AUTH_HEADERS)
    assert sweep.status_code == 200
    dead_ids = {item["id"] for item in sweep.json()["dead_lettered"]}
    assert job_id in dead_ids

    tasks = client.get(
        "/api/v1/ops/tasks", params={"kind": "generation_job"}, headers=AUTH_HEADERS
    ).json()
    target = next(item for item in tasks if item["id"] == job_id)
    assert target["status"] == "dead_letter"


def test_retry_reruns_failed_task_and_succeeds(client: TestClient) -> None:
    job_id = _seed_retryable_generation_job()
    response = client.post(
        f"/api/v1/ops/tasks/generation_job/{job_id}/retry", headers=AUTH_HEADERS
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    # eager 模式下重试同步执行完毕
    assert payload["status"] == "succeeded"
    assert payload["attempts"] == 2


def test_retry_rejects_dead_letter_task(client: TestClient) -> None:
    job_id = _seed_exhausted_failed_job()
    client.post("/api/v1/ops/tasks/sweep", headers=AUTH_HEADERS)
    response = client.post(
        f"/api/v1/ops/tasks/generation_job/{job_id}/retry", headers=AUTH_HEADERS
    )
    assert response.status_code == 409
    assert "死信" in response.json()["detail"]


def test_discard_dead_letter_task(client: TestClient) -> None:
    job_id = _seed_exhausted_failed_job()
    client.post("/api/v1/ops/tasks/sweep", headers=AUTH_HEADERS)
    discarded = client.post(
        f"/api/v1/ops/tasks/generation_job/{job_id}/discard", headers=AUTH_HEADERS
    )
    assert discarded.status_code == 200
    assert discarded.json()["status"] == "dismissed"

    repeat = client.post(
        f"/api/v1/ops/tasks/generation_job/{job_id}/discard", headers=AUTH_HEADERS
    )
    assert repeat.status_code == 409


def test_ops_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/ops/metrics").status_code == 401
    assert client.get("/api/v1/ops/tasks").status_code == 401
    assert client.post("/api/v1/ops/tasks/sweep").status_code == 401


def test_unknown_task_returns_404(client: TestClient) -> None:
    retry = client.post(
        "/api/v1/ops/tasks/generation_job/gen-missing/retry", headers=AUTH_HEADERS
    )
    assert retry.status_code == 404
    discard = client.post(
        "/api/v1/ops/tasks/generation_job/gen-missing/discard", headers=AUTH_HEADERS
    )
    assert discard.status_code == 404


def test_unknown_kind_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/ops/tasks", params={"kind": "mystery"}, headers=AUTH_HEADERS
    )
    assert response.status_code == 422
