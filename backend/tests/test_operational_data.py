"""针对"运营数据数据库化"后端的专项测试。

验证种子数据幂等、商品毛利率计算、店铺/告警/看板/自动化匹配均从数据库取数，
而非早期写死在 .py 里的元组。这些路径是 Step 1（去硬编码）的核心交付。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import (
    AlertModel,
    AutomationRuleModel,
    ProductModel,
    ShopModel,
)
from app.main import app
from app.services import automation_repository as ar
from app.services import dashboard_repository as dr
from app.services.seed import seed_if_empty


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_seed_is_idempotent(client: TestClient) -> None:
    from app.db.session import session_scope

    with session_scope() as db:
        seed_if_empty(db)
        second = seed_if_empty(db)
    # 无论首次是否已经存在（lifespan 会先写入），连续调用都必须幂等、不重复写入
    assert second is False
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(ProductModel)) == 18


def test_product_margins_are_derived_from_cost(client: TestClient) -> None:
    from app.db.session import session_scope

    with session_scope() as db:
        rows = db.scalars(select(ProductModel)).all()
        assert len(rows) == 18
        for product in rows:
            margin = (product.price - product.cost) / product.price
            assert 0.0 <= margin <= 1.0


def test_shops_and_alerts_are_seeded(client: TestClient) -> None:
    from app.db.session import session_scope

    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(ShopModel)) >= 4
        assert db.scalar(select(func.count()).select_from(AlertModel)) >= 1


def test_dashboard_overview_reads_from_database(client: TestClient) -> None:
    from app.db.session import session_scope

    with session_scope() as db:
        overview = dr.get_dashboard_overview(db, "shop-all")
    assert len(overview.metrics) == 4
    assert len(overview.trend) == 7


def test_automation_matches_scan_database_products(client: TestClient) -> None:
    from app.db.session import session_scope

    with session_scope() as db:
        ar._ensure_default_rules(db, "org-demo-001")
        inventory_rule = db.scalars(
            select(AutomationRuleModel).where(
                AutomationRuleModel.rule_type == "inventory_low"
            )
        ).first()
        quality_rule = db.scalars(
            select(AutomationRuleModel).where(
                AutomationRuleModel.rule_type == "product_quality"
            )
        ).first()
        assert inventory_rule is not None
        assert quality_rule is not None
        assert len(ar._matches(db, inventory_rule)) >= 1
        assert len(ar._matches(db, quality_rule)) >= 1
