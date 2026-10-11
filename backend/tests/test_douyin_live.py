"""抖店真实业务链路测试（live read + live write）。

目标：证明"接上真实业务"不是靠假数据，而是真的按平台协议读写：
- 同步：调用 `product.listV2` → 落库 → 店铺切换为 live 数据源；
- 写入：`sku/list` + `sku/editPrice` / `product/setOffline` → 真实调用并翻 `is_demo`；
- 安全：未授权/缺凭证时不伪造成功。

全部使用 httpx.MockTransport 拦截网络，不需要真实店铺或凭证。
"""
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import (
    AuditLogModel,
    OperationJobModel,
    PlatformConnectionModel,
    ProductModel,
    ShopModel,
)
from app.integrations.douyin import DouyinClient
from app.main import app
from app.schemas.common import Platform
from app.schemas.products import BatchAction, JobStatus
from app.services import platform_sync
from app.services.platform_sync import (
    ProductSyncError,
    map_douyin_product,
    sync_douyin_products,
)
from app.services.platform_write import run_product_job
from app.services.token_cipher import TokenCipher

SHANGHAI = ZoneInfo("Asia/Shanghai")

# 本文件会往共享的内存库写入 live 店铺/商品，测试结束必须恢复，
# 否则会污染其它断言全局商品数量的用例。
_SHOP_IDS = (
    "shop-live-douyin-4463798",
    "shop-live-douyin-write",
    "shop-live-douyin-notoken",
)
_JOB_IDS = ("job-dy-price", "job-dy-unpublish", "job-dy-notoken")


@pytest.fixture(autouse=True)
def _restore_shared_state():
    """每个用例后清理本文件写入的 live 数据，避免污染断言全局数量的其它用例。

    纯函数用例不会启动 app（表尚未创建），此处的容错让清理保持幂等。
    """
    yield
    from sqlalchemy.exc import OperationalError

    from app.db.session import session_scope

    try:
        with session_scope() as db:
            db.query(ProductModel).filter(ProductModel.shop_id.in_(_SHOP_IDS)).delete(
                synchronize_session=False
            )
            db.query(ShopModel).filter(ShopModel.id.in_(_SHOP_IDS)).delete(
                synchronize_session=False
            )
            db.query(AuditLogModel).filter(AuditLogModel.job_id.in_(_JOB_IDS)).delete(
                synchronize_session=False
            )
            db.query(OperationJobModel).filter(OperationJobModel.id.in_(_JOB_IDS)).delete(
                synchronize_session=False
            )
            connection = db.scalar(
                select(PlatformConnectionModel).where(
                    PlatformConnectionModel.platform == Platform.DOUYIN.value
                )
            )
            if connection is not None:
                connection.state = "revoked"
                connection.encrypted_access_token = None
                connection.updated_at = datetime.now(SHANGHAI)
    except OperationalError:
        pass


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def settings():
    from app.core.config import get_settings

    return get_settings()


def _build_client(handler) -> DouyinClient:
    return DouyinClient(
        app_key="dy-key",
        app_secret="dy-secret",
        redirect_uri="https://example.test/callback",
        auth_base_url="https://open.douyin.com/platform/oauth/connect",
        token_base_url="https://openapi-fxg.jinritemai.com",
        api_base_url="https://openapi-fxg.jinritemai.com",
        transport=httpx.MockTransport(handler),
    )


def _douyin_rows() -> list[dict]:
    """抖店 product.listV2 样例响应（价格单位为分）。"""
    return [
        {
            "product_id": "3501000001",
            "name": "抖店真实商品 A",
            "outer_product_id": "OPT-001",
            "price": 12900,
            "stock": 8,
            "status": 0,
        },
        {
            "product_id": "3501000002",
            "name": "抖店真实商品 B",
            "outer_product_id": "OPT-002",
            "price": 9900,
            "stock": 240,
            "status": 1,
        },
    ]


def _prepare_write_target(db, cipher: TokenCipher) -> None:
    """准备一个 live 抖店 + 已授权连接 + 一件真实商品，供写操作用例共用。

    每个写用例都自己准备，避免用例之间隐式依赖（teardown 会清掉这些数据）。
    """
    shop_id = "shop-live-douyin-write"
    if db.get(ShopModel, shop_id) is None:
        db.add(
            ShopModel(
                id=shop_id,
                organization_id="org-demo-001",
                platform=Platform.DOUYIN.value,
                platform_label="抖店",
                name="抖店授权店",
                status="active",
                last_synced_at=datetime.now(SHANGHAI),
                data_source="live",
                capabilities=[],
            )
        )
    if db.get(ProductModel, "product-dy-write-1") is None:
        db.add(
            ProductModel(
                id="product-dy-write-1",
                organization_id="org-demo-001",
                shop_id=shop_id,
                sku="DY-3501",
                platform_item_id="3501000001",
                title="抖店商品",
                platform=Platform.DOUYIN.value,
                platform_label="抖店",
                shop_name="抖店授权店",
                status="online",
                risk="normal",
                risk_labels=[],
                price=129.0,
                cost=40.0,
                stock=10,
                sales_7d=1,
                revenue_7d=129.0,
                conversion_rate=1.0,
                updated_at=datetime.now(SHANGHAI),
            )
        )
    connection = db.scalar(
        select(PlatformConnectionModel).where(
            PlatformConnectionModel.platform == Platform.DOUYIN.value
        )
    )
    connection.state = "ready"
    connection.encrypted_access_token = cipher.encrypt("FAKE_DY_TOKEN")
    connection.platform_shop_id = "4463798"
    connection.updated_at = datetime.now(SHANGHAI)


def test_map_douyin_product_converts_fen_to_yuan_and_low_stock_risk() -> None:
    mapped = map_douyin_product(_douyin_rows()[0])
    assert mapped["price"] == 129.0  # 抖店以「分」计价
    assert mapped["sku"] == "OPT-001"
    assert mapped["platform_item_id"] == "3501000001"
    assert mapped["status"] == "online"
    assert mapped["risk"] == "warning"  # 库存 8 低于安全线 25
    assert "库存低于安全线" in mapped["risk_labels"][0]

    offline = map_douyin_product(_douyin_rows()[1])
    assert offline["status"] == "offline"
    assert offline["risk"] == "normal"
    assert "商品未上架" in offline["risk_labels"]

    missing_sku = map_douyin_product({"product_id": "999", "name": "无编码", "status": 0})
    assert missing_sku["sku"] == "DY-999"


def test_sync_pulls_real_products_and_switches_shop_to_live(client: TestClient, settings) -> None:
    from app.db.session import session_scope

    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = dict(urllib.parse.parse_qsl(request.content.decode()))
        calls.append(body)
        method = body.get("method")
        if method == "product.listV2":
            return httpx.Response(
                200, json={"err_no": 0, "data": {"products": _douyin_rows(), "total": 2}}
            )
        return httpx.Response(200, json={"err_no": 0, "data": {}})

    douyin_client = _build_client(handler)
    cipher = TokenCipher(settings.token_encryption_keys)

    with session_scope() as db:
        connection = db.scalar(
            select(PlatformConnectionModel).where(
                PlatformConnectionModel.organization_id == "org-demo-001",
                PlatformConnectionModel.platform == Platform.DOUYIN.value,
            )
        )
        if connection is None:
            connection = PlatformConnectionModel(
                id="conn-dy-live",
                organization_id="org-demo-001",
                platform=Platform.DOUYIN.value,
                created_at=datetime.now(SHANGHAI),
                updated_at=datetime.now(SHANGHAI),
                scopes=[],
            )
            db.add(connection)
        connection.state = "ready"
        connection.encrypted_access_token = cipher.encrypt("FAKE_DY_TOKEN")
        connection.platform_shop_id = "4463798"
        connection.platform_shop_name = "抖店开放平台测试专用旗舰店"
        connection.updated_at = datetime.now(SHANGHAI)
        db.commit()

    with session_scope() as db:
        result = sync_douyin_products(db, settings=settings, client=douyin_client)

    assert result.is_live is True
    assert result.created == 2
    assert result.total_fetched == 2
    assert result.shop_id == "shop-live-douyin-4463798"
    assert calls and calls[0]["method"] == "product.listV2"

    with session_scope() as db:
        shop = db.get(ShopModel, "shop-live-douyin-4463798")
        assert shop is not None
        assert shop.data_source == "live"
        assert shop.last_synced_at is not None

        products = db.scalars(
            select(ProductModel).where(ProductModel.shop_id == result.shop_id)
        ).all()
        assert len(products) == 2
        by_item = {p.platform_item_id: p for p in products}
        assert by_item["3501000001"].title == "抖店真实商品 A"
        assert by_item["3501000001"].price == 129.0
        assert by_item["3501000001"].platform == Platform.DOUYIN.value

        # 再次同步必须幂等：不产生重复行
        again = sync_douyin_products(db, settings=settings, client=douyin_client)
        assert again.created == 0
        assert again.updated == 0
        assert again.unchanged == 2
        products = db.scalars(
            select(ProductModel).where(ProductModel.shop_id == result.shop_id)
        ).all()
        assert products != []


def test_sync_refuses_when_not_authorized(client: TestClient, settings) -> None:
    from app.db.session import session_scope

    douyin_client = _build_client(
        lambda _request: httpx.Response(200, json={"err_no": 0, "data": {}})
    )

    with session_scope() as db:
        connection = db.scalar(
            select(PlatformConnectionModel).where(
                PlatformConnectionModel.platform == Platform.DOUYIN.value
            )
        )
        connection.state = "revoked"
        connection.encrypted_access_token = None
        connection.updated_at = datetime.now(SHANGHAI)
        db.commit()

        with pytest.raises(ProductSyncError, match="尚未完成授权"):
            sync_douyin_products(db, settings=settings, client=douyin_client)


def test_sync_requires_server_credentials(client: TestClient) -> None:
    from app.db.session import session_scope

    empty = platform_sync.Settings(
        douyin_app_key=None,
        douyin_app_secret=None,
        token_encryption_keys="",
    )
    with session_scope() as db:
        with pytest.raises(ProductSyncError, match="DOUYIN_APP_KEY"):
            sync_douyin_products(db, settings=empty, client=None)


def test_douyin_real_price_update_calls_platform_and_flips_is_demo(
    client: TestClient, settings
) -> None:
    from app.db.session import session_scope

    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = dict(urllib.parse.parse_qsl(request.content.decode()))
        calls.append(body)
        method = body.get("method")
        if method == "sku/list":
            return httpx.Response(
                200, json={"err_no": 0, "data": {"sku_list": [{"sku_id": "sku-dy-1"}]}}
            )
        return httpx.Response(200, json={"err_no": 0, "data": {}})

    douyin_client = _build_client(handler)
    cipher = TokenCipher(settings.token_encryption_keys)

    with session_scope() as db:
        _prepare_write_target(db, cipher)
        db.add(
            OperationJobModel(
                id="job-dy-price",
                kind="product",
                action=BatchAction.UPDATE_PRICE.value,
                idempotency_key="dy-price-key",
                status=JobStatus.QUEUED.value,
                progress=0,
                total=1,
                succeeded=0,
                failed=0,
                entity_ids=["product-dy-write-1"],
                payload={"price": 99.0},
                results=[],
                created_at=datetime.now(SHANGHAI),
                updated_at=datetime.now(SHANGHAI),
                is_demo=True,
            )
        )
        db.commit()

    with session_scope() as db:
        run_product_job(
            db,
            db.get(OperationJobModel, "job-dy-price"),
            settings=settings,
            douyin_client=douyin_client,
        )

    methods = [body["method"] for body in calls if "method" in body]
    assert "sku/list" in methods
    assert "sku.editPrice" in methods or "sku/editPrice" in methods

    edit_call = next(body for body in calls if body.get("method") == "sku/editPrice")
    param_json = urllib.parse.unquote(edit_call["param_json"])
    assert "sku-dy-1" in param_json
    assert "9900" in param_json  # 99 元 → 9900 分

    with session_scope() as db:
        job = db.get(OperationJobModel, "job-dy-price")
        assert job.is_demo is False
        assert job.succeeded == 1
        assert db.get(ProductModel, "product-dy-write-1").price == 99.0
        audit = db.scalars(
            select(AuditLogModel).where(AuditLogModel.job_id == "job-dy-price")
        ).all()
        assert len(audit) == 1
        assert audit[0].is_demo is False


def test_douyin_unpublish_calls_set_offline(client: TestClient, settings) -> None:
    from app.db.session import session_scope

    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = dict(urllib.parse.parse_qsl(request.content.decode()))
        calls.append(body)
        return httpx.Response(200, json={"err_no": 0, "data": {}})

    douyin_client = _build_client(handler)
    cipher = TokenCipher(settings.token_encryption_keys)

    with session_scope() as db:
        _prepare_write_target(db, cipher)
        db.add(
            OperationJobModel(
                id="job-dy-unpublish",
                kind="product",
                action=BatchAction.UNPUBLISH.value,
                idempotency_key="dy-unpublish-key",
                status=JobStatus.QUEUED.value,
                progress=0,
                total=1,
                succeeded=0,
                failed=0,
                entity_ids=["product-dy-write-1"],
                payload={},
                results=[],
                created_at=datetime.now(SHANGHAI),
                updated_at=datetime.now(SHANGHAI),
                is_demo=True,
            )
        )
        db.commit()

    with session_scope() as db:
        run_product_job(
            db,
            db.get(OperationJobModel, "job-dy-unpublish"),
            settings=settings,
            douyin_client=douyin_client,
        )

    assert [body["method"] for body in calls] == ["product/setOffline"]
    param_json = urllib.parse.unquote(calls[0]["param_json"])
    assert "3501000001" in param_json

    with session_scope() as db:
        job = db.get(OperationJobModel, "job-dy-unpublish")
        assert job.is_demo is False
        assert job.succeeded == 1
        assert db.get(ProductModel, "product-dy-write-1").status == "offline"


def test_douyin_write_without_token_fails_safe(client: TestClient, settings) -> None:
    from app.db.session import session_scope

    douyin_client = _build_client(
        lambda _request: httpx.Response(200, json={"err_no": 0, "data": {}})
    )
    shop_id = "shop-live-douyin-notoken"

    with session_scope() as db:
        if db.get(ShopModel, shop_id) is None:
            db.add(
                ShopModel(
                    id=shop_id,
                    organization_id="org-demo-001",
                    platform=Platform.DOUYIN.value,
                    platform_label="抖店",
                    name="未授权抖店",
                    status="active",
                    last_synced_at=datetime.now(SHANGHAI),
                    data_source="live",
                    capabilities=[],
                )
            )
        if db.get(ProductModel, "product-dy-notoken") is None:
            db.add(
                ProductModel(
                    id="product-dy-notoken",
                    organization_id="org-demo-001",
                    shop_id=shop_id,
                    sku="DY-NT",
                    platform_item_id="3501999999",
                    title="未授权抖店商品",
                    platform=Platform.DOUYIN.value,
                    platform_label="抖店",
                    shop_name="未授权抖店",
                    status="online",
                    risk="normal",
                    risk_labels=[],
                    price=50.0,
                    cost=20.0,
                    stock=5,
                    sales_7d=1,
                    revenue_7d=50.0,
                    conversion_rate=1.0,
                    updated_at=datetime.now(SHANGHAI),
                )
            )
        connection = db.scalar(
            select(PlatformConnectionModel).where(
                PlatformConnectionModel.platform == Platform.DOUYIN.value
            )
        )
        connection.state = "revoked"
        connection.encrypted_access_token = None
        connection.updated_at = datetime.now(SHANGHAI)
        db.add(
            OperationJobModel(
                id="job-dy-notoken",
                kind="product",
                action=BatchAction.UPDATE_PRICE.value,
                idempotency_key="dy-notoken-key",
                status=JobStatus.QUEUED.value,
                progress=0,
                total=1,
                succeeded=0,
                failed=0,
                entity_ids=["product-dy-notoken"],
                payload={"price": 30.0},
                results=[],
                created_at=datetime.now(SHANGHAI),
                updated_at=datetime.now(SHANGHAI),
                is_demo=True,
            )
        )
        db.commit()

    with session_scope() as db:
        run_product_job(
            db,
            db.get(OperationJobModel, "job-dy-notoken"),
            settings=settings,
            douyin_client=douyin_client,
        )

    with session_scope() as db:
        job = db.get(OperationJobModel, "job-dy-notoken")
        assert job.is_demo is True
        assert job.failed == 1
        assert "未授权" in job.results[0]["message"]
        assert db.get(ProductModel, "product-dy-notoken").price == 50.0  # 未回写
