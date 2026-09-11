from datetime import datetime
from zoneinfo import ZoneInfo

from app.schemas.auth import UserProfile
from app.schemas.common import CapabilityMode, Platform, Severity
from app.schemas.workspace import (
    AlertItem,
    Organization,
    PlatformCapability,
    SearchResult,
    Shop,
    WorkspaceBootstrap,
    WorkspaceContext,
    WorkspaceSummary,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEMO_NOW = datetime(2026, 9, 11, 16, 30, tzinfo=SHANGHAI)

DEMO_USER = UserProfile(
    id="user-demo-001",
    name="徐店长",
    role_name="运营主管",
    organization_id="org-demo-001",
    permissions=[
        "dashboard:read",
        "product:read",
        "product:batch",
        "order:read",
        "after_sale:operate",
        "campaign:read",
        "asset:read",
        "diagnostic:read",
    ],
)

DEMO_SHOPS = [
    Shop(
        id="shop-all",
        name="全部店铺",
        platform=Platform.ALL,
        platform_label="全平台",
        status="active",
        last_synced_at=DEMO_NOW,
    ),
    Shop(
        id="shop-taobao-001",
        name="柔肤旗舰店",
        platform=Platform.TAOBAO,
        platform_label="淘宝",
        status="active",
        last_synced_at=DEMO_NOW,
    ),
    Shop(
        id="shop-douyin-001",
        name="柔肤抖音专营店",
        platform=Platform.DOUYIN,
        platform_label="抖店",
        status="active",
        last_synced_at=DEMO_NOW,
    ),
    Shop(
        id="shop-pdd-001",
        name="柔肤品牌馆",
        platform=Platform.PINDUODUO,
        platform_label="拼多多",
        status="warning",
        last_synced_at=DEMO_NOW.replace(minute=23),
    ),
]

WORKSPACE_BOOTSTRAP = WorkspaceBootstrap(
    organization=Organization(id="org-demo-001", name="柔肤电商事业部"),
    shops=DEMO_SHOPS,
    context=WorkspaceContext(
        organization_id="org-demo-001", shop_id="shop-all", platform=Platform.ALL
    ),
    summary=WorkspaceSummary(
        today_sales=128_640,
        paid_orders=3_186,
        active_alerts=12,
        pending_tasks=28,
        updated_at=DEMO_NOW,
    ),
)

ALERTS = [
    AlertItem(
        id="alert-001",
        title="库存预警",
        description="柔肤保湿面霜等 12 个 SKU 库存低于安全线",
        severity=Severity.CRITICAL,
        shop_id="shop-taobao-001",
        shop_name="柔肤旗舰店",
        created_at=DEMO_NOW.replace(minute=26),
    ),
    AlertItem(
        id="alert-002",
        title="售后即将超时",
        description="3 个退款申请将在 2 小时内到达处理时限",
        severity=Severity.WARNING,
        shop_id="shop-douyin-001",
        shop_name="柔肤抖音专营店",
        created_at=DEMO_NOW.replace(hour=15, minute=48),
    ),
    AlertItem(
        id="alert-003",
        title="同步完成",
        description="全部店铺商品与订单数据已完成本轮同步",
        severity=Severity.INFO,
        shop_id="shop-all",
        shop_name="全部店铺",
        created_at=DEMO_NOW.replace(hour=15, minute=30),
        is_read=True,
    ),
]

CAPABILITIES = {
    "shop-taobao-001": [
        PlatformCapability(
            key="product.update_price", label="修改商品价格", mode=CapabilityMode.ASYNC
        ),
        PlatformCapability(
            key="product.change_status", label="商品上下架", mode=CapabilityMode.DIRECT
        ),
        PlatformCapability(
            key="review.reply",
            label="回复评价",
            mode=CapabilityMode.REDIRECT,
            reason="当前授权仅支持读取评价",
        ),
    ],
    "shop-douyin-001": [
        PlatformCapability(
            key="product.update_price", label="修改商品价格", mode=CapabilityMode.ASYNC
        ),
        PlatformCapability(
            key="product.change_status", label="商品上下架", mode=CapabilityMode.ASYNC
        ),
        PlatformCapability(key="review.reply", label="回复评价", mode=CapabilityMode.DIRECT),
    ],
    "shop-pdd-001": [
        PlatformCapability(
            key="product.update_price",
            label="修改商品价格",
            mode=CapabilityMode.REDIRECT,
            reason="等待价格写入权限审核",
        ),
        PlatformCapability(
            key="product.change_status",
            label="商品上下架",
            mode=CapabilityMode.UNSUPPORTED,
            reason="当前店铺未授权",
        ),
        PlatformCapability(key="review.reply", label="回复评价", mode=CapabilityMode.REDIRECT),
    ],
}

SEARCH_INDEX = [
    SearchResult(
        id="SKU-10028",
        type="sku",
        title="柔肤保湿面霜",
        subtitle="SKU-10028 · 柔肤旗舰店",
        route="/products?sku=SKU-10028",
    ),
    SearchResult(
        id="DD20260911001",
        type="order",
        title="订单 DD20260911001",
        subtitle="张** · 待发货 · 128 元",
        route="/orders?order=DD20260911001",
    ),
    SearchResult(
        id="campaign-0915",
        type="campaign",
        title="9.15 店铺优惠券",
        subtitle="柔肤旗舰店 · 待开始",
        route="/campaigns?campaign=campaign-0915",
    ),
]
