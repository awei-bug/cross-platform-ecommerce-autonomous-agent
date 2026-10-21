"""平台真实商品同步：把已授权店铺的平台商品落库，并把店铺切换为 live 数据源。

这条链路是"接上真实业务"的关键一步，设计上遵循三条约束：

- **只写真实数据**：同步只在平台连接处于 `ready` 且凭证可用时执行，否则返回
  `is_live=False`，绝不拿模拟数据冒充真实店铺数据（见 ProductSyncResponse）。
- **幂等 upsert**：以平台商品 ID 为准做幂等，重复同步不会产生重复行，`unchanged`
  用于表达"本次无变化"，便于前端展示真实增量。
- **不编造平台没返回的字段**：销量、转化率、成本价平台列表接口并不返回，
  已存在则保留原有值，新建则置 0 并写入 `warnings`，而不是随手造一个数。
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import ProductModel, ShopModel
from app.integrations.douyin import DouyinApiError, DouyinClient
from app.schemas.common import Platform
from app.schemas.integrations import ProductSyncResponse
from app.schemas.products import ProductRisk, ProductStatus
from app.services.douyin_connections import get_douyin_connection
from app.services.token_cipher import TokenCipher

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_ORG = "org-demo-001"
PLATFORM_LABEL = "抖店"

LOW_STOCK_THRESHOLD = 25

# 抖店商品在店铺中的状态：0-在线；1-下线；2-删除
_DOUYIN_STATUS_CODES: dict[int, str] = {
    0: ProductStatus.ONLINE.value,
    1: ProductStatus.OFFLINE.value,
    2: ProductStatus.OFFLINE.value,
}


class ProductSyncError(RuntimeError):
    """同步前置条件不满足（未授权/缺凭证/平台报错）。"""


def build_douyin_client(settings: Settings) -> DouyinClient | None:
    if not settings.douyin_app_key or not settings.douyin_app_secret:
        return None
    return DouyinClient(
        app_key=settings.douyin_app_key,
        app_secret=settings.douyin_app_secret,
        redirect_uri=settings.douyin_redirect_uri or "",
        auth_base_url=settings.douyin_auth_base_url,
        token_base_url=settings.douyin_token_base_url,
        api_base_url=settings.douyin_api_base_url,
        timeout_seconds=settings.douyin_http_timeout_seconds,
        max_attempts=settings.douyin_http_max_attempts,
    )


def _live_douyin_access_token(db: Session, organization_id: str, cipher: TokenCipher) -> str | None:
    connection = get_douyin_connection(db, organization_id)
    if connection is None or connection.state != "ready" or not connection.encrypted_access_token:
        return None
    return cipher.decrypt(connection.encrypted_access_token)


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _resolve_external_id(product_id: str) -> str:
    """抖店同步商品的 data-hub 外部身份。

    命名带平台前缀，避免与 data-hub 原生 external_id（内容平台侧 `cc-*`）混淆，
    也让幂等优先级里"哪些商品是抖店来的"一眼可辨。
    """
    return f"dy-{product_id}" if product_id else ""


def map_douyin_product(row: dict) -> dict:
    """把抖店 `product.listV2` 的单条记录映射为 ProductModel 字段字典。

    抖店价格单位为「分」，此处统一折算为「元」。
    """
    raw_title = row.get("name") or row.get("product_name")
    title = str(raw_title).strip() if raw_title else ""
    product_id = str(row.get("product_id") or row.get("productId") or "").strip()
    title = title or f"未命名商品 {product_id}"
    raw_status = row.get("status")
    status = _DOUYIN_STATUS_CODES.get(_coerce_int(raw_status, -1), ProductStatus.OFFLINE.value)
    stock = _coerce_int(row.get("stock") or row.get("stock_num"))
    price = _coerce_float(row.get("price")) / 100

    risk = ProductRisk.NORMAL.value
    risk_labels: list[str] = []
    if stock <= 0:
        risk = ProductRisk.CRITICAL.value
        risk_labels.append("库存为零")
    elif stock <= LOW_STOCK_THRESHOLD:
        risk = ProductRisk.WARNING.value
        risk_labels.append(f"库存低于安全线 {LOW_STOCK_THRESHOLD} 件")
    if status == ProductStatus.OFFLINE.value:
        risk_labels.append("商品未上架")

    return {
        "sku": str(row.get("outer_product_id") or "").strip() or f"DY-{product_id}",
        "platform_item_id": product_id,
        "external_id": _resolve_external_id(product_id),
        "title": title[:200],
        "status": status,
        "risk": risk,
        "risk_labels": risk_labels,
        "price": round(price, 2),
        "stock": stock,
    }


def _ensure_live_shop(
    db: Session, *, shop_id: str, shop_name: str, now: datetime
) -> ShopModel:
    shop = db.get(ShopModel, shop_id)
    if shop is None:
        shop = ShopModel(
            id=shop_id,
            organization_id=DEFAULT_ORG,
            platform=Platform.DOUYIN.value,
            platform_label=PLATFORM_LABEL,
            name=shop_name,
            status="active",
            data_source="live",
            capabilities=[],
        )
        db.add(shop)
    shop.name = shop_name
    shop.data_source = "live"
    shop.last_synced_at = now
    shop.status = "active"
    return shop


def sync_douyin_products(
    db: Session,
    *,
    settings: Settings | None = None,
    client: DouyinClient | None = None,
    page_size: int = 50,
    max_pages: int = 20,
) -> ProductSyncResponse:
    """同步抖店真实商品到数据库。

    前置条件：抖店连接已授权（`ready`）且服务端凭证齐全。任一不满足都会
    抛出 `ProductSyncError`，由路由层转成明确的 HTTP 错误。
    """
    settings = settings or get_settings()
    # 先校验服务端凭证，避免把「凭证缺失」错报成「加密密钥缺失」。
    douyin_client = client or build_douyin_client(settings)
    if douyin_client is None:
        raise ProductSyncError("缺少 DOUYIN_APP_KEY / DOUYIN_APP_SECRET，无法同步真实店铺数据")
    cipher = TokenCipher(settings.token_encryption_keys)

    connection = get_douyin_connection(db, DEFAULT_ORG)
    if connection is None or connection.state != "ready":
        raise ProductSyncError("抖店尚未完成授权，请先完成店铺授权再同步")
    access_token = _live_douyin_access_token(db, DEFAULT_ORG, cipher)
    if not access_token:
        raise ProductSyncError("抖店授权凭证不可用，请重新发起授权")

    shop_name = connection.platform_shop_name or PLATFORM_LABEL
    platform_shop_id = connection.platform_shop_id or "default"
    shop_id = f"shop-live-douyin-{platform_shop_id}"

    now = datetime.now(SHANGHAI)
    rows: list[dict] = []
    total_reported = 0
    try:
        for page in range(1, max_pages + 1):
            page_rows, total = asyncio.run(
                douyin_client.list_products(access_token, page=page, size=page_size)
            )
            rows.extend(page_rows)
            total_reported = max(total_reported, total)
            if not page_rows or len(rows) >= total_reported:
                break
    except DouyinApiError as exc:
        raise ProductSyncError(f"调用抖店商品接口失败：{exc}") from exc

    # 幂等优先级：external_id > platform_item_id > sku。
    #
    # 按契约 [商品主数据契约.md](../../../电商垂类整合计划/商品主数据契约.md) 规则 2，
    # external_id 是 data-hub 的唯一身份，抖店同步来的商品统一记 `dy-{platform_item_id}`，
    # 与 data-hub 原生 `cc-*` 不冲突。这里先按 external_id 建索引，历史行没有
    # external_id 时回落到 platform_item_id，保证老数据重复同步仍命中同一行。
    existing: dict[str, ProductModel] = {}
    for product in db.query(ProductModel).filter(
        ProductModel.shop_id == shop_id,
        ProductModel.platform == Platform.DOUYIN.value,
    ):
        if product.external_id:
            existing.setdefault(product.external_id, product)
        if product.platform_item_id:
            existing.setdefault(product.platform_item_id, product)

    created = updated = unchanged = 0
    seen_ids: set[str] = set()
    for row in rows:
        mapped = map_douyin_product(row)
        product_id = mapped["platform_item_id"]
        if not product_id:
            continue
        seen_ids.add(product_id)
        external_id = mapped["external_id"]
        model = existing.get(external_id) or existing.get(product_id)
        if model is not None:
            # 命中后补写 external_id：老行此前为空，首次同步即完成身份对齐。
            if not model.external_id:
                model.external_id = external_id
                existing.setdefault(external_id, model)
        if model is None:
            model = ProductModel(
                id=f"product-dy-{product_id}",
                organization_id=DEFAULT_ORG,
                shop_id=shop_id,
                platform=Platform.DOUYIN.value,
                platform_label=PLATFORM_LABEL,
                shop_name=shop_name,
                cost=0.0,
                sales_7d=0,
                revenue_7d=0.0,
                conversion_rate=0.0,
                updated_at=now,
                **mapped,
            )
            db.add(model)
            created += 1
            continue
        changed = False
        for field, value in mapped.items():
            if getattr(model, field) != value:
                setattr(model, field, value)
                changed = True
        model.shop_name = shop_name
        model.updated_at = now
        updated += 1 if changed else 0
        unchanged += 1 if not changed else 0

    _ensure_live_shop(db, shop_id=shop_id, shop_name=shop_name, now=now)

    warnings: list[str] = []
    if created:
        warnings.append(
            "平台商品列表不返回成本价、7 日销量与转化率，"
            "新建商品这些指标为 0，请在详情页维护成本价后再看毛利相关指标。"
        )
    if total_reported and total_reported > len(rows):
        warnings.append(
            f"本次最多同步 {max_pages} 页共 {len(rows)} 件，店铺实际共 {total_reported} 件。"
        )

    db.commit()
    return ProductSyncResponse(
        platform=Platform.DOUYIN,
        shop_id=shop_id,
        shop_name=shop_name,
        data_source="live",
        is_live=True,
        created=created,
        updated=updated,
        unchanged=unchanged,
        total_fetched=len(rows),
        warnings=warnings,
        synced_at=now,
    )
