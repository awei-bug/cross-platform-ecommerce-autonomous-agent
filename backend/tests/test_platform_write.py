"""真实写操作安全层测试。

覆盖：演示态批量任务的 partial 行为与失败项重试恢复。抖店 live 链路的真实写入测试在
test_douyin_live.py 中单独覆盖（沙箱店铺 4463798 的改价/上下架）。
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import AuditLogModel, OperationJobModel
from app.main import app
from app.schemas.products import BatchAction, JobStatus
from app.services import product_repository as pr

SHANGHAI = ZoneInfo("Asia/Shanghai")


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_demo_job_reports_partial_and_retry_recovers(client: TestClient) -> None:
    from app.db.session import session_scope

    with session_scope() as db:
        db.add(
            OperationJobModel(
                id="job-demo-retry",
                kind="product",
                action=BatchAction.SYNC.value,
                idempotency_key="demo-retry-key",
                status=JobStatus.QUEUED.value,
                progress=0,
                total=4,
                succeeded=0,
                failed=0,
                entity_ids=["product-10028", "product-10031", "product-10042", "product-10056"],
                payload={},
                results=[],
                created_at=datetime.now(SHANGHAI),
                updated_at=datetime.now(SHANGHAI),
                is_demo=True,
            )
        )
        db.commit()

    with session_scope() as db:
        pr.execute_batch_job(db, "job-demo-retry")
        failed_audit = db.scalars(
            select(AuditLogModel).where(AuditLogModel.job_id == "job-demo-retry")
        ).all()
        assert any(not entry.is_demo for entry in failed_audit) is False  # 演示态审计 is_demo=True

    with session_scope() as db:
        job = db.get(OperationJobModel, "job-demo-retry")
        assert job.status == JobStatus.PARTIAL.value
        assert job.failed == 1

    with session_scope() as db:
        pr.retry_batch_job(db, "job-demo-retry")

    with session_scope() as db:
        job = db.get(OperationJobModel, "job-demo-retry")
        assert job.failed == 0
        assert job.status == JobStatus.SUCCEEDED.value
