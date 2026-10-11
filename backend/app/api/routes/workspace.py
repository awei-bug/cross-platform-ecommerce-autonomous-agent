from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_demo_user
from app.db.models import AlertModel, ShopModel, WorkspaceStatsModel
from app.db.session import get_db
from app.schemas.common import Platform
from app.schemas.workspace import (
    AlertItem,
    AlertReadAllResult,
    AlertReadStateUpdate,
    Organization,
    PlatformCapability,
    Shop,
    WorkspaceBootstrap,
    WorkspaceContext,
    WorkspaceSummary,
)
from app.services.alert_repository import (
    list_alerts_with_state,
    set_alert_read_state,
    set_all_alerts_read,
)

router = APIRouter(
    prefix="/workspace",
    tags=["workspace"],
    dependencies=[Depends(require_demo_user)],
)

ORGANIZATION_ID = "org-demo-001"
ORGANIZATION_NAME = "柔肤电商事业部"

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _shops_from_db(db: Session) -> list[Shop]:
    rows = db.scalars(
        select(ShopModel).where(ShopModel.organization_id == ORGANIZATION_ID)
    ).all()
    return [
        Shop(
            id=row.id,
            name=row.name,
            platform=Platform(row.platform),
            platform_label=row.platform_label,
            status=row.status,
            last_synced_at=row.last_synced_at,
            data_source=row.data_source,
        )
        for row in rows
    ]


def _alerts_from_db(db: Session) -> list[AlertItem]:
    rows = db.scalars(
        select(AlertModel).where(AlertModel.organization_id == ORGANIZATION_ID)
    ).all()
    return [
        AlertItem(
            id=row.id,
            title=row.title,
            description=row.description,
            severity=row.severity,
            shop_id=row.shop_id,
            shop_name=row.shop_name,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _summary_from_db(db: Session) -> WorkspaceSummary:
    stats = db.get(WorkspaceStatsModel, ORGANIZATION_ID)
    if stats is None:
        return WorkspaceSummary(
            today_sales=0,
            paid_orders=0,
            active_alerts=0,
            pending_tasks=0,
            updated_at=datetime.now(SHANGHAI),
        )
    return WorkspaceSummary(
        today_sales=stats.today_sales,
        paid_orders=stats.paid_orders,
        active_alerts=stats.active_alerts,
        pending_tasks=stats.pending_tasks,
        updated_at=stats.updated_at,
    )


@router.get("/bootstrap", response_model=WorkspaceBootstrap)
def bootstrap(db: Annotated[Session, Depends(get_db)]) -> WorkspaceBootstrap:
    return WorkspaceBootstrap(
        organization=Organization(id=ORGANIZATION_ID, name=ORGANIZATION_NAME),
        shops=_shops_from_db(db),
        context=WorkspaceContext(
            organization_id=ORGANIZATION_ID,
            shop_id="shop-all",
            platform=Platform.ALL,
        ),
        summary=_summary_from_db(db),
    )


@router.get("/alerts", response_model=list[AlertItem])
def list_alerts(
    db: Annotated[Session, Depends(get_db)],
    unread_only: bool = Query(default=False),
) -> list[AlertItem]:
    return list_alerts_with_state(db, _alerts_from_db(db), unread_only=unread_only)


@router.patch("/alerts/{alert_id}", response_model=AlertItem)
def update_alert_state(
    alert_id: str,
    request: AlertReadStateUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> AlertItem:
    alert = next(
        (item for item in _alerts_from_db(db) if item.id == alert_id), None
    )
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="告警不存在")
    is_read = set_alert_read_state(db, alert_id, is_read=request.is_read)
    return alert.model_copy(update={"is_read": is_read})


@router.post("/alerts/read-all", response_model=AlertReadAllResult)
def read_all_alerts(db: Annotated[Session, Depends(get_db)]) -> AlertReadAllResult:
    return AlertReadAllResult(changed=set_all_alerts_read(db, _alerts_from_db(db)))


@router.get("/capabilities", response_model=list[PlatformCapability])
def list_capabilities(
    db: Annotated[Session, Depends(get_db)], shop_id: str = Query(...)
) -> list[PlatformCapability]:
    shop = db.get(ShopModel, shop_id)
    if shop is None or shop.capabilities is None:
        return []
    return [PlatformCapability(**cap) for cap in shop.capabilities]
