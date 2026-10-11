from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import require_demo_user
from app.schemas.common import Platform
from app.schemas.reviews import (
    ReviewOverview,
    ReviewRating,
    ReviewTicket,
    ReviewTicketAction,
    ReviewTicketStatus,
)
from app.services.review_repository import get_review_overview, update_review_ticket

router = APIRouter(prefix="/reviews", tags=["reviews"], dependencies=[Depends(require_demo_user)])


@router.get("", response_model=ReviewOverview)
def reviews(
    shop_id: Annotated[str, Query()] = "shop-all",
    platform: Annotated[Platform, Query()] = Platform.ALL,
    product_id: Annotated[str, Query(max_length=100)] = "",
    rating: Annotated[ReviewRating | None, Query()] = None,
    q: Annotated[str, Query(max_length=100)] = "",
    ticket_status: Annotated[ReviewTicketStatus | None, Query()] = None,
) -> ReviewOverview:
    return get_review_overview(shop_id, platform, product_id, rating, q, ticket_status)


@router.post("/tickets", response_model=ReviewTicket)
def review_ticket(action: ReviewTicketAction) -> ReviewTicket:
    try:
        return update_review_ticket(action)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
