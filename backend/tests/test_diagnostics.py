"""数据诊断测试：健康分可解释性、问题清单排序与口径下发。"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.diagnostics_service import (
    HEALTH_ALGORITHM_VERSION,
    build_issues,
    compute_health,
)


@pytest.fixture(scope="module")
def client(tmp_path_factory) -> TestClient:
    # 隔离素材存储目录：导出/上传文件只落临时目录，不污染 data/assets
    settings = get_settings()
    original_path = settings.asset_storage_local_path
    settings.asset_storage_local_path = str(tmp_path_factory.mktemp("assets"))
    with TestClient(app) as test_client:
        yield test_client
    settings.asset_storage_local_path = original_path


AUTH_HEADERS = {"Authorization": "Bearer demo-access-token"}


def test_overview_returns_explainable_health_score(client: TestClient) -> None:
    response = client.get(
        "/api/v1/diagnostics/overview",
        params={"shop_id": "shop-all"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()
    health = payload["health"]
    assert health["algorithm_version"] == HEALTH_ALGORITHM_VERSION
    assert 0 <= health["score"] <= 100
    assert len(health["components"]) == 5
    total_weight = sum(item["weight"] for item in health["components"])
    assert abs(total_weight - 1.0) < 1e-6
    for component in health["components"]:
        assert 0 <= component["score"] <= 100
        assert component["detail"], "每个分项必须带可解释说明"


def test_issues_are_sorted_by_priority_and_evidence_backed(client: TestClient) -> None:
    payload = client.get(
        "/api/v1/diagnostics/overview", headers=AUTH_HEADERS
    ).json()
    issues = payload["issues"]
    assert issues, "演示数据应产生诊断问题"
    priorities = [item["priority"] for item in issues]
    assert priorities == sorted(priorities, reverse=True)
    for issue in issues:
        assert issue["evidence"], f"{issue['title']} 缺少证据"
        assert issue["estimated_loss"] >= 0
        assert issue["loss_note"], "估算金额必须带口径说明"
        assert 0 <= issue["urgency"] <= 100


def test_metric_definitions_are_served(client: TestClient) -> None:
    payload = client.get(
        "/api/v1/diagnostics/overview", headers=AUTH_HEADERS
    ).json()
    keys = {item["key"] for item in payload["metric_definitions"]}
    assert {"health_score", "estimated_loss", "urgency"} <= keys


def test_shop_scope_filters_issues(client: TestClient) -> None:
    payload = client.get(
        "/api/v1/diagnostics/overview",
        params={"shop_id": "shop-douyin-001"},
        headers=AUTH_HEADERS,
    ).json()
    assert payload["shop_id"] == "shop-douyin-001"
    for issue in payload["issues"]:
        assert issue["shop_id"] == "shop-douyin-001"


def test_comparison_ranks_shops_by_health(client: TestClient) -> None:
    payload = client.get(
        "/api/v1/diagnostics/overview", headers=AUTH_HEADERS
    ).json()
    rows = payload["comparison"]
    assert len(rows) >= 2
    scores = [row["health_score"] for row in rows]
    assert scores == sorted(scores, reverse=True)
    for row in rows:
        assert row["shop_id"] != "shop-all"
        assert row["product_count"] > 0


def test_health_components_are_stable_for_same_input() -> None:
    from sqlalchemy import select

    from app.db.models import ProductModel
    from app.db.session import session_scope

    with session_scope() as db:
        products = list(db.scalars(select(ProductModel)).all())
    empty_map = {product.id: [] for product in products}
    first = compute_health(products, empty_map, None)
    second = compute_health(products, empty_map, None)
    assert first == second


def test_priority_reflects_confidence_downgrade() -> None:
    from sqlalchemy import select

    from app.db.models import ProductModel
    from app.db.session import session_scope

    with session_scope() as db:
        products = list(db.scalars(select(ProductModel)).all())
    competitor_map = {product.id: [] for product in products}
    issues = build_issues(products, competitor_map, None)
    # 无竞品覆盖时价格对标类问题不应出现（无证据不进清单）
    assert all(issue["kind"] != "price_gap" for issue in issues)


# ---------------------------------------------------------------- 诊断报告


def test_generate_template_report_when_ai_disabled(client: TestClient) -> None:
    response = client.post(
        "/api/v1/diagnostics/reports",
        params={"shop_id": "shop-all"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 201
    payload = response.json()
    # 默认 AI_LIVE_GENERATION_ENABLED=false，必须走模板且如实标注
    assert payload["source"] == "template"
    assert "规则模板生成" in payload["content"]
    assert "口径与边界声明" in payload["content"]
    assert payload["snapshot"]["health"]["score"] >= 0
    assert payload["snapshot"]["issues"]


def test_report_list_and_detail(client: TestClient) -> None:
    created = client.post(
        "/api/v1/diagnostics/reports", headers=AUTH_HEADERS
    ).json()
    listing = client.get("/api/v1/diagnostics/reports", headers=AUTH_HEADERS)
    assert listing.status_code == 200
    assert any(item["id"] == created["id"] for item in listing.json())

    detail = client.get(
        f"/api/v1/diagnostics/reports/{created['id']}", headers=AUTH_HEADERS
    )
    assert detail.status_code == 200
    assert detail.json()["content"] == created["content"]

    missing = client.get(
        "/api/v1/diagnostics/reports/diag-report-missing", headers=AUTH_HEADERS
    )
    assert missing.status_code == 404


def test_report_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/diagnostics/reports")
    assert response.status_code == 401


# ---------------------------------------------------------------- 导出


def test_export_pdf_and_xlsx_with_login(client: TestClient) -> None:
    report = client.post("/api/v1/diagnostics/reports", headers=AUTH_HEADERS).json()
    pdf = client.post(
        f"/api/v1/diagnostics/reports/{report['id']}/exports",
        params={"format": "pdf"},
        headers=AUTH_HEADERS,
    )
    assert pdf.status_code == 201
    assert pdf.json()["format"] == "pdf"
    assert pdf.json()["file_size"] > 1000
    assert pdf.json()["status"] == "succeeded"

    downloaded = client.get(
        f"/api/v1/diagnostics/exports/{pdf.json()['id']}/download", headers=AUTH_HEADERS
    )
    assert downloaded.status_code == 200
    assert downloaded.content[:4] == b"%PDF"

    xlsx = client.post(
        f"/api/v1/diagnostics/reports/{report['id']}/exports",
        params={"format": "xlsx"},
        headers=AUTH_HEADERS,
    )
    assert xlsx.status_code == 201
    assert xlsx.json()["file_name"].endswith(".xlsx")
    xlsx_download = client.get(
        f"/api/v1/diagnostics/exports/{xlsx.json()['id']}/download", headers=AUTH_HEADERS
    )
    assert xlsx_download.status_code == 200
    assert xlsx_download.content[:2] == b"PK"  # xlsx 是 zip 魔数


def test_export_rejects_unknown_format(client: TestClient) -> None:
    report = client.post("/api/v1/diagnostics/reports", headers=AUTH_HEADERS).json()
    response = client.post(
        f"/api/v1/diagnostics/reports/{report['id']}/exports",
        params={"format": "docx"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 400


def test_export_requires_authentication(client: TestClient) -> None:
    report = client.post("/api/v1/diagnostics/reports", headers=AUTH_HEADERS).json()
    create = client.post(
        f"/api/v1/diagnostics/reports/{report['id']}/exports",
        params={"format": "pdf"},
    )
    assert create.status_code == 401
    download = client.get("/api/v1/diagnostics/exports/diag-export-x/download")
    assert download.status_code == 401


def test_export_unknown_report_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/diagnostics/reports/diag-report-missing/exports",
        params={"format": "pdf"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404
