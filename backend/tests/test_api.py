import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


AUTH_HEADERS = {"Authorization": "Bearer demo-access-token"}


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_checks_database_and_task_mode(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "sqlite+pysqlite",
        "task_execution": "eager",
    }


def test_workspace_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/workspace/bootstrap")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_workspace_bootstrap(client: TestClient) -> None:
    response = client.get("/api/v1/workspace/bootstrap", headers=AUTH_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["organization"]["name"] == "柔肤电商事业部"
    assert len(payload["shops"]) >= 4


def test_login_rejects_invalid_credentials(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"account": "wrong", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_login_and_current_user(client: TestClient) -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"account": "demo", "password": "demo1234"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["access_token"] == "demo-access-token"

    me_response = client.get("/api/v1/auth/me", headers=AUTH_HEADERS)
    assert me_response.status_code == 200
    assert me_response.json()["role_name"] == "运营主管"


def test_cross_store_search(client: TestClient) -> None:
    response = client.get(
        "/api/v1/search",
        params={"q": "SKU-10028"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()[0]["type"] == "sku"


def test_products_support_server_filters_sorting_and_pagination(client: TestClient) -> None:
    response = client.get(
        "/api/v1/products",
        params={
            "shop_id": "shop-all",
            "risk": "critical",
            "sort_by": "stock",
            "page_size": 2,
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_demo"] is True
    assert payload["pagination"]["page_size"] == 2
    assert payload["summary"]["critical"] >= 2
    assert all(item["risk"] == "critical" for item in payload["items"])


def test_product_detail_contains_operational_context(client: TestClient) -> None:
    response = client.get("/api/v1/products/product-10028", headers=AUTH_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["sku"] == "SKU-10028"
    assert payload["competitors"]
    assert payload["ai_suggestions"]
    assert payload["is_demo"] is True


def test_batch_job_is_idempotent_and_reports_partial_result(client: TestClient) -> None:
    body = {
        "action": "sync",
        "product_ids": [
            "product-10028",
            "product-10031",
            "product-10042",
            "product-10056",
        ],
        "idempotency_key": "test-batch-idempotency-001",
    }
    created = client.post("/api/v1/products/batch-actions", json=body, headers=AUTH_HEADERS)
    repeated = client.post("/api/v1/products/batch-actions", json=body, headers=AUTH_HEADERS)
    assert created.status_code == 202
    assert repeated.json()["id"] == created.json()["id"]

    job_id = created.json()["id"]
    finished = client.get(f"/api/v1/products/jobs/{job_id}", headers=AUTH_HEADERS)
    assert finished.json()["status"] == "partial"
    assert finished.json()["progress"] == 100
    assert finished.json()["failed"] == 1


def test_dashboard_overview_changes_with_shop_context(client: TestClient) -> None:
    all_shops = client.get("/api/v1/dashboard/overview?shop_id=shop-all", headers=AUTH_HEADERS)
    taobao = client.get("/api/v1/dashboard/overview?shop_id=shop-taobao-001", headers=AUTH_HEADERS)
    assert all_shops.status_code == 200
    assert len(all_shops.json()["metrics"]) == 4
    assert len(all_shops.json()["trend"]) == 7
    assert taobao.json()["ai_brief"]["context_label"].startswith("柔肤旗舰店")
    assert all_shops.json()["metrics"][0]["value"] > taobao.json()["metrics"][0]["value"]


def test_multi_shop_scope_filters_dashboard_products_and_orders(client: TestClient) -> None:
    scope = "shop-taobao-001,shop-douyin-001"

    dashboard = client.get(
        "/api/v1/dashboard/overview",
        params={"shop_id": scope},
        headers=AUTH_HEADERS,
    )
    products = client.get(
        "/api/v1/products",
        params={"shop_id": scope, "page_size": 100},
        headers=AUTH_HEADERS,
    )
    orders = client.get(
        "/api/v1/orders",
        params={"shop_id": scope, "page_size": 100},
        headers=AUTH_HEADERS,
    )

    assert dashboard.status_code == 200
    assert dashboard.json()["ai_brief"]["context_label"].startswith("2 个店铺")
    assert products.status_code == 200
    assert products.json()["pagination"]["total"] == 12
    assert {item["shop_id"] for item in products.json()["items"]} == {
        "shop-taobao-001",
        "shop-douyin-001",
    }
    assert orders.status_code == 200
    assert orders.json()["pagination"]["total"] == 8
    assert {item["shop_id"] for item in orders.json()["items"]} == {
        "shop-taobao-001",
        "shop-douyin-001",
    }


def test_shop_all_scope_remains_compatible(client: TestClient) -> None:
    response = client.get(
        "/api/v1/products",
        params={"shop_id": "shop-all", "page_size": 100},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 18
    assert len({item["shop_id"] for item in payload["items"]}) >= 3


def test_campaign_overview_supports_shop_and_platform_scope(client: TestClient) -> None:
    response = client.get(
        "/api/v1/campaigns",
        params={"shop_id": "shop-taobao-001,shop-douyin-001"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_demo"] is True
    assert len(payload["campaigns"]) == 4
    assert payload["summary"]["anomaly_campaigns"] == 2
    assert payload["budget_alerts"]
    assert {item["platform"] for item in payload["campaigns"]} == {"taobao", "douyin"}

    platform_response = client.get(
        "/api/v1/campaigns",
        params={"shop_id": "shop-all", "platform": "pinduoduo", "status": "review"},
        headers=AUTH_HEADERS,
    )
    assert platform_response.status_code == 200
    assert len(platform_response.json()["campaigns"]) == 1
    assert platform_response.json()["campaigns"][0]["name"] == "大促蓄水人群"


def test_connector_status_does_not_fake_real_authorization(client: TestClient) -> None:
    response = client.get("/api/v1/integrations/connectors", headers=AUTH_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert {item["platform"] for item in payload} == {"douyin"}
    assert all(item["state"] != "ready" for item in payload)
    assert any(item["missing_secrets"] for item in payload)


def test_orders_support_sla_risk_filters_and_mask_sensitive_data(client: TestClient) -> None:
    response = client.get(
        "/api/v1/orders",
        params={"shop_id": "shop-all", "risk": "critical", "sort_by": "sla_deadline"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_demo"] is True
    assert payload["summary"]["critical"] == 3
    assert payload["summary"]["overdue"] == 1
    assert all(item["sensitive_data_masked"] for item in payload["items"])
    assert all(item["risk"] == "critical" for item in payload["items"])


def test_order_detail_contains_sla_conversation_and_ai_context(client: TestClient) -> None:
    response = client.get(
        "/api/v1/orders/order-dd20260911001",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["buyer_phone_masked"].startswith("138****")
    assert "*" in payload["shipping_address_masked"]
    assert payload["conversation"]
    assert payload["ai_replies"]
    assert "approve_refund" in payload["available_actions"]
    assert payload["is_demo"] is True


def test_order_action_is_idempotent_partial_and_audited(client: TestClient) -> None:
    body = {
        "action": "mark_follow_up",
        "order_ids": [
            "order-dd20260911001",
            "order-tb20260912018",
            "order-pd20260912007",
        ],
        "idempotency_key": "test-order-action-idempotency-001",
    }
    created = client.post("/api/v1/orders/actions", json=body, headers=AUTH_HEADERS)
    repeated = client.post("/api/v1/orders/actions", json=body, headers=AUTH_HEADERS)
    assert created.status_code == 202
    assert repeated.json()["id"] == created.json()["id"]

    job_id = created.json()["id"]
    finished = client.get(f"/api/v1/orders/jobs/{job_id}", headers=AUTH_HEADERS)
    assert finished.json()["status"] == "partial"
    assert finished.json()["failed"] == 1

    audit = client.get("/api/v1/orders/audit", headers=AUTH_HEADERS)
    assert audit.status_code == 200
    assert len(audit.json()) >= 3
    assert any(entry["result"] == "failed" for entry in audit.json())


def test_alert_read_state_is_persisted(client: TestClient) -> None:
    updated = client.patch(
        "/api/v1/workspace/alerts/alert-001",
        json={"is_read": True},
        headers=AUTH_HEADERS,
    )
    assert updated.status_code == 200
    assert updated.json()["is_read"] is True

    alerts = client.get("/api/v1/workspace/alerts", headers=AUTH_HEADERS)
    assert next(item for item in alerts.json() if item["id"] == "alert-001")["is_read"] is True

    restored = client.patch(
        "/api/v1/workspace/alerts/alert-001",
        json={"is_read": False},
        headers=AUTH_HEADERS,
    )
    assert restored.json()["is_read"] is False


def test_reviews_overview_supports_shop_rating_and_ticket_filters(client: TestClient) -> None:
    response = client.get(
        "/api/v1/reviews",
        params={"shop_id": "shop-taobao-001,shop-douyin-001", "rating": "negative"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_demo"] is True
    assert payload["summary"]["negative"] == 1
    assert {item["platform"] for item in payload["reviews"]} == {"douyin"}
    assert payload["tickets"]

    filtered = client.get(
        "/api/v1/reviews",
        params={"shop_id": "shop-all", "ticket_status": "resolved"},
        headers=AUTH_HEADERS,
    )
    assert filtered.status_code == 200
    assert len(filtered.json()["reviews"]) == 1
    assert filtered.json()["reviews"][0]["ticket_status"] == "resolved"


def test_review_ticket_update_is_persisted(client: TestClient) -> None:
    response = client.post(
        "/api/v1/reviews/tickets",
        json={
            "review_id": "review-003",
            "assignee": "林小满",
            "status": "in_progress",
            "reply_draft": "感谢反馈，我们会持续改进。",
            "follow_up_note": "已加入客服回访队列",
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"

    overview = client.get("/api/v1/reviews", headers=AUTH_HEADERS)
    review = next(item for item in overview.json()["reviews"] if item["id"] == "review-003")
    assert review["ticket_status"] == "in_progress"
    assert (
        next(item for item in overview.json()["tickets"] if item["review_id"] == "review-003")[
            "assignee"
        ]
        == "林小满"
    )


def test_reports_overview_supports_templates_and_scope(client: TestClient) -> None:
    response = client.get(
        "/api/v1/reports",
        params={"shop_id": "shop-taobao-001", "template_id": "ad", "metrics": "spend,roi"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_demo"] is True
    assert payload["selected_template"] == "ad"
    assert [item["key"] for item in payload["metrics"]] == ["spend", "roi"]
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["platform_label"] == "淘宝"


def test_report_export_and_note_are_recorded(client: TestClient) -> None:
    export = client.post(
        "/api/v1/reports/exports",
        json={
            "template_id": "monthly",
            "format": "pdf",
            "shop_id": "shop-all",
            "metrics": ["revenue"],
        },
        headers=AUTH_HEADERS,
    )
    assert export.status_code == 200
    assert export.json()["status"] == "succeeded"
    assert export.json()["file_name"].endswith(".pdf")

    note = client.post(
        "/api/v1/reports/notes",
        json={
            "template_id": "monthly",
            "title": "月度复盘",
            "conclusion": "成交增长",
            "next_actions": "继续优化投放",
        },
        headers=AUTH_HEADERS,
    )
    assert note.status_code == 200
    assert note.json()["template_id"] == "monthly"
    overview = client.get("/api/v1/reports?template_id=monthly", headers=AUTH_HEADERS)
    assert any(item["title"] == "月度复盘" for item in overview.json()["notes"])


def test_automation_rules_scan_demo_risks_and_keep_auto_mode_disabled(client: TestClient) -> None:
    overview = client.get("/api/v1/automation", headers=AUTH_HEADERS)
    assert overview.status_code == 200
    rules = overview.json()["rules"]
    assert {rule["rule_type"] for rule in rules} == {
        "after_sale_sla",
        "inventory_low",
        "product_quality",
    }

    inventory_rule = next(rule for rule in rules if rule["rule_type"] == "inventory_low")
    missing_confirmation = client.post(
        f"/api/v1/automation/rules/{inventory_rule['id']}/runs",
        json={},
        headers=AUTH_HEADERS,
    )
    assert missing_confirmation.status_code == 409

    run = client.post(
        f"/api/v1/automation/rules/{inventory_rule['id']}/runs",
        json={"confirm": True},
        headers=AUTH_HEADERS,
    )
    assert run.status_code == 201
    assert run.json()["matched_count"] >= 1
    assert run.json()["task_count"] == run.json()["matched_count"]
    first_task_ids = {item["task_id"] for item in run.json()["results"]}
    assert None not in first_task_ids

    repeated_run = client.post(
        f"/api/v1/automation/rules/{inventory_rule['id']}/runs",
        json={"confirm": True},
        headers=AUTH_HEADERS,
    )
    assert repeated_run.status_code == 201
    assert {item["task_id"] for item in repeated_run.json()["results"]} == first_task_ids

    task_id = next(iter(first_task_ids))
    updated_task = client.patch(
        f"/api/v1/automation/tasks/{task_id}",
        json={"status": "in_progress", "assignee": "徐店长"},
        headers=AUTH_HEADERS,
    )
    assert updated_task.status_code == 200
    assert updated_task.json()["status"] == "in_progress"
    assert updated_task.json()["assignee"] == "徐店长"

    auto_mode = client.patch(
        f"/api/v1/automation/rules/{inventory_rule['id']}",
        json={"mode": "auto"},
        headers=AUTH_HEADERS,
    )
    assert auto_mode.status_code == 409

    history = client.get("/api/v1/automation", headers=AUTH_HEADERS)
    assert history.json()["runs"][0]["rule_id"] == inventory_rule["id"]
    assert any(task["id"] == task_id for task in history.json()["tasks"])


def test_binary_asset_upload_and_authenticated_preview(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets/uploads?title=测试主图",
        headers={**AUTH_HEADERS, "Content-Type": "image/png", "X-Filename": "cover.png"},
        content=b"fake-png-content",
    )
    assert uploaded.status_code == 201
    asset = uploaded.json()
    version = asset["versions"][0]
    assert asset["asset_type"] == "image"
    assert asset["is_demo"] is False
    assert version["source"] == "upload"
    assert version["content_type"] == "image/png"
    assert version["file_size"] == len(b"fake-png-content")

    preview = client.get(version["preview_url"], headers=AUTH_HEADERS)
    assert preview.status_code == 200
    assert preview.content == b"fake-png-content"
    assert preview.headers["content-type"].startswith("image/png")

    unauthorized = client.get(version["preview_url"])
    assert unauthorized.status_code == 401
