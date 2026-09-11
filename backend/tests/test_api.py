from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer demo-access-token"}


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_workspace_requires_authentication() -> None:
    response = client.get("/api/v1/workspace/bootstrap")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_workspace_bootstrap() -> None:
    response = client.get("/api/v1/workspace/bootstrap", headers=AUTH_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["organization"]["name"] == "柔肤电商事业部"
    assert len(payload["shops"]) >= 4


def test_login_rejects_invalid_credentials() -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"account": "wrong", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_login_and_current_user() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"account": "demo", "password": "demo1234"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["access_token"] == "demo-access-token"

    me_response = client.get("/api/v1/auth/me", headers=AUTH_HEADERS)
    assert me_response.status_code == 200
    assert me_response.json()["role_name"] == "运营主管"


def test_cross_store_search() -> None:
    response = client.get(
        "/api/v1/search",
        params={"q": "SKU-10028"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()[0]["type"] == "sku"
