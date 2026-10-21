from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import AuditLogModel, OperationJobModel
from app.schemas.common import Pagination, Platform
from app.schemas.orders import (
    AfterSaleStatus,
    AiReplySuggestion,
    ConversationMessage,
    OrderAction,
    OrderActionItemResult,
    OrderActionJob,
    OrderActionRequest,
    OrderActionStatus,
    OrderAuditEntry,
    OrderDetail,
    OrderLine,
    OrderListItem,
    OrderListResponse,
    OrderRisk,
    OrderStatus,
    OrderSummary,
    OrderTimelineItem,
)
from app.services.shop_scope import parse_shop_scope

SHANGHAI = ZoneInfo("Asia/Shanghai")
DATA_UPDATED_AT = datetime(2026, 9, 12, 13, 10, tzinfo=SHANGHAI)

SHOP_DATA = {
    "taobao": (Platform.TAOBAO, "淘宝", "shop-taobao-001", "柔肤旗舰店"),
    "douyin": (Platform.DOUYIN, "抖店", "shop-douyin-001", "柔肤抖音专营店"),
    "pdd": (Platform.PINDUODUO, "拼多多", "shop-pdd-001", "柔肤品牌馆"),
}

ORDER_ROWS = [
    (
        "DD20260911001",
        "douyin",
        "张**",
        "柔肤保湿面霜",
        "SKU-10028",
        1,
        128.0,
        "shipped",
        "merchant_processing",
        "critical",
        (12, 45),
        128.0,
        ["退款申请已超时", "买家连续催促"],
    ),
    (
        "TB20260912018",
        "taobao",
        "李**",
        "玻尿酸修护精华液",
        "SKU-10031",
        2,
        318.0,
        "pending_shipment",
        "none",
        "critical",
        (13, 42),
        318.0,
        ["发货时效不足 1 小时", "高客单订单"],
    ),
    (
        "PD20260912007",
        "pdd",
        "王**",
        "氨基酸净澈洁面乳",
        "SKU-10042",
        2,
        138.0,
        "shipped",
        "requested",
        "critical",
        (14, 20),
        138.0,
        ["仅退款待处理", "距离平台介入不足 2 小时"],
    ),
    (
        "DD20260912033",
        "douyin",
        "赵**",
        "多肽抗皱精华霜",
        "SKU-10129",
        1,
        199.0,
        "pending_shipment",
        "none",
        "warning",
        (15, 30),
        80.0,
        ["发货时效不足 3 小时"],
    ),
    (
        "TB20260912026",
        "taobao",
        "陈**",
        "洋甘菊舒敏水乳套装",
        "SKU-10169",
        1,
        219.0,
        "shipped",
        "buyer_returning",
        "warning",
        (16, 40),
        109.0,
        ["退货物流 24 小时未更新"],
    ),
    (
        "PD20260912019",
        "pdd",
        "周**",
        "清透防晒乳 SPF50+",
        "SKU-10063",
        3,
        357.0,
        "pending_shipment",
        "none",
        "warning",
        (17, 20),
        120.0,
        ["库存分配等待确认"],
    ),
    (
        "TB20260911088",
        "taobao",
        "孙**",
        "神经酰胺屏障乳",
        "SKU-10084",
        1,
        139.0,
        "shipped",
        "refund_processing",
        "warning",
        (18, 10),
        70.0,
        ["退款到账处理中"],
    ),
    (
        "DD20260912041",
        "douyin",
        "吴**",
        "积雪草舒缓喷雾",
        "SKU-10091",
        2,
        158.0,
        "shipped",
        "requested",
        "warning",
        (18, 50),
        79.0,
        ["商品破损举证待核验"],
    ),
    (
        "PD20260911052",
        "pdd",
        "郑**",
        "茶树控油爽肤水",
        "SKU-10136",
        1,
        89.0,
        "completed",
        "resolved",
        "normal",
        None,
        0.0,
        [],
    ),
    (
        "TB20260912039",
        "taobao",
        "冯**",
        "烟酰胺焕亮身体乳",
        "SKU-10077",
        2,
        158.0,
        "shipped",
        "none",
        "normal",
        None,
        0.0,
        [],
    ),
    (
        "DD20260912058",
        "douyin",
        "褚**",
        "咖啡因紧致颈霜",
        "SKU-10188",
        1,
        169.0,
        "completed",
        "none",
        "normal",
        None,
        0.0,
        [],
    ),
    (
        "PD20260912031",
        "pdd",
        "卫**",
        "舒缓修红面膜 10 片",
        "SKU-10056",
        2,
        198.0,
        "shipped",
        "resolved",
        "normal",
        None,
        0.0,
        [],
    ),
]


def _deadline(value: tuple[int, int] | None) -> datetime | None:
    if value is None:
        return None
    return DATA_UPDATED_AT.replace(hour=value[0], minute=value[1])


def _build_order(row: tuple) -> OrderListItem:
    (
        order_no,
        platform_key,
        buyer,
        title,
        sku,
        quantity,
        amount,
        order_status,
        after_sale_status,
        risk,
        deadline_value,
        estimated_loss,
        reasons,
    ) = row
    platform, platform_label, shop_id, shop_name = SHOP_DATA[platform_key]
    deadline = _deadline(deadline_value)
    remaining = None
    if deadline:
        remaining = int((deadline - DATA_UPDATED_AT).total_seconds() // 60)
    return OrderListItem(
        id=f"order-{order_no.lower()}",
        order_no=order_no,
        platform=platform,
        platform_label=platform_label,
        shop_id=shop_id,
        shop_name=shop_name,
        buyer_masked=buyer,
        item_title=title,
        sku=sku,
        quantity=quantity,
        amount=amount,
        order_status=OrderStatus(order_status),
        after_sale_status=AfterSaleStatus(after_sale_status),
        risk=OrderRisk(risk),
        risk_reasons=reasons,
        sla_deadline=deadline,
        remaining_minutes=remaining,
        estimated_loss=estimated_loss,
        created_at=DATA_UPDATED_AT.replace(day=11, hour=18, minute=20),
        updated_at=DATA_UPDATED_AT,
    )


ORDERS = [_build_order(row) for row in ORDER_ROWS]

ACTION_LABELS = {
    OrderAction.REMIND_SHIP: "催促发货",
    OrderAction.APPROVE_REFUND: "同意退款",
    OrderAction.REJECT_REFUND: "拒绝退款",
    OrderAction.SEND_REPLY: "发送回复",
    OrderAction.MARK_FOLLOW_UP: "标记跟进",
}


def list_orders(
    *,
    shop_id: str,
    platform: Platform,
    q: str,
    order_status: OrderStatus | None,
    after_sale_status: AfterSaleStatus | None,
    risk: OrderRisk | None,
    sla: str,
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
) -> OrderListResponse:
    shop_scope = parse_shop_scope(shop_id)
    scoped = [item for item in ORDERS if shop_scope is None or item.shop_id in shop_scope]
    if platform != Platform.ALL:
        scoped = [item for item in scoped if item.platform == platform]
    if q:
        keyword = q.casefold().strip()
        scoped = [
            item
            for item in scoped
            if keyword in item.order_no.casefold()
            or keyword in item.sku.casefold()
            or keyword in item.item_title.casefold()
            or keyword in item.buyer_masked.casefold()
        ]
    if order_status:
        scoped = [item for item in scoped if item.order_status == order_status]
    if after_sale_status:
        scoped = [item for item in scoped if item.after_sale_status == after_sale_status]
    if risk:
        scoped = [item for item in scoped if item.risk == risk]
    if sla == "overdue":
        scoped = [
            item
            for item in scoped
            if item.remaining_minutes is not None and item.remaining_minutes < 0
        ]
    elif sla == "two_hours":
        scoped = [
            item
            for item in scoped
            if item.remaining_minutes is not None and 0 <= item.remaining_minutes <= 120
        ]
    elif sla == "today":
        scoped = [item for item in scoped if item.sla_deadline is not None]

    summary = OrderSummary(
        total=len(scoped),
        critical=sum(item.risk == OrderRisk.CRITICAL for item in scoped),
        overdue=sum(
            item.remaining_minutes is not None and item.remaining_minutes < 0 for item in scoped
        ),
        due_within_2h=sum(
            item.remaining_minutes is not None and 0 <= item.remaining_minutes <= 120
            for item in scoped
        ),
        pending_after_sale=sum(
            item.after_sale_status
            in {AfterSaleStatus.REQUESTED, AfterSaleStatus.MERCHANT_PROCESSING}
            for item in scoped
        ),
        pending_shipment=sum(item.order_status == OrderStatus.PENDING_SHIPMENT for item in scoped),
        estimated_loss=sum(item.estimated_loss for item in scoped),
    )
    sorters = {
        "updated_at": lambda item: item.updated_at,
        "amount": lambda item: item.amount,
        "estimated_loss": lambda item: item.estimated_loss,
        "sla_deadline": lambda item: item.sla_deadline or datetime.max.replace(tzinfo=SHANGHAI),
        "risk": lambda item: {
            OrderRisk.CRITICAL: 3,
            OrderRisk.WARNING: 2,
            OrderRisk.NORMAL: 1,
        }[item.risk],
    }
    scoped.sort(key=sorters.get(sort_by, sorters["risk"]), reverse=sort_order == "desc")
    start = (page - 1) * page_size
    return OrderListResponse(
        items=scoped[start : start + page_size],
        pagination=Pagination(page=page, page_size=page_size, total=len(scoped)),
        summary=summary,
        data_updated_at=DATA_UPDATED_AT,
    )


def _available_actions(item: OrderListItem) -> list[OrderAction]:
    actions = [OrderAction.SEND_REPLY, OrderAction.MARK_FOLLOW_UP]
    if item.order_status == OrderStatus.PENDING_SHIPMENT:
        actions.insert(0, OrderAction.REMIND_SHIP)
    if item.after_sale_status in {
        AfterSaleStatus.REQUESTED,
        AfterSaleStatus.MERCHANT_PROCESSING,
    }:
        actions = [OrderAction.APPROVE_REFUND, OrderAction.REJECT_REFUND, *actions]
    return actions


def get_order(db: Session, order_id: str) -> OrderDetail | None:
    item = next((order for order in ORDERS if order.id == order_id), None)
    if not item:
        return None
    deadline_text = (
        item.sla_deadline.strftime("%H:%M") if item.sla_deadline else "当前没有待处理 SLA"
    )
    return OrderDetail(
        **item.model_dump(),
        buyer_phone_masked="138****7621",
        shipping_address_masked="浙江省杭州市余杭区 **** 街道 **** 号",
        logistics_company="中通快递" if item.order_status != OrderStatus.PENDING_SHIPMENT else None,
        tracking_no_masked=(
            "ZT********3287" if item.order_status != OrderStatus.PENDING_SHIPMENT else None
        ),
        lines=[
            OrderLine(
                sku=item.sku,
                title=item.item_title,
                quantity=item.quantity,
                unit_price=round(item.amount / item.quantity, 2),
            )
        ],
        timeline=[
            OrderTimelineItem(
                time=item.created_at,
                title="订单支付成功",
                detail="平台订单已同步至运营中枢。",
                state="completed",
            ),
            OrderTimelineItem(
                time=item.updated_at.replace(hour=10, minute=25),
                title="规则巡检完成",
                detail=(item.risk_reasons[0] if item.risk_reasons else "当前未发现高风险异常。"),
                state="warning" if item.risk != OrderRisk.NORMAL else "completed",
            ),
            OrderTimelineItem(
                time=item.sla_deadline or item.updated_at,
                title="平台处理时限",
                detail=f"应在 {deadline_text} 前完成处理，倒计时由服务端口径计算。",
                state="critical" if item.risk == OrderRisk.CRITICAL else "pending",
            ),
        ],
        conversation=[
            ConversationMessage(
                id=f"message-{item.order_no}-1",
                sender=item.buyer_masked,
                sender_type="buyer",
                content="你好，我想确认一下现在的处理进度，麻烦尽快回复。",
                sent_at=item.updated_at.replace(hour=11, minute=36),
            ),
            ConversationMessage(
                id=f"message-{item.order_no}-2",
                sender="柔肤客服",
                sender_type="merchant",
                content="您好，已经收到您的申请，我们正在核验订单与物流信息。",
                sent_at=item.updated_at.replace(hour=11, minute=43),
            ),
        ],
        ai_replies=[
            AiReplySuggestion(
                id="reply-calm",
                tone="安抚说明",
                content=(
                    "您好，您的订单情况我们已经核验，当前正在优先处理。"
                    "我们会在平台时限前给出明确结果，并及时同步进度。"
                ),
                evidence=[f"订单 {item.order_no}", *item.risk_reasons[:1]],
            ),
            AiReplySuggestion(
                id="reply-solution",
                tone="方案优先",
                content=(
                    "您好，给您带来不便非常抱歉。我们已将该订单升级为优先工单，"
                    "会根据平台规则完成处理；如需补充凭证，我们会第一时间联系您。"
                ),
                evidence=[item.platform_label, f"处理时限 {deadline_text}"],
            ),
        ],
        available_actions=_available_actions(item),
        audit_entries=list_audit_entries(db, item.id),
        capability_note="演示环境只创建可追踪任务和审计记录，不会向真实平台写入数据。",
    )


def _to_order_job(model: OperationJobModel) -> OrderActionJob:
    return OrderActionJob(
        id=model.id,
        action=model.action,
        status=model.status,
        progress=model.progress,
        total=model.total,
        succeeded=model.succeeded,
        failed=model.failed,
        created_at=model.created_at,
        updated_at=model.updated_at,
        results=[OrderActionItemResult.model_validate(item) for item in model.results],
        is_demo=model.is_demo,
    )


def _to_audit_entry(model: AuditLogModel) -> OrderAuditEntry:
    return OrderAuditEntry(
        id=model.id,
        order_id=model.entity_id,
        order_no=model.entity_reference,
        action=model.action,
        action_label=model.action_label,
        actor=model.actor,
        result=model.result,
        note=model.note,
        created_at=model.created_at,
        is_demo=model.is_demo,
    )


def create_action_job(db: Session, request: OrderActionRequest) -> OrderActionJob:
    existing = db.scalar(
        select(OperationJobModel).where(
            OperationJobModel.kind == "order",
            OperationJobModel.idempotency_key == request.idempotency_key,
        )
    )
    if existing is not None:
        return _to_order_job(existing)

    selected = [item for item in ORDERS if item.id in request.order_ids]
    now = datetime.now(SHANGHAI)
    model = OperationJobModel(
        id=f"order-job-{uuid4().hex[:10]}",
        kind="order",
        action=request.action.value,
        idempotency_key=request.idempotency_key,
        status=OrderActionStatus.QUEUED.value,
        progress=0,
        total=len(selected),
        succeeded=0,
        failed=0,
        entity_ids=[item.id for item in selected],
        payload=request.payload,
        results=[],
        created_at=now,
        updated_at=now,
        is_demo=True,
    )
    db.add(model)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(OperationJobModel).where(
                OperationJobModel.kind == "order",
                OperationJobModel.idempotency_key == request.idempotency_key,
            )
        )
        if existing is None:
            raise
        return _to_order_job(existing)

    from app.workers.tasks import process_order_action

    try:
        process_order_action.delay(model.id)
    except Exception as exc:
        model.status = OrderActionStatus.FAILED.value
        model.progress = 100
        model.last_error = f"任务分发失败：{exc}"
        model.updated_at = datetime.now(SHANGHAI)
        db.commit()

    db.expire_all()
    refreshed = db.get(OperationJobModel, model.id)
    if refreshed is None:
        raise RuntimeError("订单任务创建后无法读取")
    return _to_order_job(refreshed)


def get_action_job(db: Session, job_id: str) -> OrderActionJob | None:
    model = db.get(OperationJobModel, job_id)
    if model is None or model.kind != "order":
        return None
    return _to_order_job(model)


def execute_action_job(db: Session, job_id: str) -> None:
    model = db.get(OperationJobModel, job_id)
    if model is None or model.kind != "order":
        return
    if model.status in {OrderActionStatus.SUCCEEDED.value, OrderActionStatus.PARTIAL.value}:
        return

    model.status = OrderActionStatus.RUNNING.value
    model.progress = 40
    model.started_at = datetime.now(SHANGHAI)
    model.updated_at = datetime.now(SHANGHAI)
    db.commit()

    requested_ids = set(model.entity_ids)
    selected = [item for item in ORDERS if item.id in requested_ids]
    results: list[OrderActionItemResult] = []
    now = datetime.now(SHANGHAI)
    for index, item in enumerate(selected):
        failed = model.total >= 3 and index == len(selected) - 1
        message = "平台授权状态已变化，请刷新能力后重试" if failed else "演示任务执行成功"
        result = OrderActionItemResult(
            order_id=item.id,
            order_no=item.order_no,
            success=not failed,
            message=message,
        )
        results.append(result)
        db.add(
            AuditLogModel(
                id=f"audit-{uuid4().hex[:10]}",
                job_id=model.id,
                domain="order",
                entity_id=item.id,
                entity_reference=item.order_no,
                action=model.action,
                action_label=ACTION_LABELS[OrderAction(model.action)],
                actor="徐店长",
                result="succeeded" if result.success else "failed",
                note=result.message,
                metadata_json={"is_demo_execution": True},
                created_at=now,
                is_demo=True,
            )
        )

    model.results = [result.model_dump(mode="json") for result in results]
    model.succeeded = sum(result.success for result in results)
    model.failed = sum(not result.success for result in results)
    model.status = (
        OrderActionStatus.PARTIAL.value if model.failed else OrderActionStatus.SUCCEEDED.value
    )
    model.progress = 100
    model.updated_at = now
    db.commit()


def list_audit_entries(db: Session, order_id: str | None = None) -> list[OrderAuditEntry]:
    statement = select(AuditLogModel).where(AuditLogModel.domain == "order")
    if order_id:
        statement = statement.where(AuditLogModel.entity_id == order_id)
    statement = statement.order_by(desc(AuditLogModel.created_at)).limit(100)
    return [_to_audit_entry(model) for model in db.scalars(statement)]
