from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import OperationJobModel, ProductModel, ShopModel
from app.schemas.common import Pagination, Platform
from app.schemas.products import (
    AiSuggestion,
    BatchActionRequest,
    BatchItemResult,
    BatchJob,
    CompetitorSnapshot,
    JobStatus,
    ProductDetail,
    ProductListItem,
    ProductListResponse,
    ProductRisk,
    ProductSpec,
    ProductStatus,
    ProductSummary,
)
from app.services.shop_scope import parse_shop_scope

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_ORG = "org-demo-001"
DATA_UPDATED_AT = datetime(2026, 9, 12, 9, 40, tzinfo=SHANGHAI)


def _shops_are_live(db: Session, shop_ids: set[str]) -> bool:
    if not shop_ids:
        return False
    live = db.scalars(
        select(ShopModel).where(
            ShopModel.id.in_(shop_ids), ShopModel.data_source == "live"
        )
    ).all()
    return {shop.id for shop in live} == shop_ids


def _to_list_item(p: ProductModel) -> ProductListItem:
    return ProductListItem(
        id=p.id,
        sku=p.sku,
        title=p.title,
        platform=Platform(p.platform),
        platform_label=p.platform_label,
        shop_id=p.shop_id,
        shop_name=p.shop_name,
        status=ProductStatus(p.status),
        risk=ProductRisk(p.risk),
        risk_labels=p.risk_labels,
        price=p.price,
        cost=p.cost,
        stock=p.stock,
        sales_7d=p.sales_7d,
        revenue_7d=p.revenue_7d,
        conversion_rate=p.conversion_rate,
        updated_at=p.updated_at,
    )


def list_products(
    db: Session,
    *,
    shop_id: str,
    platform: Platform,
    q: str,
    status: ProductStatus | None,
    risk: ProductRisk | None,
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
    organization_id: str = DEFAULT_ORG,
) -> ProductListResponse:
    stmt = select(ProductModel).where(ProductModel.organization_id == organization_id)
    shop_scope = parse_shop_scope(shop_id)
    if shop_scope is not None:
        stmt = stmt.where(ProductModel.shop_id.in_(shop_scope))
    if platform != Platform.ALL:
        stmt = stmt.where(ProductModel.platform == platform.value)
    if q:
        keyword = q.casefold().strip()
        stmt = stmt.where(
            (ProductModel.sku.casefold().contains(keyword))
            | (ProductModel.title.casefold().contains(keyword))
        )
    if status:
        stmt = stmt.where(ProductModel.status == status.value)
    if risk:
        stmt = stmt.where(ProductModel.risk == risk.value)

    rows = list(db.scalars(stmt))

    summary = ProductSummary(
        total=len(rows),
        critical=sum(item.risk == ProductRisk.CRITICAL.value for item in rows),
        warning=sum(item.risk == ProductRisk.WARNING.value for item in rows),
        offline=sum(item.status == ProductStatus.OFFLINE.value for item in rows),
        low_stock=sum(item.stock < 25 for item in rows),
    )
    sorters = {
        "updated_at": lambda item: item.updated_at,
        "sales_7d": lambda item: item.sales_7d,
        "revenue_7d": lambda item: item.revenue_7d,
        "stock": lambda item: item.stock,
        "price": lambda item: item.price,
        "conversion_rate": lambda item: item.conversion_rate,
        "risk": lambda item: {
            ProductRisk.CRITICAL.value: 3,
            ProductRisk.WARNING.value: 2,
            ProductRisk.NORMAL.value: 1,
        }[item.risk],
    }
    rows.sort(key=sorters.get(sort_by, sorters["risk"]), reverse=sort_order == "desc")
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]

    shop_ids = {item.shop_id for item in rows}
    is_demo = not _shops_are_live(db, shop_ids)

    return ProductListResponse(
        items=[_to_list_item(item) for item in page_rows],
        pagination=Pagination(page=page, page_size=page_size, total=len(rows)),
        summary=summary,
        data_updated_at=DATA_UPDATED_AT,
        is_demo=is_demo,
    )


def get_product(db: Session, product_id: str) -> ProductDetail | None:
    product = db.get(ProductModel, product_id)
    if product is None:
        return None
    is_demo = not _shops_are_live(db, {product.shop_id})
    return ProductDetail(
        **_to_list_item(product).model_dump(),
        category="美容护肤 / 面部护理",
        barcode=f"697{product.sku.removeprefix('SKU-')}8821",
        specs=[
            ProductSpec(label="规格", value="50g / 标准装"),
            ProductSpec(label="发货时效", value="承诺 48 小时内"),
            ProductSpec(
                label="毛利率",
                value=f"{(product.price - product.cost) / product.price:.1%}",
            ),
            ProductSpec(label="安全库存", value="25 件"),
        ],
        competitors=[
            CompetitorSnapshot(
                name="竞品 A",
                price=round(product.price * 0.94, 2),
                sales_7d=product.sales_7d + 46,
                difference="价格低 6%",
            ),
            CompetitorSnapshot(
                name="竞品 B",
                price=round(product.price * 1.08, 2),
                sales_7d=max(product.sales_7d - 31, 0),
                difference="销量低 12%",
            ),
        ],
        ai_suggestions=[
            AiSuggestion(
                title="先处理库存与投放联动",
                detail=f"当前库存 {product.stock} 件，建议根据近 7 日销量调整投放上限。",
                impact="降低缺货损失风险",
                action="生成补货任务",
            ),
            AiSuggestion(
                title="优化主图利益点",
                detail="将核心功效与适用肤质前置，并保留平台合规词。",
                impact="预计改善点击到详情转化",
                action="前往素材 AI",
            ),
        ],
        capability_note="种子演示店仅创建可审计任务，不会向平台写入数据。",
        is_demo=is_demo,
    )


def _to_batch_job(model: OperationJobModel) -> BatchJob:
    return BatchJob(
        id=model.id,
        action=model.action,
        status=model.status,
        progress=model.progress,
        total=model.total,
        succeeded=model.succeeded,
        failed=model.failed,
        created_at=model.created_at,
        updated_at=model.updated_at,
        results=[BatchItemResult.model_validate(item) for item in model.results],
        is_demo=model.is_demo,
    )


def create_batch_job(db: Session, request: BatchActionRequest) -> BatchJob:
    existing = db.scalar(
        select(OperationJobModel).where(
            OperationJobModel.kind == "product",
            OperationJobModel.idempotency_key == request.idempotency_key,
        )
    )
    if existing is not None:
        return _to_batch_job(existing)

    selected = list(
        db.scalars(
            select(ProductModel).where(
                ProductModel.organization_id == DEFAULT_ORG,
                ProductModel.id.in_(request.product_ids),
            )
        )
    )
    now = datetime.now(SHANGHAI)
    is_demo = not _shops_are_live(db, {item.shop_id for item in selected})
    model = OperationJobModel(
        id=f"job-{uuid4().hex[:10]}",
        kind="product",
        action=request.action.value,
        idempotency_key=request.idempotency_key,
        status=JobStatus.QUEUED.value,
        progress=0,
        total=len(selected),
        succeeded=0,
        failed=0,
        entity_ids=[item.id for item in selected],
        payload=request.payload,
        results=[],
        created_at=now,
        updated_at=now,
        is_demo=is_demo,
    )
    db.add(model)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(OperationJobModel).where(
                OperationJobModel.kind == "product",
                OperationJobModel.idempotency_key == request.idempotency_key,
            )
        )
        if existing is None:
            raise
        return _to_batch_job(existing)

    from app.workers.tasks import process_product_batch

    try:
        process_product_batch.delay(model.id)
    except Exception as exc:
        model.status = JobStatus.FAILED.value
        model.progress = 100
        model.last_error = f"任务分发失败：{exc}"
        model.updated_at = datetime.now(SHANGHAI)
        db.commit()

    db.expire_all()
    refreshed = db.get(OperationJobModel, model.id)
    if refreshed is None:
        raise RuntimeError("商品任务创建后无法读取")
    return _to_batch_job(refreshed)


def get_batch_job(db: Session, job_id: str) -> BatchJob | None:
    model = db.get(OperationJobModel, job_id)
    if model is None or model.kind != "product":
        return None
    return _to_batch_job(model)


def execute_batch_job(db: Session, job_id: str) -> None:
    model = db.get(OperationJobModel, job_id)
    if model is None or model.kind != "product":
        return
    if model.status in {JobStatus.SUCCEEDED.value, JobStatus.PARTIAL.value}:
        return

    model.status = JobStatus.RUNNING.value
    model.progress = 45
    model.updated_at = datetime.now(SHANGHAI)
    db.commit()

    from app.services.platform_write import run_product_job

    run_product_job(db, model)


def retry_batch_job(db: Session, job_id: str) -> BatchJob | None:
    model = db.get(OperationJobModel, job_id)
    if model is None or model.kind != "product":
        return None
    failed_ids = [
        result["product_id"] for result in model.results if not result.get("success")
    ]
    if not failed_ids:
        return _to_batch_job(model)

    from app.services.platform_write import run_product_job

    run_product_job(db, model, process_only_ids=failed_ids)
    db.expire_all()
    refreshed = db.get(OperationJobModel, job_id)
    if refreshed is None:
        raise RuntimeError("商品重试任务执行后无法读取")
    return _to_batch_job(refreshed)
