from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.security import require_demo_user
from app.schemas.campaigns import AdOverview, CampaignStatus
from app.schemas.common import Platform
from app.services.campaign_repository import get_ad_overview

router = APIRouter(
    prefix="/campaigns",
    tags=["campaigns"],
    dependencies=[Depends(require_demo_user)],
)


@router.get("", response_model=AdOverview)
def campaigns(
    shop_id: Annotated[str, Query()] = "shop-all",
    platform: Annotated[Platform, Query()] = Platform.ALL,
    account_id: Annotated[str, Query(max_length=100)] = "",
    campaign_status: Annotated[CampaignStatus | None, Query(alias="status")] = None,
    q: Annotated[str, Query(max_length=100)] = "",
) -> AdOverview:
    return get_ad_overview(
        shop_id=shop_id,
        platform=platform,
        account_id=account_id,
        status=campaign_status,
        q=q,
    )
