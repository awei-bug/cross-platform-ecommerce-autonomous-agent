from fastapi import APIRouter, Depends, Query

from app.core.security import require_demo_user
from app.schemas.workspace import SearchResult
from app.services.mock_repository import SEARCH_INDEX

router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(require_demo_user)],
)


@router.get("", response_model=list[SearchResult])
def global_search(q: str = Query(min_length=1, max_length=80)) -> list[SearchResult]:
    keyword = q.strip().lower()
    return [
        item
        for item in SEARCH_INDEX
        if keyword in item.id.lower()
        or keyword in item.title.lower()
        or keyword in item.subtitle.lower()
    ]
