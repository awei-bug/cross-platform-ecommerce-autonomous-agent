"""Browser observations are evidence, never inferred sales or demand scores."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.schemas.ecomops import StrictModel


class RankingEvidence(StrictModel):
    source_url: str = Field(max_length=2000)
    category: str = Field(min_length=1, max_length=200)
    rank: int = Field(ge=1, le=100000)
    collected_at: AwareDatetime
    evidence_file: str = Field(min_length=1, max_length=500)
    evidence_sha256: str = Field(pattern="^[a-f0-9]{64}$")

    @field_validator("source_url")
    @classmethod
    def public_url(cls, value: str) -> str:
        return Observation.public_url(value)


class Observation(StrictModel):
    source_url: str = Field(max_length=2000)
    title: str = Field(min_length=1, max_length=500)
    price: float | None = Field(default=None, gt=0, le=1e8, strict=True)
    currency: str | None = Field(default=None, pattern="^[A-Z]{3}$")
    collected_at: AwareDatetime
    specifications: dict[str, str] = Field(default_factory=dict, max_length=30)
    description: str = Field(default="", max_length=5000)
    price_evidence: str = Field(default="", max_length=500)
    evidence_file: str = Field(min_length=1, max_length=500)
    evidence_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    missing_fields: list[str] = Field(default_factory=list, max_length=30)
    capture_method: Literal["browser_schema_org", "browser_amazon_dom"] = "browser_schema_org"
    ranking: RankingEvidence | None = None
    popularity_claim: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def price_has_evidence(self):
        if self.price is not None and (not self.currency or not self.price_evidence.strip()):
            raise ValueError("有价格时必须同时提供币种与页面价格证据")
        return self

    @field_validator("source_url")
    @classmethod
    def public_url(cls, value: str) -> str:
        import ipaddress

        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
            raise ValueError("来源必须为无凭证的公开 HTTP(S) URL")
        if host == "localhost" or host.endswith((".localhost", ".local")) or "." not in host:
            raise ValueError("来源必须为公开商品页面")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return value
        if not address.is_global:
            raise ValueError("来源不得为私有地址")
        return value

    @field_validator("specifications")
    @classmethod
    def bounded_specs(cls, value: dict[str, str]) -> dict[str, str]:
        if any(len(k) > 100 or len(v) > 1000 for k, v in value.items()):
            raise ValueError("规格字段过长")
        return value


class ResearchBatch(StrictModel):
    collection_id: str = Field(min_length=3, max_length=80, pattern="^[a-zA-Z0-9_-]+$")
    country: str = Field(pattern="^[A-Z]{2}$")
    category: str = Field(min_length=1, max_length=200)
    observations: list[Observation] = Field(min_length=1, max_length=50)


class ResearchAnalysis(StrictModel):
    collection_id: str = Field(min_length=3, max_length=80, pattern="^[a-zA-Z0-9_-]+$")
    country: str = Field(default="US", pattern="^[A-Z]{2}$")
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    commission_pct: float = Field(default=15, ge=0, lt=100)
    ad_rate_pct: float = Field(default=10, ge=0, lt=100)
    target_margin_pct: float = Field(default=15, ge=0, lt=100)
