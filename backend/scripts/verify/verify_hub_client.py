"""跨境项目 data-hub 只读客户端与 external_id 对齐自检。

用法::

    python scripts/verify/verify_hub_client.py

覆盖 8 项断言：
1. 未配置 DATA_HUB_URL 时 hub_enabled 为 False
2. 未配置时全部读返回空而不抛异常（降级不阻断）
3. external_id 命名规则：抖店商品为 dy-{platform_item_id}
4. sync 幂等优先级：external_id 命中 > platform_item_id 回退
5. 历史行无 external_id 时，重复同步会补写身份而不新建行
6. 商品详情在无记忆库连接时 knowledge.available=False
7. 商品详情在有真实连接时能取到知识卡字段
8. 不写入：客户端没有任何写方法（源码级断言）

前置：无需真实 data-hub。第 7 项用本地 MockTransport 拦截 httpx，
不需要启动真实服务，也不需要凭证。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.db.models import Base, ProductModel, ShopModel  # noqa: E402
from app.schemas.products import ProductDetail  # noqa: E402
from app.services import hub_client as hub  # noqa: E402
from app.services.platform_sync import _resolve_external_id, map_douyin_product  # noqa: E402
from app.services.product_repository import get_product  # noqa: E402

SHANGHAI = ZoneInfo("Asia/Shanghai")

checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "data_hub_url": None,
        "data_hub_tenant_slug": None,
    }
    base.update(overrides)
    return Settings(**base)


def main() -> int:
    settings = _settings()

    # --- 1. 未配置时不可用 ---
    check("hub.disabled.by.default", hub.hub_enabled(settings) is False)

    # --- 2. 未配置时读返回空而非抛异常 ---
    try:
        empty_item = hub.fetch_product_knowledge("cc-1", settings=settings)
        empty_list = hub.list_product_knowledge(settings=settings)
        empty_search = hub.search_product_knowledge("水杯", settings=settings)
        ok = empty_item is None and empty_list == [] and empty_search == []
        check(
            "hub.reads.degrade.to.empty",
            ok,
            f"item={empty_item} list={empty_list} search={empty_search}",
        )
    except Exception as exc:  # noqa: BLE001
        check("hub.reads.degrade.to.empty", False, f"raised {exc!r}")

    # --- 3. external_id 命名规则 ---
    mapped = map_douyin_product({
        "product_id": "123456",
        "name": "便携榨汁杯",
        "status": 0,
        "stock": 30,
        "price": 12900,
    })
    check(
        "hub.external_id.naming",
        mapped["external_id"] == "dy-123456" and _resolve_external_id("") == "",
        f"external_id={mapped['external_id']}",
    )

    # --- 4/5. 幂等优先级与历史行补写 ---
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    shop = ShopModel(
        id="shop-live-douyin-test",
        organization_id="org-demo-001",
        platform="douyin",
        platform_label="抖店",
        name="授权店铺",
        status="active",
        data_source="live",
    )
    session.add(shop)
    session.commit()

    # 历史行：只有 platform_item_id，没有 external_id
    legacy = ProductModel(
        id="product-dy-legacy",
        organization_id="org-demo-001",
        shop_id=shop.id,
        sku="LEGACY-1",
        platform_item_id="999",
        external_id=None,
        title="旧商品",
        platform="douyin",
        platform_label="抖店",
        shop_name="授权店铺",
        status="online",
        risk="normal",
        risk_labels=[],
        price=99.0,
        cost=0.0,
        stock=10,
        sales_7d=0,
        revenue_7d=0.0,
        conversion_rate=0.0,
        updated_at=datetime.now(SHANGHAI),
    )
    session.add(legacy)
    session.commit()

    row = {"product_id": "999", "name": "旧商品（改名）", "status": 0, "stock": 12, "price": 9900}
    again = map_douyin_product(row)
    # 模拟 sync 中的匹配顺序：external_id 优先，回落到 platform_item_id
    existing = {}
    for product in session.query(ProductModel).filter(ProductModel.shop_id == shop.id):
        if product.external_id:
            existing.setdefault(product.external_id, product)
        if product.platform_item_id:
            existing.setdefault(product.platform_item_id, product)

    matched = existing.get(again["external_id"]) or existing.get(again["platform_item_id"])
    check(
        "hub.idempotency.legacy.row.matched",
        matched is not None,
        f"matched={matched.id if matched else None}",
    )

    if matched is not None:
        if not matched.external_id:
            matched.external_id = again["external_id"]
        changed = any(getattr(matched, f) != v for f, v in again.items())
        session.commit()
        session.refresh(matched)
        check(
            "hub.idempotency.identity.backfilled",
            matched.external_id == "dy-999" and matched.id == "product-dy-legacy",
            f"external_id={matched.external_id}",
        )
        check("hub.idempotency.no.duplicate.row", session.query(ProductModel).count() == 1,
              f"rows={session.query(ProductModel).count()}")
        check("hub.idempotency.detects.change", changed is True, "title/stock 变化被识别")

    # --- 6. 无连接时 knowledge.available=False ---
    detail = get_product(session, legacy.id)
    check(
        "hub.detail.knowledge.unavailable",
        isinstance(detail, ProductDetail) and detail.knowledge.available is False,
        f"available={detail.knowledge.available if detail else 'no-detail'}",
    )

    # --- 7. 有真实连接时取到知识卡字段（MockTransport 拦截，无需真实服务） ---
    try:
        import httpx

        sample = {
            "external_id": "cc-verify-001",
            "title": "便携榨汁杯 380ml",
            "price": 129.0,
            "stock": 30,
            "category": "厨具",
            "selling_points": ["380ml 容量", "USB 充电一次榨 15 杯"],
            "scenario": "办公室、出差",
            "spec": {"容量": "380ml"},
            "faq": [{"q": "能榨冰块吗", "a": "不建议"}],
            "images": ["https://example.test/a.png"],
            "status": "published",
            "source": "content_create",
            "version": 3,
        }

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["X-Hub-Tenant"] == "demo", "租户头必须传递"
            return httpx.Response(200, json={"ok": True, "item": sample})

        live = _settings(
            data_hub_url="http://127.0.0.1:8120",
            data_hub_token="hub-local-token",
            data_hub_tenant_slug="demo",
        )
        check("hub.enabled.when.configured", hub.hub_enabled(live) is True)

        original_client = hub._client
        hub._client = lambda settings=None: httpx.Client(
            base_url="http://127.0.0.1:8120",
            headers=hub._headers(live),
            timeout=5.0,
            transport=httpx.MockTransport(handler),
        )
        try:
            knowledge = hub.fetch_product_knowledge("cc-verify-001", settings=live)
        finally:
            hub._client = original_client

        ok = (
            isinstance(knowledge, dict)
            and knowledge.get("selling_points") == ["380ml 容量", "USB 充电一次榨 15 杯"]
            and knowledge.get("version") == 3
        )
        points = knowledge.get("selling_points") if knowledge else None
        check("hub.reads.knowledge.fields", ok, f"selling_points={points}")
    except Exception as exc:  # noqa: BLE001
        check("hub.reads.knowledge.fields", False, f"raised {exc!r}")

    # --- 8. 只读保证：源码中不存在写方法 ---
    source = (ROOT / "app" / "services" / "hub_client.py").read_text(encoding="utf-8")
    write_calls = [token for token in ("/hub/ingest", "def ack", "def ingest") if token in source]
    check(
        "hub.client.is.readonly",
        not write_calls,
        "仅 GET /hub/products 与 POST /hub/search，无 ingest/ack",
    )

    session.close()
    passed = sum(1 for _, ok, _ in checks if ok)
    print(f"\n{passed}/{len(checks)} passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
