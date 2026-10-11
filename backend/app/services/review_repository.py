from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.schemas.common import Platform
from app.schemas.reviews import (
    ReviewItem,
    ReviewOverview,
    ReviewProduct,
    ReviewRating,
    ReviewSummary,
    ReviewTemplate,
    ReviewTicket,
    ReviewTicketAction,
    ReviewTicketStatus,
    SentimentWord,
)
from app.services.shop_scope import parse_shop_scope

SHANGHAI = ZoneInfo("Asia/Shanghai")
DATA_UPDATED_AT = datetime(2026, 9, 13, 9, 20, tzinfo=SHANGHAI)

PRODUCTS = [
    ReviewProduct(
        id="review-product-tb-001",
        title="氨基酸温和洁面乳 120g",
        sku="RF-FACE-120",
        shop_id="shop-taobao-001",
        shop_name="柔肤旗舰店",
        platform=Platform.TAOBAO,
        platform_label="淘宝",
        review_count=1286,
        negative_count=19,
    ),
    ReviewProduct(
        id="review-product-dy-001",
        title="玻尿酸补水面霜 50g",
        sku="RF-CREAM-050",
        shop_id="shop-douyin-001",
        shop_name="柔肤抖店旗舰店",
        platform=Platform.DOUYIN,
        platform_label="抖店",
        review_count=864,
        negative_count=23,
    ),
    ReviewProduct(
        id="review-product-pdd-001",
        title="敏感肌水乳套装",
        sku="RF-SET-002",
        shop_id="shop-pdd-001",
        shop_name="柔肤拼多多专营店",
        platform=Platform.PINDUODUO,
        platform_label="拼多多",
        review_count=642,
        negative_count=31,
    ),
]

REVIEWS = [
    ReviewItem(
        id="review-001",
        product_id="review-product-pdd-001",
        product_title="敏感肌水乳套装",
        sku="RF-SET-002",
        platform=Platform.PINDUODUO,
        platform_label="拼多多",
        shop_id="shop-pdd-001",
        shop_name="柔肤拼多多专营店",
        rating=2,
        rating_label=ReviewRating.NEGATIVE,
        content="包装有点破损，外盒压扁了，发货速度倒是挺快，希望加强打包。",
        images=["外盒破损"],
        buyer_nickname="小***海",
        created_at=DATA_UPDATED_AT - timedelta(hours=2),
        keywords=["破损", "发货快"],
        ticket_id="ticket-001",
        ticket_status=ReviewTicketStatus.OPEN,
    ),
    ReviewItem(
        id="review-002",
        product_id="review-product-dy-001",
        product_title="玻尿酸补水面霜 50g",
        sku="RF-CREAM-050",
        platform=Platform.DOUYIN,
        platform_label="抖店",
        shop_id="shop-douyin-001",
        shop_name="柔肤抖店旗舰店",
        rating=1,
        rating_label=ReviewRating.NEGATIVE,
        content="用了两天就觉得刺痛，和直播间说的敏感肌适用不太一样。",
        images=[],
        buyer_nickname="阿***呀",
        created_at=DATA_UPDATED_AT - timedelta(hours=5),
        keywords=["刺痛", "敏感肌"],
        ticket_id="ticket-002",
        ticket_status=ReviewTicketStatus.IN_PROGRESS,
    ),
    ReviewItem(
        id="review-003",
        product_id="review-product-tb-001",
        product_title="氨基酸温和洁面乳 120g",
        sku="RF-FACE-120",
        platform=Platform.TAOBAO,
        platform_label="淘宝",
        shop_id="shop-taobao-001",
        shop_name="柔肤旗舰店",
        rating=3,
        rating_label=ReviewRating.NEUTRAL,
        content="泡沫比较细，但感觉洗完有一点干，物流包装正常。",
        images=[],
        buyer_nickname="木***子",
        created_at=DATA_UPDATED_AT - timedelta(days=1, hours=1),
        keywords=["偏干", "泡沫细"],
        ticket_id=None,
        ticket_status=None,
    ),
    ReviewItem(
        id="review-004",
        product_id="review-product-tb-001",
        product_title="氨基酸温和洁面乳 120g",
        sku="RF-FACE-120",
        platform=Platform.TAOBAO,
        platform_label="淘宝",
        shop_id="shop-taobao-001",
        shop_name="柔肤旗舰店",
        rating=5,
        rating_label=ReviewRating.POSITIVE,
        content="洗得很干净又不紧绷，已经回购第二支了，客服回复也很快。",
        images=["使用反馈"],
        buyer_nickname="晴***天",
        created_at=DATA_UPDATED_AT - timedelta(days=1, hours=3),
        keywords=["不紧绷", "回购"],
        ticket_id=None,
        ticket_status=None,
    ),
    ReviewItem(
        id="review-005",
        product_id="review-product-dy-001",
        product_title="玻尿酸补水面霜 50g",
        sku="RF-CREAM-050",
        platform=Platform.DOUYIN,
        platform_label="抖店",
        shop_id="shop-douyin-001",
        shop_name="柔肤抖店旗舰店",
        rating=4,
        rating_label=ReviewRating.POSITIVE,
        content="保湿效果不错，质地清爽，送的小样也很喜欢。",
        images=[],
        buyer_nickname="星***落",
        created_at=DATA_UPDATED_AT - timedelta(days=2),
        keywords=["保湿", "清爽"],
        ticket_id=None,
        ticket_status=None,
    ),
    ReviewItem(
        id="review-006",
        product_id="review-product-pdd-001",
        product_title="敏感肌水乳套装",
        sku="RF-SET-002",
        platform=Platform.PINDUODUO,
        platform_label="拼多多",
        shop_id="shop-pdd-001",
        shop_name="柔肤拼多多专营店",
        rating=1,
        rating_label=ReviewRating.NEGATIVE,
        content="收到货后发现漏液，客服已经联系我处理了，希望后续能改善密封。",
        images=["漏液照片"],
        buyer_nickname="柚***茶",
        created_at=DATA_UPDATED_AT - timedelta(days=2, hours=4),
        keywords=["漏液", "密封"],
        ticket_id="ticket-003",
        ticket_status=ReviewTicketStatus.RESOLVED,
    ),
]

TICKETS = [
    ReviewTicket(
        id="ticket-001",
        review_id="review-001",
        product_title="敏感肌水乳套装",
        shop_name="柔肤拼多多专营店",
        title="包装破损差评跟进",
        status=ReviewTicketStatus.OPEN,
        assignee="运营待分配",
        reply_draft="您好，很抱歉这次收到的包裹外盒有破损。我们已记录并会加强仓库打包，若商品有受损请联系在线客服，我们会优先为您处理。",
        follow_up_note="待确认商品本体是否受损",
        updated_at=DATA_UPDATED_AT - timedelta(hours=2),
    ),
    ReviewTicket(
        id="ticket-002",
        review_id="review-002",
        product_title="玻尿酸补水面霜 50g",
        shop_name="柔肤抖店旗舰店",
        title="敏感不适差评跟进",
        status=ReviewTicketStatus.IN_PROGRESS,
        assignee="林小满",
        reply_draft="您好，给您带来不适我们非常抱歉。请先暂停使用并联系在线客服，我们会根据您的情况协助处理，同时核查批次与适用说明。",
        follow_up_note="已转客服，等待买家反馈",
        updated_at=DATA_UPDATED_AT - timedelta(hours=4),
    ),
    ReviewTicket(
        id="ticket-003",
        review_id="review-006",
        product_title="敏感肌水乳套装",
        shop_name="柔肤拼多多专营店",
        title="漏液差评跟进",
        status=ReviewTicketStatus.RESOLVED,
        assignee="周子涵",
        reply_draft="您好，真的很抱歉给您添麻烦了，已为您安排补发并反馈仓库加强密封检查。",
        follow_up_note="已补发，买家确认收货",
        updated_at=DATA_UPDATED_AT - timedelta(days=1),
    ),
]

WORDS = [
    SentimentWord(word="发货快", count=82, sentiment=ReviewRating.POSITIVE),
    SentimentWord(word="保湿", count=71, sentiment=ReviewRating.POSITIVE),
    SentimentWord(word="不紧绷", count=54, sentiment=ReviewRating.POSITIVE),
    SentimentWord(word="破损", count=19, sentiment=ReviewRating.NEGATIVE),
    SentimentWord(word="发货慢", count=14, sentiment=ReviewRating.NEGATIVE),
    SentimentWord(word="刺痛", count=11, sentiment=ReviewRating.NEGATIVE),
    SentimentWord(word="漏液", count=9, sentiment=ReviewRating.NEGATIVE),
    SentimentWord(word="偏干", count=27, sentiment=ReviewRating.NEUTRAL),
]

TEMPLATES = [
    ReviewTemplate(
        id="template-thanks",
        name="好评感谢",
        scenario="好评",
        content="感谢您的认可和回购，我们会继续把产品和服务做好，期待下次再见。",
        tone="真诚",
    ),
    ReviewTemplate(
        id="template-package",
        name="包装破损安抚",
        scenario="物流/包装",
        content="您好，很抱歉包裹在运输中出现破损。我们已记录问题并会加强打包，如商品有受损请联系我们优先处理。",
        tone="安抚",
    ),
    ReviewTemplate(
        id="template-sensitive",
        name="敏感不适关怀",
        scenario="使用不适",
        content="您好，给您带来不适我们非常抱歉，建议先暂停使用并联系我们，我们会根据实际情况协助处理。",
        tone="关怀",
    ),
]


def _scoped_reviews(
    shop_id: str,
    platform: Platform,
    product_id: str,
    rating: ReviewRating | None,
    q: str,
    ticket_status: ReviewTicketStatus | None,
) -> list[ReviewItem]:
    scope = parse_shop_scope(shop_id)
    keyword = q.strip().lower()
    return [
        item
        for item in REVIEWS
        if (scope is None or item.shop_id in scope)
        and (platform == Platform.ALL or item.platform == platform)
        and (not product_id or item.product_id == product_id)
        and (rating is None or item.rating_label == rating)
        and (
            not keyword
            or keyword in item.content.lower()
            or keyword in item.product_title.lower()
            or keyword in item.buyer_nickname.lower()
            or any(keyword in word.lower() for word in item.keywords)
        )
        and (ticket_status is None or item.ticket_status == ticket_status)
    ]


def get_review_overview(
    shop_id: str,
    platform: Platform = Platform.ALL,
    product_id: str = "",
    rating: ReviewRating | None = None,
    q: str = "",
    ticket_status: ReviewTicketStatus | None = None,
) -> ReviewOverview:
    reviews = _scoped_reviews(shop_id, platform, product_id, rating, q, ticket_status)
    scope = parse_shop_scope(shop_id)
    products = [
        item
        for item in PRODUCTS
        if (scope is None or item.shop_id in scope)
        and (platform == Platform.ALL or item.platform == platform)
    ]
    review_ids = {item.id for item in reviews}
    tickets = [item for item in TICKETS if item.review_id in review_ids]
    summary = ReviewSummary(
        total=len(reviews),
        positive=sum(item.rating_label == ReviewRating.POSITIVE for item in reviews),
        neutral=sum(item.rating_label == ReviewRating.NEUTRAL for item in reviews),
        negative=sum(item.rating_label == ReviewRating.NEGATIVE for item in reviews),
        open_tickets=sum(
            item.status in {ReviewTicketStatus.OPEN, ReviewTicketStatus.IN_PROGRESS}
            for item in tickets
        ),
        monitored_products=len(products),
    )
    return ReviewOverview(
        products=products,
        reviews=reviews,
        tickets=tickets,
        words=WORDS,
        templates=TEMPLATES,
        summary=summary,
        data_updated_at=DATA_UPDATED_AT,
    )


def update_review_ticket(action: ReviewTicketAction) -> ReviewTicket:
    ticket = next((item for item in TICKETS if item.review_id == action.review_id), None)
    review = next((item for item in REVIEWS if item.id == action.review_id), None)
    if review is None:
        raise ValueError("评价不存在")
    if ticket is None:
        ticket = ReviewTicket(
            id=f"ticket-{action.review_id}",
            review_id=review.id,
            product_title=review.product_title,
            shop_name=review.shop_name,
            title=f"{review.product_title}差评跟进",
            status=action.status,
            assignee=action.assignee,
            reply_draft=action.reply_draft,
            follow_up_note=action.follow_up_note,
            updated_at=DATA_UPDATED_AT,
        )
        TICKETS.append(ticket)
    else:
        ticket.status = action.status
        ticket.assignee = action.assignee
        ticket.reply_draft = action.reply_draft
        ticket.follow_up_note = action.follow_up_note
        ticket.updated_at = DATA_UPDATED_AT
    review.ticket_id = ticket.id
    review.ticket_status = ticket.status
    return ticket
