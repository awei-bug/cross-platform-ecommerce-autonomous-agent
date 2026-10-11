from app.schemas.auth import UserProfile
from app.schemas.workspace import SearchResult

# 登录身份仍为演示账号；真实业务数据（店铺/商品/告警/能力矩阵）已迁至数据库，
# 由 app.services.seed 在空库时写入，并经由各 repository 从数据库读取。
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
        "review:read",
        "report:read",
        "asset:read",
        "diagnostic:read",
        "automation:manage",
        "integration:read",
    ],
)

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
