"""Persist browser evidence in the data platform read by selection workflows."""

from hashlib import sha256
from statistics import median
from urllib.parse import urlsplit

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.ecomops import OpsRecord
from app.schemas.ecomops import ImportRequest, RecordInput
from app.schemas.research import Observation, ResearchAnalysis, ResearchBatch


def import_research(db: Session, org: str, actor: str, batch: ResearchBatch) -> dict:
    from app.services.ecomops_service import import_records

    records = []
    for item in batch.observations:
        identity = f"{batch.collection_id}\n{batch.country}\n{item.source_url}"
        records.append(
            RecordInput(
                kind="competitor",
                key="web-" + sha256(identity.encode()).hexdigest(),
                source="browser_public:" + batch.collection_id,
                is_demo=False,
                data={
                    **item.model_dump(mode="json"),
                    "collection_id": batch.collection_id,
                    "country": batch.country,
                    "category": batch.category,
                    "verification": "page_observation_not_independent_verification",
                    "sales": None,
                    "review_pain_points": None,
                },
            )
        )
    return {
        **import_records(db, org, actor, ImportRequest(records=records)),
        "collection_id": batch.collection_id,
    }


def collection_records(db: Session, org: str, collection_id: str, country: str) -> list[OpsRecord]:
    # Use the existing tenant-scoped table; JSON payloads work on SQLite and PostgreSQL.
    rows = db.scalars(
        select(OpsRecord).where(OpsRecord.organization_id == org, OpsRecord.kind == "competitor")
    )
    return [
        r
        for r in rows
        if r.payload.get("collection_id") == collection_id
        and r.payload.get("country") == country
        and not r.is_demo
    ]


def list_collections(db: Session, org: str) -> list[dict]:
    rows = db.scalars(
        select(OpsRecord)
        .where(OpsRecord.organization_id == org, OpsRecord.kind == "competitor")
        .order_by(OpsRecord.updated_at.desc())
    )
    result = {}
    for row in rows:
        data = row.payload
        if row.is_demo or not data.get("collection_id") or not data.get("country"):
            continue
        key = (data["collection_id"], data["country"])
        if key not in result:
            result[key] = {
                "collection_id": key[0],
                "country": key[1],
                "category": data.get("category", ""),
                "count": 0,
            }
        result[key]["count"] += 1
    return list(result.values())


def analyze_research(db: Session, org: str, request: ResearchAnalysis) -> dict:
    rows = collection_records(db, org, request.collection_id, request.country)
    usable, excluded = [], []
    for row in rows:
        try:
            # Generic record imports cannot smuggle incomplete/invalid evidence into this analysis.
            fields = {k: v for k, v in row.payload.items() if k in Observation.model_fields}
            observation = Observation.model_validate(fields)
            valid = observation.price is not None and observation.currency == request.currency
        except ValidationError:
            valid = False
        if valid:
            usable.append(row)
        else:
            excluded.append({"key": row.key, "reason": "缺少有效价格/证据或币种不匹配"})
    ratio = 1 - (request.commission_pct + request.ad_rate_pct + request.target_margin_pct) / 100
    prices = [r.payload["price"] for r in usable]
    return {
        "collection_id": request.collection_id,
        "country": request.country,
        "currency": request.currency,
        "sample_count": len(usable),
        "source_count": len({urlsplit(r.payload["source_url"]).hostname for r in usable}),
        "ranked_sample_count": sum(bool(r.payload.get("ranking")) for r in usable),
        "observed_prices": {
            "min": min(prices) if prices else None,
            "median": median(prices) if prices else None,
            "max": max(prices) if prices else None,
        },
        "assumptions": request.model_dump(),
        "candidates": [
            {
                "key": r.key,
                **r.payload,
                "max_fixed_cost_at_target_margin": round(r.payload["price"] * ratio, 4)
                if ratio > 0
                else None,
            }
            for r in usable
        ],
        "excluded": excluded,
        "cost_formula": "全部非比例单件成本上限 = 样本售价×(1-佣金率-广告率-目标毛利率)",
        "limitations": [
            "样本价格分布，不代表市场均价；尺寸、材质、套装数量与促销需人工对齐",
            "价格可能随地区、会员、税费、配送和时间变化；库存未验证",
            "缺少真实销量、搜索趋势与供应商报价，不能证明需求或预测盈利",
            "榜单位置仅代表该站点该品类采集时的排名；购买量声明为平台展示口径，非精确销量",
            "费率及目标毛利为分析假设，成本上限不是采购报价或建议售价",
            "成本上限须覆盖采购、全程物流、税费、平台履约、包装、仓储与售后损耗；尚未取得这些报价",
        ]
        + (["费率与目标毛利合计不低于100%，无正成本空间"] if ratio <= 0 else []),
    }
