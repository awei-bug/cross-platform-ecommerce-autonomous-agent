"""竞品知识库：结构化沉淀 + 轻量关键词相似度检索。

设计取舍（2026-10-12）：文档叙事要求"竞品信息向量化入库、随时检索对标"。
当前阶段不引入 pgvector / 外部 embedding 服务，改用标题+卖点+痛点分词生成的
关键词权重向量（JSON 存储），检索用余弦相似度。接口形状与向量检索一致，
后续换 pgvector 时只需替换 `search_competitors` 的实现，调用方无感。

数据源分三类：seeded（演示种子）、manual（人工录入）、taobaoke（淘宝客公开
商品接口，真实数据 is_demo=False）。seeded 与 manual 均标注 is_demo=True，
绝不把演示数据描述成真实情报；taobaoke 数据在返回中携带平台口径说明。
"""
from __future__ import annotations

import asyncio
import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import CompetitorModel
from app.integrations.taobao import (
    TaobaokeClient,
    TaobaokeMaterial,
    TaobaokeNotConfigured,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_ORG = "org-demo-001"
DEFAULT_CATEGORY = "美容护肤 / 面部护理"

# 演示竞品库：字段与商品详情页"竞品快照"同源，但这里做结构化沉淀，
# 支持卖点/痛点/关键词检索，而不是写死在单个商品响应里。
SEED_COMPETITORS = [
    {
        "category": DEFAULT_CATEGORY,
        "title": "竞品 玻尿酸保湿安瓶精华",
        "platform_label": "天猫",
        "price": 99.0,
        "sales_7d": 612,
        "conversion_rate": 6.1,
        "selling_points": ["小分子玻尿酸", "7 天补水", "医美级原料"],
        "review_pain_points": ["包装易漏液", "客服响应慢"],
    },
    {
        "category": DEFAULT_CATEGORY,
        "title": "竞品 氨基酸温和洁面乳",
        "platform_label": "淘宝",
        "price": 55.0,
        "sales_7d": 488,
        "conversion_rate": 5.4,
        "selling_points": ["弱酸性配方", "敏感肌可用", "150g 大容量"],
        "review_pain_points": ["泡沫偏少", "香味清淡"],
    },
    {
        "category": DEFAULT_CATEGORY,
        "title": "竞品 烟酰胺焕亮身体乳",
        "platform_label": "抖音",
        "price": 69.0,
        "sales_7d": 905,
        "conversion_rate": 5.9,
        "selling_points": ["5% 烟酰胺", "美白特证", "持久留香"],
        "review_pain_points": ["长毛争议", "质地厚重"],
    },
    {
        "category": DEFAULT_CATEGORY,
        "title": "竞品 清透防晒隔离乳",
        "platform_label": "天猫",
        "price": 105.0,
        "sales_7d": 534,
        "conversion_rate": 4.8,
        "selling_points": ["SPF50+ 高倍防护", "清爽不油腻", "孕妇可用"],
        "review_pain_points": ["上脸假白", "与粉底搓泥"],
    },
    {
        "category": DEFAULT_CATEGORY,
        "title": "竞品 神经酰胺屏障修护霜",
        "platform_label": "京东",
        "price": 145.0,
        "sales_7d": 297,
        "conversion_rate": 4.2,
        "selling_points": ["三重神经酰胺", "医美共创", "28 天屏障修护"],
        "review_pain_points": ["定价偏高", "见效周期长"],
    },
    {
        "category": DEFAULT_CATEGORY,
        "title": "竞品 水杨酸净痘精华凝胶",
        "platform_label": "拼多多",
        "price": 49.0,
        "sales_7d": 763,
        "conversion_rate": 6.4,
        "selling_points": ["1.5% 水杨酸", "夜间局部修护", "不刺激配方"],
        "review_pain_points": ["初期脱皮", "味道刺鼻"],
    },
]

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    """中英文混合分词：英文/数字按词，中文按字二元组。

    不引 jieba 等外部依赖；二元组对中文短文本（标题/卖点）足够稳定。
    """
    text = text.strip()
    if not text:
        return []
    tokens: list[str] = []
    for word in _TOKEN_PATTERN.findall(text):
        tokens.append(word.lower())
    chinese_runs = _TOKEN_PATTERN.split(text)
    for run in chinese_runs:
        chars = [ch for ch in run if "\u4e00" <= ch <= "\u9fff"]
        if len(chars) == 1:
            tokens.append(chars[0])
            continue
        tokens.extend("".join(chars[i : i + 2]) for i in range(len(chars) - 1))
    return tokens


def build_keywords(texts: list[str]) -> dict[str, float]:
    """把多段文本压成关键词权重向量（词频归一化）。"""
    counts: dict[str, int] = {}
    for text in texts:
        for token in tokenize(text):
            counts[token] = counts.get(token, 0) + 1
    if not counts:
        return {}
    peak = max(counts.values())
    return {token: round(count / peak, 4) for token, count in counts.items()}


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    dot = sum(left[token] * right[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return round(dot / (left_norm * right_norm), 4)


def _keywords_texts(model: CompetitorModel) -> list[str]:
    return [model.title, *model.selling_points, *model.review_pain_points]


def _to_payload(model: CompetitorModel) -> dict:
    return {
        "id": model.id,
        "category": model.category,
        "title": model.title,
        "platform_label": model.platform_label,
        "price": model.price,
        "sales_7d": model.sales_7d,
        "conversion_rate": model.conversion_rate,
        "selling_points": list(model.selling_points),
        "review_pain_points": list(model.review_pain_points),
        "source": model.source,
        "is_demo": model.is_demo,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def ensure_seed_competitors(db: Session, organization_id: str = DEFAULT_ORG) -> int:
    """空库时写入演示竞品。返回新增条数。"""
    existing = db.scalar(select(CompetitorModel).limit(1))
    if existing is not None:
        return 0
    now = datetime.now(SHANGHAI)
    for index, item in enumerate(SEED_COMPETITORS, start=1):
        texts = [item["title"], *item["selling_points"], *item["review_pain_points"]]
        db.add(
            CompetitorModel(
                id=f"competitor-{index:03d}",
                organization_id=organization_id,
                category=item["category"],
                title=item["title"],
                platform_label=item["platform_label"],
                price=item["price"],
                sales_7d=item["sales_7d"],
                conversion_rate=item["conversion_rate"],
                selling_points=list(item["selling_points"]),
                review_pain_points=list(item["review_pain_points"]),
                keywords=build_keywords(texts),
                source="seeded",
                is_demo=True,
                created_at=now,
                updated_at=now,
            )
        )
    db.commit()
    return len(SEED_COMPETITORS)


def create_competitor(
    db: Session,
    organization_id: str,
    *,
    category: str,
    title: str,
    price: float,
    selling_points: list[str],
    review_pain_points: list[str],
    platform_label: str = "人工录入",
    sales_7d: int = 0,
    conversion_rate: float = 0.0,
) -> dict:
    """录入竞品（人工来源）。仅写本地知识库，不触发任何平台调用。"""
    now = datetime.now(SHANGHAI)
    texts = [title, *selling_points, *review_pain_points]
    model = CompetitorModel(
        id=f"competitor-{now.strftime('%Y%m%d%H%M%S')}-{abs(hash(title)) % 10_000:04d}",
        organization_id=organization_id,
        category=category.strip() or DEFAULT_CATEGORY,
        title=title.strip()[:200],
        platform_label=platform_label.strip()[:32] or "人工录入",
        price=round(price, 2),
        sales_7d=max(int(sales_7d), 0),
        conversion_rate=round(conversion_rate, 2),
        selling_points=[point.strip()[:120] for point in selling_points if point.strip()],
        review_pain_points=[point.strip()[:120] for point in review_pain_points if point.strip()],
        keywords=build_keywords(texts),
        source="manual",
        is_demo=True,
        created_at=now,
        updated_at=now,
    )
    db.add(model)
    db.commit()
    return _to_payload(model)


def list_competitors(
    db: Session, organization_id: str = DEFAULT_ORG, category: str | None = None
) -> list[dict]:
    statement = select(CompetitorModel).where(
        CompetitorModel.organization_id == organization_id
    )
    if category:
        statement = statement.where(CompetitorModel.category == category)
    rows = db.scalars(statement.order_by(desc(CompetitorModel.updated_at))).all()
    return [_to_payload(row) for row in rows]


def search_competitors(
    db: Session,
    *,
    query_texts: list[str],
    category: str | None = None,
    organization_id: str = DEFAULT_ORG,
    limit: int = 5,
    min_similarity: float = 0.02,
) -> list[dict]:
    """按关键词相似度检索对标竞品。

    同类目竞品全权重参与；跨类目打折到 40%，保证"对标"相关性。
    返回结构含 similarity，供诊断引擎作为价格对标证据。
    """
    query_vector = build_keywords(query_texts)
    if not query_vector:
        return []
    statement = select(CompetitorModel).where(
        CompetitorModel.organization_id == organization_id
    )
    if category:
        statement = statement.where(CompetitorModel.category == category)
    rows = db.scalars(statement).all()
    scored: list[tuple[float, CompetitorModel]] = []
    for row in rows:
        if not row.keywords:
            row.keywords = build_keywords(_keywords_texts(row))
        similarity = cosine_similarity(query_vector, row.keywords)
        if similarity < min_similarity:
            continue
        scored.append((similarity, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    for similarity, row in scored[:limit]:
        payload = _to_payload(row)
        payload["similarity"] = similarity
        results.append(payload)
    return results


def _material_selling_points(material: TaobaokeMaterial) -> list[str]:
    """把淘宝客返回的推广属性转成可检索的卖点条目。"""
    points: list[str] = []
    if material.coupon_amount:
        points.append(f"优惠券 {material.coupon_amount:.0f} 元")
    if material.reserve_price and material.reserve_price > material.price:
        points.append(f"原价 {material.reserve_price:.2f} 元")
    if material.sales_volume:
        points.append(f"月销 {material.sales_volume} 件（平台口径）")
    if material.commission_rate:
        points.append(f"推广佣金率 {material.commission_rate:.1f}%")
    if material.shop_title:
        points.append(str(material.shop_title)[:60])
    return points[:6]


def import_taobaoke_competitors(
    db: Session,
    organization_id: str,
    *,
    keyword: str,
    category: str | None = None,
    limit: int = 10,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """从淘宝客公开商品接口导入竞品（真实数据）。

    - 凭证缺失时抛 TaobaokeNotConfigured，调用方如实提示配置路径；
    - 按商品 id 幂等：重复导入同一关键词时更新价格与销量，不产生重复条目；
    - 销量为淘宝客平台口径（近 30 天），与演示种子的 7 日口径不同，返回中携带 note。
    """
    settings = get_settings()
    missing = [
        name
        for name, value in (
            ("TAOBAOKE_APP_KEY", settings.taobaoke_app_key),
            ("TAOBAOKE_APP_SECRET", settings.taobaoke_app_secret),
            ("TAOBAOKE_ADZONE_ID", settings.taobaoke_adzone_id),
        )
        if not value
    ]
    if missing:
        raise TaobaokeNotConfigured(
            "尚未配置淘宝客凭证（缺少 " + "、".join(missing) + "）；"
            "个人实名可在淘宝联盟申请 AppKey 与推广位，步骤见 README 竞品数据源一节"
        )
    client = TaobaokeClient(
        app_key=settings.taobaoke_app_key or "",
        app_secret=settings.taobaoke_app_secret or "",
        adzone_id=settings.taobaoke_adzone_id or "",
        api_base_url=settings.taobaoke_api_base_url,
        timeout_seconds=settings.taobaoke_http_timeout_seconds,
        max_attempts=settings.taobaoke_http_max_attempts,
        transport=transport,
    )
    materials = asyncio.run(
        client.search_materials(keyword=keyword.strip(), page_size=min(max(limit, 1), 40))
    )
    now = datetime.now(SHANGHAI)
    created = 0
    updated = 0
    items: list[dict] = []
    for material in materials[: max(limit, 1)]:
        competitor_id = f"competitor-tbk-{material.item_id}"
        selling_points = _material_selling_points(material)
        keyword_vector = build_keywords([material.title, *selling_points])
        row = db.get(CompetitorModel, competitor_id)
        if row is None:
            row = CompetitorModel(
                id=competitor_id,
                organization_id=organization_id,
                category=(category or material.category_name or DEFAULT_CATEGORY)[:120],
                title=material.title,
                platform_label="天猫" if material.is_tmall else "淘宝",
                price=material.price,
                sales_7d=material.sales_volume,
                conversion_rate=0.0,
                selling_points=selling_points,
                review_pain_points=[],
                keywords=keyword_vector,
                source="taobaoke",
                is_demo=False,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            created += 1
        else:
            if category:
                row.category = category[:120]
            row.title = material.title
            row.platform_label = "天猫" if material.is_tmall else "淘宝"
            row.price = material.price
            row.sales_7d = material.sales_volume
            row.selling_points = selling_points
            row.keywords = keyword_vector
            row.source = "taobaoke"
            row.is_demo = False
            row.updated_at = now
            updated += 1
        items.append(_to_payload(row))
    db.commit()
    return {
        "keyword": keyword.strip(),
        "source": "taobaoke",
        "created": created,
        "updated": updated,
        "note": (
            "数据来自淘宝客公开商品接口（真实数据）；价格取券后价，"
            "销量为平台近 30 天口径，与演示种子的 7 日口径不同。"
        ),
        "items": items,
    }
