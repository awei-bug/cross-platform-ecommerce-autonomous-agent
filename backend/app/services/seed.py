from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AlertModel,
    AlertStateModel,
    ProductModel,
    ShopModel,
    WorkspaceStatsModel,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEMO_NOW = datetime(2026, 9, 12, 9, 40, tzinfo=SHANGHAI)
DEFAULT_ORG = "org-demo-001"

# 店铺主键 -> (platform, label, shop_id, shop_name)
SHOP_DATA = {
    "taobao": ("taobao", "淘宝", "shop-taobao-001", "柔肤旗舰店"),
    "douyin": ("douyin", "抖店", "shop-douyin-001", "柔肤抖音专营店"),
    "pdd": ("pinduoduo", "拼多多", "shop-pdd-001", "柔肤品牌馆"),
}

SEED_SHOPS = [
    {
        "id": "shop-all",
        "organization_id": DEFAULT_ORG,
        "platform": "all",
        "platform_label": "全平台",
        "name": "全部店铺",
        "status": "active",
        "last_synced_at": DEMO_NOW,
        "data_source": "seeded",
        "capabilities": [],
    },
    {
        "id": "shop-taobao-001",
        "organization_id": DEFAULT_ORG,
        "platform": "taobao",
        "platform_label": "淘宝",
        "name": "柔肤旗舰店",
        "status": "active",
        "last_synced_at": DEMO_NOW,
        "data_source": "seeded",
        "capabilities": [
            {"key": "product.update_price", "label": "修改商品价格", "mode": "async"},
            {"key": "product.change_status", "label": "商品上下架", "mode": "direct"},
            {"key": "order.after_sale", "label": "处理售后", "mode": "async"},
            {"key": "order.remind_ship", "label": "催促发货", "mode": "direct"},
            {
                "key": "review.reply",
                "label": "回复评价",
                "mode": "redirect",
                "reason": "当前授权仅支持读取评价",
            },
        ],
    },
    {
        "id": "shop-douyin-001",
        "organization_id": DEFAULT_ORG,
        "platform": "douyin",
        "platform_label": "抖店",
        "name": "柔肤抖音专营店",
        "status": "active",
        "last_synced_at": DEMO_NOW,
        "data_source": "seeded",
        "capabilities": [
            {"key": "product.update_price", "label": "修改商品价格", "mode": "async"},
            {"key": "product.change_status", "label": "商品上下架", "mode": "async"},
            {"key": "order.after_sale", "label": "处理售后", "mode": "async"},
            {"key": "order.remind_ship", "label": "催促发货", "mode": "async"},
            {"key": "review.reply", "label": "回复评价", "mode": "direct"},
        ],
    },
    {
        "id": "shop-pdd-001",
        "organization_id": DEFAULT_ORG,
        "platform": "pinduoduo",
        "platform_label": "拼多多",
        "name": "柔肤品牌馆",
        "status": "warning",
        "last_synced_at": DEMO_NOW.replace(minute=23),
        "data_source": "seeded",
        "capabilities": [
            {
                "key": "product.update_price",
                "label": "修改商品价格",
                "mode": "redirect",
                "reason": "等待价格写入权限审核",
            },
            {
                "key": "product.change_status",
                "label": "商品上下架",
                "mode": "unsupported",
                "reason": "当前店铺未授权",
            },
            {
                "key": "order.after_sale",
                "label": "处理售后",
                "mode": "redirect",
                "reason": "需前往拼多多商家后台确认退款",
            },
            {
                "key": "order.remind_ship",
                "label": "催促发货",
                "mode": "unsupported",
                "reason": "当前平台不支持通过开放 API 催单",
            },
            {"key": "review.reply", "label": "回复评价", "mode": "redirect"},
        ],
    },
]

# 每行：sku, 标题, 店铺键, 状态, 风险, 价格, 成本, 库存, 7日销量, 7日销售额, 转化率, 风险标签
SEED_PRODUCT_ROWS = [
    (
        "10028", "柔肤保湿面霜", "taobao", "online", "critical",
        129.0, 47.0, 8, 386, 49794.0, 4.8,
        ["库存低于安全线", "近 24 小时流量上涨"],
    ),
    (
        "10031", "玻尿酸修护精华液", "douyin", "online", "warning",
        159.0, 58.0, 26, 312, 49608.0, 5.6,
        ["竞品降价", "转化率波动"],
    ),
    (
        "10042", "氨基酸净澈洁面乳", "pdd", "offline", "critical",
        69.0, 24.0, 0, 271, 18699.0, 3.9,
        ["商品下架", "库存为零"],
    ),
    (
        "10056", "舒缓修红面膜 10 片", "taobao", "online", "normal",
        99.0, 35.0, 128, 249, 24651.0, 4.2, [],
    ),
    (
        "10063", "清透防晒乳 SPF50+", "douyin", "online", "warning",
        119.0, 42.0, 34, 228, 27132.0, 3.5,
        ["活动价即将到期"],
    ),
    (
        "10077", "烟酰胺焕亮身体乳", "pdd", "draft", "normal",
        79.0, 28.0, 96, 0, 0.0, 0.0, [],
    ),
    (
        "10084", "神经酰胺屏障乳", "taobao", "online", "warning",
        139.0, 51.0, 18, 203, 28217.0, 4.0,
        ["库存可售 2.1 天"],
    ),
    (
        "10091", "积雪草舒缓喷雾", "douyin", "offline", "warning",
        89.0, 31.0, 42, 176, 15664.0, 3.2,
        ["审核素材待更新"],
    ),
    (
        "10103", "水杨酸净痘凝胶", "pdd", "online", "normal",
        59.0, 19.0, 156, 168, 9912.0, 4.6, [],
    ),
    (
        "10117", "胶原紧致眼霜", "taobao", "draft", "normal",
        169.0, 62.0, 73, 0, 0.0, 0.0, [],
    ),
    (
        "10129", "多肽抗皱精华霜", "douyin", "online", "critical",
        199.0, 77.0, 11, 142, 28258.0, 2.7,
        ["差评率升高", "库存紧张"],
    ),
    (
        "10136", "茶树控油爽肤水", "pdd", "online", "warning",
        75.0, 25.0, 23, 139, 10425.0, 3.8,
        ["竞品低价 8%"],
    ),
    (
        "10148", "牛油果滋养唇膜", "taobao", "online", "normal",
        49.0, 14.0, 215, 132, 6468.0, 5.1, [],
    ),
    (
        "10155", "VC 焕亮安瓶精华", "douyin", "online", "normal",
        189.0, 71.0, 87, 124, 23436.0, 4.4, [],
    ),
    (
        "10169", "洋甘菊舒敏水乳套装", "pdd", "offline", "critical",
        219.0, 84.0, 6, 116, 25404.0, 3.1,
        ["疑似价格冲突", "库存低"],
    ),
    (
        "10172", "海藻补水睡眠面膜", "taobao", "online", "normal",
        109.0, 39.0, 144, 109, 11881.0, 4.7, [],
    ),
    (
        "10188", "咖啡因紧致颈霜", "douyin", "draft", "warning",
        149.0, 55.0, 61, 0, 0.0, 0.0,
        ["主图清晰度不足"],
    ),
    (
        "10195", "益生元温和卸妆膏", "pdd", "online", "normal",
        95.0, 33.0, 198, 96, 9120.0, 4.1, [],
    ),
]

SEED_ALERTS = [
    {
        "id": "alert-001",
        "organization_id": DEFAULT_ORG,
        "title": "库存预警",
        "description": "柔肤保湿面霜等 12 个 SKU 库存低于安全线",
        "severity": "critical",
        "shop_id": "shop-taobao-001",
        "shop_name": "柔肤旗舰店",
        "created_at": DEMO_NOW.replace(minute=26),
    },
    {
        "id": "alert-002",
        "organization_id": DEFAULT_ORG,
        "title": "售后即将超时",
        "description": "3 个退款申请将在 2 小时内到达处理时限",
        "severity": "warning",
        "shop_id": "shop-douyin-001",
        "shop_name": "柔肤抖音专营店",
        "created_at": DEMO_NOW.replace(hour=15, minute=48),
    },
    {
        "id": "alert-003",
        "organization_id": DEFAULT_ORG,
        "title": "同步完成",
        "description": "全部店铺商品与订单数据已完成本轮同步",
        "severity": "info",
        "shop_id": "shop-all",
        "shop_name": "全部店铺",
        "created_at": DEMO_NOW.replace(hour=15, minute=30),
    },
]

SEED_STATS = {
    "organization_id": DEFAULT_ORG,
    "today_sales": 128_640,
    "paid_orders": 3_186,
    "active_alerts": 12,
    "pending_tasks": 28,
    "updated_at": DEMO_NOW,
}


def _build_product_row(row: tuple) -> dict:
    (
        sku,
        title,
        shop_key,
        status,
        risk,
        price,
        cost,
        stock,
        sales_7d,
        revenue_7d,
        conversion_rate,
        labels,
    ) = row
    platform, platform_label, shop_id, shop_name = SHOP_DATA[shop_key]
    return {
        "id": f"product-{sku}",
        "organization_id": DEFAULT_ORG,
        "shop_id": shop_id,
        "sku": f"SKU-{sku}",
        "platform_item_id": f"NUMIID-{sku}",
        "title": title,
        "platform": platform,
        "platform_label": platform_label,
        "shop_name": shop_name,
        "status": status,
        "risk": risk,
        "risk_labels": labels,
        "price": price,
        "cost": cost,
        "stock": stock,
        "sales_7d": sales_7d,
        "revenue_7d": revenue_7d,
        "conversion_rate": conversion_rate,
        "updated_at": DEMO_NOW,
    }


def seed_if_empty(db: Session) -> bool:
    """把种子演示店数据写入数据库。仅当 shops 表为空时执行，避免重复写入。"""
    existing = db.scalar(select(ShopModel).limit(1))
    if existing is not None:
        return False

    for shop in SEED_SHOPS:
        db.add(ShopModel(**shop))
    for row in SEED_PRODUCT_ROWS:
        db.add(ProductModel(**_build_product_row(row)))
    for alert in SEED_ALERTS:
        db.add(AlertModel(**alert))
    db.add(WorkspaceStatsModel(**SEED_STATS))
    # alert-003 默认已读，保持与原始演示一致
    db.add(
        AlertStateModel(
            alert_id="alert-003",
            is_read=True,
            read_at=DEMO_NOW,
            updated_at=DEMO_NOW,
        )
    )
    db.commit()
    return True
