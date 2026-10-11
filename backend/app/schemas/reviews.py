from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from app.schemas.common import Platform


class ReviewRating(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class ReviewTicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class ReviewProduct(BaseModel):
    id: str
    title: str
    sku: str
    shop_id: str
    shop_name: str
    platform: Platform
    platform_label: str
    monitored: bool = True
    review_count: int
    negative_count: int


class ReviewItem(BaseModel):
    id: str
    product_id: str
    product_title: str
    sku: str
    platform: Platform
    platform_label: str
    shop_id: str
    shop_name: str
    rating: int
    rating_label: ReviewRating
    content: str
    images: list[str]
    buyer_nickname: str
    created_at: datetime
    keywords: list[str]
    ticket_id: str | None = None
    ticket_status: ReviewTicketStatus | None = None


class ReviewTicket(BaseModel):
    id: str
    review_id: str
    product_title: str
    shop_name: str
    title: str
    status: ReviewTicketStatus
    assignee: str
    reply_draft: str
    follow_up_note: str
    updated_at: datetime
    is_demo: bool = True


class SentimentWord(BaseModel):
    word: str
    count: int
    sentiment: ReviewRating


class ReviewTemplate(BaseModel):
    id: str
    name: str
    scenario: str
    content: str
    tone: str


class ReviewSummary(BaseModel):
    total: int
    positive: int
    neutral: int
    negative: int
    open_tickets: int
    monitored_products: int


class ReviewOverview(BaseModel):
    products: list[ReviewProduct]
    reviews: list[ReviewItem]
    tickets: list[ReviewTicket]
    words: list[SentimentWord]
    templates: list[ReviewTemplate]
    summary: ReviewSummary
    data_updated_at: datetime
    is_demo: bool = True


class ReviewTicketAction(BaseModel):
    review_id: str
    assignee: str = "运营待分配"
    status: ReviewTicketStatus = ReviewTicketStatus.OPEN
    reply_draft: str = ""
    follow_up_note: str = ""
