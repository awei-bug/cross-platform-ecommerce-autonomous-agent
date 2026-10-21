"""智能体复盘模块测试：规划、执行、反思闭环、人工确认与只读边界。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import (
    AgentRunModel,
    AgentStepModel,
    DiagnosisModel,
    OperationJobModel,
)
from app.db.session import session_scope
from app.main import app
from app.schemas.agent import AgentStepKind
from app.services.agent_orchestrator import plan_goal
from app.services.competitor_repository import search_competitors
from app.services.diagnosis_engine import reflect


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


AUTH_HEADERS = {"Authorization": "Bearer demo-access-token"}

FULL_GOAL = "汇总 3 家店铺 7 天经营数据，对比竞品定价，诊断流量与转化问题，输出优化方案并自检复盘"


# ---------------------------------------------------------------- 规划


def test_plan_goal_parses_full_workflow() -> None:
    plan = plan_goal(FULL_GOAL)
    kinds = [step["kind"] for step in plan]
    assert kinds == [
        AgentStepKind.DATA_COLLECT.value,
        AgentStepKind.COMPETITOR_SCAN.value,
        AgentStepKind.DIAGNOSIS.value,
        AgentStepKind.RECOMMENDATION.value,
        AgentStepKind.SELF_CHECK.value,
    ]
    # 数据汇总与竞品扫描同波次并行
    assert plan[0]["wave"] == plan[1]["wave"] == 1
    assert plan[2]["wave"] == 2
    assert plan[4]["wave"] == 4


def test_plan_goal_diagnosis_only_still_runs_self_check() -> None:
    plan = plan_goal("诊断一下店铺流量问题")
    kinds = [step["kind"] for step in plan]
    assert AgentStepKind.DIAGNOSIS.value in kinds
    assert AgentStepKind.DATA_COLLECT.value in kinds  # 依赖传导
    assert AgentStepKind.SELF_CHECK.value in kinds  # 反思是硬约束
    assert AgentStepKind.COMPETITOR_SCAN.value not in kinds


def test_plan_goal_without_keywords_gets_default_workflow() -> None:
    plan = plan_goal("帮我把店铺经营情况过一遍")
    kinds = [step["kind"] for step in plan]
    assert AgentStepKind.DATA_COLLECT.value in kinds
    assert AgentStepKind.SELF_CHECK.value in kinds


# ---------------------------------------------------------------- 执行闭环


def test_create_and_execute_run_produces_evidence_backed_diagnoses(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agent/runs",
        json={"goal": FULL_GOAL},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["summary"]["steps_succeeded"] == payload["summary"]["steps_total"]
    assert payload["summary"]["diagnoses_total"] > 0

    # 所有结论必须携带指标证据（文档第三阶段硬约束）
    assert payload["diagnoses"]
    for diagnosis in payload["diagnoses"]:
        assert diagnosis["evidence"], f"{diagnosis['title']} 缺少证据"
        assert diagnosis["confidence"] in {"high", "medium", "low"}

    # 步骤档案齐全且含耗时
    kinds = {step["kind"] for step in payload["steps"]}
    assert AgentStepKind.SELF_CHECK.value in kinds
    assert all(step["duration_ms"] >= 0 for step in payload["steps"])


def test_run_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/agent/runs", json={"goal": FULL_GOAL})
    assert response.status_code == 401


def test_agent_run_creates_no_platform_write_jobs(client: TestClient) -> None:
    """只读边界：智能体运行不得产生任何平台写任务。"""
    with session_scope() as db:
        before = db.scalar(select(func.count()).select_from(OperationJobModel)) or 0
    client.post("/api/v1/agent/runs", json={"goal": FULL_GOAL}, headers=AUTH_HEADERS)
    with session_scope() as db:
        after = db.scalar(select(func.count()).select_from(OperationJobModel)) or 0
    assert after == before


def test_high_risk_diagnosis_requires_human_decision(client: TestClient) -> None:
    created = client.post(
        "/api/v1/agent/runs", json={"goal": FULL_GOAL}, headers=AUTH_HEADERS
    ).json()
    high_risk = [item for item in created["diagnoses"] if item["risk_level"] == "high"]
    # 种子数据含库存为零/下架类问题，必然产生高风险建议
    assert high_risk, "预期出现需要人工确认的高风险结论"
    pending = [item for item in high_risk if item["status"] == "pending"]
    assert pending

    target = pending[0]
    decision = client.post(
        f"/api/v1/agent/runs/{created['id']}/diagnoses/{target['id']}/decision",
        json={"decision": "approve", "note": "已人工核对库存数据"},
        headers=AUTH_HEADERS,
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"
    # decided_by 取自当前登录用户，与 /auth/me 一致
    me = client.get("/api/v1/auth/me", headers=AUTH_HEADERS).json()
    assert decision.json()["decided_by"] == me["name"]

    # 重复决策返回 409
    repeat = client.post(
        f"/api/v1/agent/runs/{created['id']}/diagnoses/{target['id']}/decision",
        json={"decision": "reject"},
        headers=AUTH_HEADERS,
    )
    assert repeat.status_code == 409

    # 驳回分支
    another = pending[1] if len(pending) > 1 else None
    if another is not None:
        rejected = client.post(
            f"/api/v1/agent/runs/{created['id']}/diagnoses/{another['id']}/decision",
            json={"decision": "reject", "note": "与本季定价策略冲突"},
            headers=AUTH_HEADERS,
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"


def test_decision_on_unknown_diagnosis_returns_404(client: TestClient) -> None:
    created = client.post(
        "/api/v1/agent/runs", json={"goal": FULL_GOAL}, headers=AUTH_HEADERS
    ).json()
    response = client.post(
        f"/api/v1/agent/runs/{created['id']}/diagnoses/diagnosis-missing/decision",
        json={"decision": "approve"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


def test_run_list_and_detail(client: TestClient) -> None:
    created = client.post(
        "/api/v1/agent/runs", json={"goal": FULL_GOAL}, headers=AUTH_HEADERS
    ).json()
    listing = client.get("/api/v1/agent/runs", headers=AUTH_HEADERS)
    assert listing.status_code == 200
    assert any(item["id"] == created["id"] for item in listing.json())

    detail = client.get(f"/api/v1/agent/runs/{created['id']}", headers=AUTH_HEADERS)
    assert detail.status_code == 200
    assert detail.json()["id"] == created["id"]

    missing = client.get("/api/v1/agent/runs/agent-run-missing", headers=AUTH_HEADERS)
    assert missing.status_code == 404


def test_single_shop_scope_limits_diagnoses(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agent/runs",
        json={"goal": FULL_GOAL, "shop_ids": ["shop-douyin-001"]},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["shop_ids"] == ["shop-douyin-001"]
    assert all(
        diagnosis["shop_id"] == "shop-douyin-001" for diagnosis in payload["diagnoses"]
    )


# ---------------------------------------------------------------- 竞品库


def test_competitor_search_ranks_by_similarity() -> None:
    with session_scope() as db:
        results = search_competitors(
            db,
            query_texts=["玻尿酸保湿面霜 补水"],
            category="美容护肤 / 面部护理",
            limit=3,
        )
    assert results
    similarities = [item["similarity"] for item in results]
    assert similarities == sorted(similarities, reverse=True)
    assert "玻尿酸" in results[0]["title"]


def test_competitor_create_and_list(client: TestClient) -> None:
    created = client.post(
        "/api/v1/agent/competitors",
        json={
            "title": "竞品 测试用益生菌面膜",
            "price": 79.0,
            "selling_points": ["益生菌发酵", "舒缓泛红"],
            "review_pain_points": ["精华液偏少"],
        },
        headers=AUTH_HEADERS,
    )
    assert created.status_code == 201
    competitor_id = created.json()["id"]

    listing = client.get(
        "/api/v1/agent/competitors", params={"q": "益生菌"}, headers=AUTH_HEADERS
    )
    assert listing.status_code == 200
    assert any(item["id"] == competitor_id for item in listing.json())


# ---------------------------------------------------------------- 反思引擎（单元级）


def test_reflect_discards_conclusion_without_evidence() -> None:
    drafts = [
        {
            "title": "无证据结论",
            "kind": "conversion",
            "evidence": [],
            "recommendation": "优化主图",
        }
    ]
    result = reflect(drafts, data_quality={}, competitor_coverage={})
    assert result["kept"] == []
    assert result["discarded"][0]["title"] == "无证据结论"


def test_reflect_downgrades_price_gap_when_coverage_insufficient() -> None:
    drafts = [
        {
            "title": "竞品低价挤压",
            "kind": "price_gap",
            "product_id": "product-10028",
            "evidence": [{"metric": "price", "value": 129.0, "threshold": "-", "source": "x"}],
            "recommendation": "评估跟价（改价需人工确认）",
        }
    ]
    result = reflect(
        drafts,
        data_quality={},
        competitor_coverage={"product-10028": 1},
    )
    assert result["kept"][0]["confidence"] == "low"
    assert result["supplement"]["competitor"] is True


def test_reflect_flags_data_gaps_for_supplement() -> None:
    result = reflect(
        [],
        data_quality={"issues": True, "missing_cost_skus": ["SKU-10028"]},
        competitor_coverage={},
    )
    assert result["supplement"]["data"] is True
    assert result["notes"]


# ---------------------------------------------------------------- 数据库约束


def test_run_persists_steps_and_diagnoses() -> None:
    with session_scope() as db:
        run = db.scalar(select(AgentRunModel).order_by(AgentRunModel.created_at.desc()).limit(1))
        assert run is not None
        steps = list(
            db.scalars(select(AgentStepModel).where(AgentStepModel.run_id == run.id)).all()
        )
        diagnoses = list(
            db.scalars(select(DiagnosisModel).where(DiagnosisModel.run_id == run.id)).all()
        )
        assert steps
        assert diagnoses
        assert all(step.status == "succeeded" for step in steps)
