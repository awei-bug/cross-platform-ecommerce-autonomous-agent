from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import session_scope
from app.main import app
from app.schemas.ecomops import Policy
from app.schemas.research import ResearchAnalysis, ResearchBatch
from app.services.browser_research import analyze_research, import_research, list_collections
from app.services.ecomops_specialists import Hold, execute_tool

HEADERS = {"Authorization": "Bearer demo-access-token"}
ROOT = "/api/v1/ecomops/research"


def batch():
    return {
        "collection_id": "research-" + uuid4().hex,
        "country": "US",
        "category": "test",
        "observations": [
            {
                "source_url": "https://example.com/item",
                "title": "Storage box",
                "price": 20,
                "currency": "USD",
                "collected_at": datetime.now(UTC).isoformat(),
                "specifications": {"size": "1 piece"},
                "price_evidence": "visible $20.00",
                "evidence_file": "product.png",
                "evidence_sha256": "a" * 64,
                "ranking": {
                    "source_url": "https://example.com/bestsellers",
                    "category": "Home",
                    "rank": 4,
                    "collected_at": datetime.now(UTC).isoformat(),
                    "evidence_file": "ranking.png",
                    "evidence_sha256": "b" * 64,
                },
            }
        ],
    }


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_import_roundtrip_deduplicates_and_retains_provenance(client):
    data = batch()
    assert client.post(f"{ROOT}/import", json=data).status_code == 401
    first = client.post(f"{ROOT}/import", headers=HEADERS, json=data)
    assert first.status_code == 200, first.text
    assert first.json()["inserted"] == 1
    assert client.post(f"{ROOT}/import", headers=HEADERS, json=data).json()["updated"] == 1
    report = client.post(
        f"{ROOT}/analyze", headers=HEADERS, json={"collection_id": data["collection_id"]}
    ).json()
    assert report["sample_count"] == report["ranked_sample_count"] == 1
    candidate = report["candidates"][0]
    assert candidate["max_fixed_cost_at_target_margin"] == 12
    assert candidate["source_url"] == data["observations"][0]["source_url"]
    assert candidate["evidence_sha256"] == "a" * 64
    assert candidate["sales"] is None
    assert candidate["ranking"]["rank"] == 4
    assert client.get(f"{ROOT}/collections", headers=HEADERS).status_code == 200


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_url", "http://127.0.0.1/private"),
        ("source_url", "https://u:p@example.com"),
        ("price", -1),
        ("price", "20"),
        ("price", True),
        ("currency", None),
        ("collected_at", "2026-10-15T12:00:00"),
        ("evidence_sha256", "bad"),
        ("price_evidence", ""),
    ],
)
def test_rejects_invalid_evidence_atomically(client, field, value):
    data = batch()
    data["observations"].append({**data["observations"][0], field: value})
    response = client.post(f"{ROOT}/import", headers=HEADERS, json=data)
    assert response.status_code == 422, response.text
    report = client.post(
        f"{ROOT}/analyze", headers=HEADERS, json={"collection_id": data["collection_id"]}
    ).json()
    assert report["sample_count"] == 0


def test_collection_country_currency_and_tenant_isolation(client):
    data = batch()
    with session_scope() as db:
        import_research(db, "research-org-a", "test", ResearchBatch(**data))
        same = ResearchAnalysis(collection_id=data["collection_id"])
        assert analyze_research(db, "research-org-a", same)["sample_count"] == 1
        assert analyze_research(db, "research-org-b", same)["sample_count"] == 0
        assert list_collections(db, "research-org-b") == []
        assert (
            analyze_research(db, "research-org-a", same.model_copy(update={"country": "DE"}))[
                "sample_count"
            ]
            == 0
        )
        other_currency = analyze_research(
            db, "research-org-a", same.model_copy(update={"currency": "EUR"})
        )
        assert other_currency["sample_count"] == 0 and len(other_currency["excluded"]) == 1
        no_margin = analyze_research(
            db, "research-org-a", same.model_copy(update={"commission_pct": 80})
        )
        assert no_margin["candidates"][0]["max_fixed_cost_at_target_margin"] is None


def test_selection_uses_only_explicit_collection_and_does_not_invent_market_score(client):
    data = batch()
    with session_scope() as db:
        import_research(db, "research-workflow", "test", ResearchBatch(**data))
        run = SimpleNamespace(
            organization_id="research-workflow",
            input={"research_collection_id": data["collection_id"], "country": "US"},
        )
        result = execute_tool(db, run, SimpleNamespace(key="market"), Policy())
        assert result["sample_count"] == 1 and result["market_score"] is None
        run.input["research_collection_id"] = "missing-collection"
        with pytest.raises(Hold) as hold:
            execute_tool(db, run, SimpleNamespace(key="market"), Policy())
        assert hold.value.status == "waiting_data"
