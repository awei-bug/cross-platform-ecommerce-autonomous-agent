from fastapi import APIRouter, Depends, Query

from app.core.security import require_demo_user
from app.schemas.workspace import AlertItem, PlatformCapability, WorkspaceBootstrap
from app.services.mock_repository import ALERTS, CAPABILITIES, WORKSPACE_BOOTSTRAP

router = APIRouter(
    prefix="/workspace",
    tags=["workspace"],
    dependencies=[Depends(require_demo_user)],
)


@router.get("/bootstrap", response_model=WorkspaceBootstrap)
def bootstrap() -> WorkspaceBootstrap:
    return WORKSPACE_BOOTSTRAP


@router.get("/alerts", response_model=list[AlertItem])
def list_alerts(unread_only: bool = Query(default=False)) -> list[AlertItem]:
    if unread_only:
        return [item for item in ALERTS if not item.is_read]
    return ALERTS


@router.get("/capabilities", response_model=list[PlatformCapability])
def list_capabilities(shop_id: str = Query(...)) -> list[PlatformCapability]:
    return CAPABILITIES.get(shop_id, [])
