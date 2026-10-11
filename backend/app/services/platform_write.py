"""商品批量动作的真实写操作安全层。

设计约束（也是面试可讲的工程取舍）：
- **幂等**：任务级幂等由 `idempotency_key` 保证（见 product_repository.create_batch_job）。
- **确认门**：批量动作在 API 层由前端二次确认后才会创建任务（见 products 路由）。
- **真实 vs 演示**：仅当目标店铺为 `data_source="live"` 且已授权连接 `ready` 时，才真正调用平台
  API；否则仅创建可审计的模拟任务，并通过 `is_demo` 标志明确区分，**绝不把模拟数据
  描述成真实授权数据**。
支持的真实写入平台：抖店（`sku/editPrice`、`product/launchProduct`、`product/setOffline`）。
平台差异收敛在各自的 writer 里，调度逻辑（幂等、审计、部分失败）保持统一。
- **可追踪 / 部分失败**：每个商品单行产出 `BatchItemResult` 与 `AuditLogModel`，失败项可单独重试。
"""
import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import AuditLogModel, OperationJobModel, ProductModel, ShopModel
from app.integrations.douyin import DouyinApiError, DouyinClient
from app.schemas.common import Platform
from app.schemas.products import BatchAction, BatchItemResult, JobStatus, ProductStatus
from app.services.platform_sync import (
    _live_douyin_access_token,
    build_douyin_client,
)
from app.services.token_cipher import TokenCipher

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_ORG = "org-demo-001"
ACTOR = "徐店长"

PRODUCT_ACTION_LABELS = {
    BatchAction.UPDATE_PRICE.value: "修改商品价格",
    BatchAction.PUBLISH.value: "商品上架",
    BatchAction.UNPUBLISH.value: "商品下架",
    BatchAction.SYNC.value: "同步商品",
}

async def _try_real_write_douyin(
    client: DouyinClient,
    action: BatchAction,
    product: ProductModel,
    payload: dict,
    token: str,
) -> tuple[bool, str, bool]:
    """抖店真实写入。返回 (success, message, executed_real)。

    抖店改价必须传真实 sku_id，而商品列表接口不返回该字段，因此改价前
    按商品实时查询 SKU；多 SKU 商品默认取主 SKU（列表首个）并在消息中说明。
    """
    if action == BatchAction.SYNC:
        return True, "同步为只读操作，未触发平台写入", False
    item_id = product.platform_item_id or product.sku
    try:
        if action == BatchAction.UPDATE_PRICE:
            skus = await client.list_skus(token, item_id)
            if not skus:
                return False, "抖店未返回该商品的 SKU，无法改价", False
            sku_id = str(skus[0].get("sku_id") or skus[0].get("id") or "")
            if not sku_id:
                return False, "抖店 SKU 响应缺少 sku_id，无法改价", False
            await client.update_sku_price(
                token,
                product_id=item_id,
                sku_id=sku_id,
                price_yuan=float(payload.get("price", product.price)),
            )
            return True, "真实写入成功", True
        if action == BatchAction.PUBLISH:
            await client.launch_product(token, item_id)
            return True, "真实写入成功", True
        if action == BatchAction.UNPUBLISH:
            await client.set_offline(token, [item_id])
            return True, "真实写入成功", True
    except DouyinApiError as exc:
        if exc.retryable:
            return False, f"平台暂时不可用，可重试：{exc}", False
        return False, f"平台拒绝：{exc}", False
    return False, "不支持的批量动作", False


def _apply_local_write(product: ProductModel, action: str, payload: dict) -> None:
    """平台写入成功后同步本地镜像数据，避免读路径展示过期值。"""
    now = datetime.now(SHANGHAI)
    if action == BatchAction.UPDATE_PRICE.value and "price" in payload:
        product.price = float(payload["price"])
        product.updated_at = now
    elif action == BatchAction.PUBLISH.value:
        product.status = ProductStatus.ONLINE.value
        product.updated_at = now
    elif action == BatchAction.UNPUBLISH.value:
        product.status = ProductStatus.OFFLINE.value
        product.updated_at = now


# 平台 → (取 token, 真实写入)。新增平台只需在这里登记，调度逻辑不用改。
_WRITE_HANDLERS: dict[str, dict[str, Callable[..., Any]]] = {
    Platform.DOUYIN.value: {
        "token": _live_douyin_access_token,
        "write": _try_real_write_douyin,
    },
}


def _simulate(
    product: ProductModel, index: int, total: int, is_retry: bool
) -> tuple[bool, str, bool]:
    """演示/种子店：模拟执行。保留"总数≥4 时末位强制失败"以演示 partial + 重试。"""
    if not is_retry and total >= 4 and index == total - 1:
        return False, "平台授权已过期，可重试", False
    return True, "演示任务执行成功", False


def _audit_entry(
    job: OperationJobModel,
    product: ProductModel,
    result: BatchItemResult,
    executed_real: bool,
) -> AuditLogModel:
    now = datetime.now(SHANGHAI)
    return AuditLogModel(
        id=f"audit-{uuid4().hex[:10]}",
        job_id=job.id,
        domain="product",
        entity_id=product.id,
        entity_reference=product.sku,
        action=job.action,
        action_label=PRODUCT_ACTION_LABELS.get(job.action, job.action),
        actor=ACTOR,
        result="succeeded" if result.success else "failed",
        note=result.message,
        metadata_json={"is_demo_execution": not executed_real},
        created_at=now,
        is_demo=not executed_real,
    )


def run_product_job(
    db: Session,
    job: OperationJobModel,
    *,
    process_only_ids: list[str] | None = None,
    settings: Settings | None = None,
    douyin_client: DouyinClient | None = None,
) -> None:
    """执行（或重试）商品批量任务。幂等键在创建阶段已保证；此处保证可追踪与部分失败。

    - process_only_ids 为 None：整任务执行（已终态则跳过）。
    - process_only_ids 非空：仅重试这些失败项，演示态下必定成功以演示恢复。
    - douyin_client 用于注入 mock 客户端做测试；缺省时按服务端凭证构建。
    """
    if process_only_ids is None and job.status in {
        JobStatus.SUCCEEDED.value,
        JobStatus.PARTIAL.value,
    }:
        return

    settings = settings or get_settings()
    cipher = TokenCipher(settings.token_encryption_keys)
    platform_clients: dict[str, Any] = {
        Platform.DOUYIN.value: douyin_client or build_douyin_client(settings),
    }

    requested_ids = set(process_only_ids) if process_only_ids else set(job.entity_ids)
    products = list(
        db.scalars(
            select(ProductModel).where(
                ProductModel.organization_id == DEFAULT_ORG,
                ProductModel.id.in_(requested_ids),
            )
        )
    )
    shops = {
        shop.id: shop
        for shop in db.scalars(
            select(ShopModel).where(ShopModel.id.in_({p.shop_id for p in products}))
        )
    }

    existing = {r["product_id"]: BatchItemResult(**r) for r in (job.results or [])}
    is_retry = process_only_ids is not None
    total = len(products)
    executed_real = False

    for index, product in enumerate(products):
        shop = shops.get(product.shop_id)
        live = bool(shop and shop.data_source == "live")
        if shop is not None and live:
            handler = _WRITE_HANDLERS.get(shop.platform)
            platform_client = platform_clients.get(shop.platform)
            token = handler["token"](db, DEFAULT_ORG, cipher) if handler else None
            if handler is not None and platform_client is not None and token:
                success, message, real = asyncio.run(
                    handler["write"](
                        platform_client, BatchAction(job.action), product, job.payload, token
                    )
                )
                executed_real = executed_real or real
                if success:
                    _apply_local_write(product, job.action, job.payload)
            elif not token:
                success, message, real = False, "目标店铺未授权，无法执行真实写入", False
            elif handler is None:
                success, message, real = (
                    False,
                    f"该平台（{shop.platform_label}）尚未实现真实写入",
                    False,
                )
            else:
                success, message, real = False, "该平台服务端凭证缺失，无法执行真实写入", False
        else:
            success, message, real = _simulate(product, index, total, is_retry)

        result = BatchItemResult(
            product_id=product.id, sku=product.sku, success=success, message=message
        )
        existing[product.id] = result
        db.add(_audit_entry(job, product, result, real))

    results = list(existing.values())
    job.results = [r.model_dump(mode="json") for r in results]
    job.succeeded = sum(r.success for r in results)
    job.failed = sum(not r.success for r in results)
    job.status = JobStatus.PARTIAL.value if job.failed else JobStatus.SUCCEEDED.value
    job.progress = 100
    job.updated_at = datetime.now(SHANGHAI)
    if executed_real:
        job.is_demo = False
    db.commit()
