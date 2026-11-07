"""基于云购库存事件的低库存预警。

数据源是 order-events 消费进程写入的 inventory_projections，
每个商品只保留最新一次事件，避免历史扣减把预警洗掉。
"""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.identity import require_session
from app.db.models import InventoryProjectionModel
from app.db.session import get_db

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(require_session)],
)


class InventoryAlert(BaseModel):
    product_id: str
    sku_id: str | None
    item_title: str
    stock_after: int
    delta: int
    organization_id: str
    source: str
    occurred_at: datetime


class InventoryAlertResponse(BaseModel):
    threshold: int
    total_projections: int
    items: list[InventoryAlert]
    is_demo: bool = False


@router.get("/alerts", response_model=InventoryAlertResponse)
def inventory_alerts(
    db: Annotated[Session, Depends(get_db)],
    threshold: Annotated[int, Query(ge=0, le=10000)] = 25,
) -> InventoryAlertResponse:
    rows = list(
        db.scalars(
            select(InventoryProjectionModel).order_by(
                desc(InventoryProjectionModel.event_id)
            )
        )
    )
    seen: set[tuple[str, str]] = set()
    items: list[InventoryAlert] = []
    for row in rows:
        key = (row.product_id, row.sku_id or "")
        if key in seen:
            continue
        seen.add(key)
        if row.stock_after >= threshold:
            continue
        items.append(
            InventoryAlert(
                product_id=row.product_id,
                sku_id=row.sku_id,
                item_title=row.item_title,
                stock_after=row.stock_after,
                delta=row.delta,
                organization_id=row.organization_id,
                source=row.source,
                occurred_at=row.occurred_at,
            )
        )
    return InventoryAlertResponse(
        threshold=threshold,
        total_projections=len(rows),
        items=items,
    )
