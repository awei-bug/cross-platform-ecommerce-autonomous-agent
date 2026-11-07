"""消费云购领域事件，落本地 order_projections 读模型。

设计约束：
- 只处理已激活租户映射的事件，无映射直接丢弃，不隐式放行。
- event_id 唯一约束做幂等，水位与投影写入处于同一事务。
- 三个配置项缺任一项就不启用，避免空配置静默连到未知端点。

可直接运行：python -m app.services.order_event_consumer --once
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import (
    EventWatermarkModel,
    InventoryProjectionModel,
    MerchantOrganizationMappingModel,
    OrderProjectionModel,
)
from app.db.session import session_scope
from app.schemas.common import Platform
from app.schemas.orders import (
    AfterSaleStatus,
    OrderListItem,
    OrderRisk,
    OrderStatus,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
CONSUMER_NAME = "order_projection"


def events_configured(settings: Settings) -> bool:
    """fail-closed：开关、地址、令牌必须同时给出。"""
    if not settings.events_enabled or not settings.events_url or not settings.events_token:
        return False
    parsed = urlsplit(settings.events_url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _parse_occurred_at(raw: object) -> datetime:
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=SHANGHAI)
            return parsed
        except ValueError:
            pass
    return datetime.now(SHANGHAI)


def _fetch_events(settings: Settings, after: int, limit: int) -> dict:
    url = f"{settings.events_url.rstrip('/')}?after={after}&limit={limit}"
    request = Request(url, headers={"X-Events-Token": settings.events_token or ""})
    with urlopen(request, timeout=settings.events_http_timeout_seconds) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        raise RuntimeError("事件端点返回结构异常")
    return body["data"]


def _organization_for(db: Session, tenant_id: int) -> str | None:
    mapping = db.scalar(
        select(MerchantOrganizationMappingModel).where(
            MerchantOrganizationMappingModel.tenant_id == tenant_id,
            MerchantOrganizationMappingModel.is_active.is_(True),
        )
    )
    return mapping.organization_id if mapping else None


def _build_item(event: dict, organization_id: str) -> dict:
    raw = event.get("payload") or "{}"
    payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    order_no = str(payload.get("order_no") or event.get("aggregate_id") or "")
    occurred = _parse_occurred_at(event.get("occurred_at"))
    item = OrderListItem(
        id=f"order-{order_no.lower()}",
        order_no=order_no,
        platform=Platform.YUNGOU,
        platform_label="云购商城",
        shop_id=organization_id,
        shop_name="云购自有商城",
        buyer_masked="云购买家",
        item_title=str(payload.get("item_title") or "云购订单"),
        sku=str(payload.get("sku") or "-"),
        quantity=int(payload.get("number") or 1),
        amount=float(payload.get("price") or 0.0),
        order_status=OrderStatus.PENDING_SHIPMENT,
        after_sale_status=AfterSaleStatus.NONE,
        risk=OrderRisk.NORMAL,
        risk_reasons=[],
        sla_deadline=None,
        remaining_minutes=None,
        estimated_loss=0.0,
        created_at=occurred,
        updated_at=occurred,
    )
    return item.model_dump(mode="json")


def _already_consumed(db: Session, event_id: int, kind: str) -> bool:
    model = OrderProjectionModel if kind == "order.created" else InventoryProjectionModel
    return db.scalar(select(model).where(model.event_id == event_id)) is not None


def _build_inventory(event: dict, organization_id: str) -> InventoryProjectionModel:
    raw = event.get("payload") or "{}"
    payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    event_id = int(event["id"])
    sku_id = payload.get("sku_id")
    return InventoryProjectionModel(
        id=f"stock-{event_id}",
        event_id=event_id,
        organization_id=organization_id,
        product_id=str(payload.get("product_id") or event.get("aggregate_id") or ""),
        sku_id=str(sku_id) if sku_id else None,
        item_title=str(payload.get("item_title") or ""),
        stock_after=int(payload.get("stock_after") or 0),
        delta=int(payload.get("delta") or 0),
        source="event",
        occurred_at=_parse_occurred_at(event.get("occurred_at")),
        created_at=datetime.now(SHANGHAI),
    )


def consume_once(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    if not events_configured(settings):
        return {"enabled": False, "fetched": 0, "inserted": 0,
                "inventory_inserted": 0, "skipped": 0}

    with session_scope() as db:
        watermark = db.get(EventWatermarkModel, CONSUMER_NAME)
        if watermark is None:
            watermark = EventWatermarkModel(
                consumer=CONSUMER_NAME,
                last_event_id=0,
                updated_at=datetime.now(SHANGHAI),
            )
            db.add(watermark)

        data = _fetch_events(settings, watermark.last_event_id, settings.events_batch_size)
        events = data.get("events") or []
        inserted = 0
        inventory_inserted = 0
        skipped = 0
        max_id = watermark.last_event_id

        for event in events:
            event_id = int(event["id"])
            max_id = max(max_id, event_id)
            kind = event.get("event_type")
            if kind not in {"order.created", "stock.changed"}:
                skipped += 1
                continue
            if _already_consumed(db, event_id, kind):
                skipped += 1
                continue

            organization_id = _organization_for(db, int(event["tenant_id"]))
            if organization_id is None:
                skipped += 1
                continue

            if kind == "order.created":
                item = _build_item(event, organization_id)
                now = datetime.now(SHANGHAI)
                db.add(
                    OrderProjectionModel(
                        id=item["id"],
                        event_id=event_id,
                        organization_id=organization_id,
                        order_no=item["order_no"],
                        source="event",
                        is_demo=False,
                        payload=item,
                        created_at=now,
                        updated_at=now,
                    )
                )
                inserted += 1
            else:
                db.add(_build_inventory(event, organization_id))
                inventory_inserted += 1

        watermark.last_event_id = max_id
        watermark.updated_at = datetime.now(SHANGHAI)

    return {
        "enabled": True,
        "fetched": len(events),
        "inserted": inserted,
        "inventory_inserted": inventory_inserted,
        "skipped": skipped,
        "watermark": max_id,
    }


def run_forever(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    interval = max(settings.events_poll_interval_seconds, 1.0)
    while True:
        try:
            result = consume_once(settings)
            if result.get("inserted"):
                print(
                    f"[order-events] 已投影 {result['inserted']} 条，水位 {result['watermark']}",
                    flush=True,
                )
        except Exception as exc:  # 单轮失败不终止进程，水位未推进下轮自动重投
            print(f"[order-events] 消费失败，下轮重试: {exc}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="云购订单事件消费器")
    parser.add_argument("--once", action="store_true", help="只消费一轮后退出")
    args = parser.parse_args()
    if args.once:
        print(json.dumps(consume_once(), ensure_ascii=False), flush=True)
    else:
        run_forever()
