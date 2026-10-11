from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_demo_user
from app.db.session import get_db
from app.schemas.dashboard import DashboardOverview
from app.services.dashboard_repository import get_dashboard_overview

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_demo_user)],
)


@router.get("/overview", response_model=DashboardOverview)
def overview(
    shop_id: str = Query(default="shop-all"),
    db: Annotated[Session, Depends(get_db)] = None,
) -> DashboardOverview:
    return get_dashboard_overview(db, shop_id)
