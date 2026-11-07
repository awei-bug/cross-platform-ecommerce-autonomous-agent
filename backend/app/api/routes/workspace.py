from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.identity import require_session
from app.db.models import AlertModel, ShopModel, WorkspaceStatsModel
from app.db.session import get_db
from app.schemas.auth import UserProfile
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

router = APIRouter(prefix="/workspace", tags=["workspace"])

# 组织边界来自已验证会话；这里不再保存任何演示组织常量。
ORGANIZATION_NAME = "柔肤电商事业部"

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _shops_from_db(db: Session, organization_id: str) -> list[Shop]:
    rows = db.scalars(
        select(ShopModel).where(ShopModel.organization_id == organization_id)
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


def _alerts_from_db(db: Session, organization_id: str) -> list[AlertItem]:
    rows = db.scalars(
        select(AlertModel).where(AlertModel.organization_id == organization_id)
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


def _summary_from_db(db: Session, organization_id: str) -> WorkspaceSummary:
    stats = db.get(WorkspaceStatsModel, organization_id)
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
def bootstrap(
    user: Annotated[UserProfile, Depends(require_session)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceBootstrap:
    organization_id = user.organization_id
    return WorkspaceBootstrap(
        organization=Organization(id=organization_id, name=ORGANIZATION_NAME),
        shops=_shops_from_db(db, organization_id),
        context=WorkspaceContext(
            organization_id=organization_id,
            shop_id="shop-all",
            platform=Platform.ALL,
        ),
        summary=_summary_from_db(db, organization_id),
    )


@router.get("/alerts", response_model=list[AlertItem])
def list_alerts(
    user: Annotated[UserProfile, Depends(require_session)],
    db: Annotated[Session, Depends(get_db)],
    unread_only: bool = Query(default=False),
) -> list[AlertItem]:
    return list_alerts_with_state(
        db, _alerts_from_db(db, user.organization_id), unread_only=unread_only
    )


@router.patch("/alerts/{alert_id}", response_model=AlertItem)
def update_alert_state(
    alert_id: str,
    request: AlertReadStateUpdate,
    user: Annotated[UserProfile, Depends(require_session)],
    db: Annotated[Session, Depends(get_db)],
) -> AlertItem:
    alert = next(
        (item for item in _alerts_from_db(db, user.organization_id) if item.id == alert_id),
        None,
    )
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="告警不存在")
    is_read = set_alert_read_state(db, alert_id, is_read=request.is_read)
    return alert.model_copy(update={"is_read": is_read})


@router.post("/alerts/read-all", response_model=AlertReadAllResult)
def read_all_alerts(
    user: Annotated[UserProfile, Depends(require_session)],
    db: Annotated[Session, Depends(get_db)],
) -> AlertReadAllResult:
    return AlertReadAllResult(
        changed=set_all_alerts_read(db, _alerts_from_db(db, user.organization_id))
    )


@router.get("/capabilities", response_model=list[PlatformCapability])
def list_capabilities(
    user: Annotated[UserProfile, Depends(require_session)],
    db: Annotated[Session, Depends(get_db)],
    shop_id: str = Query(...),
) -> list[PlatformCapability]:
    shop = db.get(ShopModel, shop_id)
    if (
        shop is None
        or shop.capabilities is None
        or shop.organization_id != user.organization_id
    ):
        return []
    return [PlatformCapability(**cap) for cap in shop.capabilities]
