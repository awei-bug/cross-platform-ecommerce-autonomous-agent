"""报表导出真实文件测试：Excel/PDF 生成、落库、下载与鉴权。"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


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


def _create_export(client: TestClient, export_format: str) -> dict:
    response = client.post(
        "/api/v1/reports/exports",
        json={
            "template_id": "weekly",
            "format": export_format,
            "shop_id": "shop-all",
            "metrics": ["revenue", "orders"],
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_export_excel_generates_real_workbook(client: TestClient) -> None:
    job = _create_export(client, "excel")
    assert job["status"] == "succeeded"
    assert job["file_name"].endswith(".xlsx")
    assert job["file_size"] > 1000

    download = client.get(
        f"/api/v1/reports/exports/{job['id']}/download", headers=AUTH_HEADERS
    )
    assert download.status_code == 200
    assert download.content[:2] == b"PK"

    import io

    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(download.content))
    assert workbook.sheetnames == ["指标概览", "7日趋势", "主体明细", "口径与边界"]
    metrics_sheet = workbook["指标概览"]
    assert metrics_sheet["A1"].value.startswith("运营周报")
    rows_sheet = workbook["主体明细"]
    assert rows_sheet.max_row >= 2  # 表头 + 至少一条明细


def test_export_pdf_generates_real_document(client: TestClient) -> None:
    job = _create_export(client, "pdf")
    assert job["status"] == "succeeded"
    assert job["file_name"].endswith(".pdf")

    download = client.get(
        f"/api/v1/reports/exports/{job['id']}/download", headers=AUTH_HEADERS
    )
    assert download.status_code == 200
    assert download.content[:4] == b"%PDF"
    assert b"STSong-Light" in download.content  # 中文字体已嵌入


def test_exports_are_recorded_in_overview(client: TestClient) -> None:
    job = _create_export(client, "excel")
    overview = client.get("/api/v1/reports", headers=AUTH_HEADERS).json()
    assert any(item["id"] == job["id"] for item in overview["exports"])


def test_export_requires_authentication(client: TestClient) -> None:
    create = client.post(
        "/api/v1/reports/exports",
        json={"template_id": "weekly", "format": "pdf", "shop_id": "shop-all"},
    )
    assert create.status_code == 401
    download = client.get("/api/v1/reports/exports/report-export-x/download")
    assert download.status_code == 401


def test_export_download_unknown_returns_404(client: TestClient) -> None:
    response = client.get(
        "/api/v1/reports/exports/report-export-missing/download", headers=AUTH_HEADERS
    )
    assert response.status_code == 404


def test_export_respects_shop_scope(client: TestClient) -> None:
    response = client.post(
        "/api/v1/reports/exports",
        json={
            "template_id": "ad",
            "format": "excel",
            "shop_id": "shop-taobao-001",
            "metrics": ["spend", "roi"],
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    job = response.json()
    assert "柔肤旗舰店" in job["file_name"]
