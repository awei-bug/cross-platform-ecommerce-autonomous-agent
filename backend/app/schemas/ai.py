from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class AiProviderProtocol(StrEnum):
    OPENAI_COMPATIBLE = "openai-compatible"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    MOCK = "mock"


class AiProviderCatalogItem(BaseModel):
    id: str
    name: str
    protocol: AiProviderProtocol
    description: str
    default_base_url: str
    requires_api_key: bool
    supports_model_discovery: bool
    capabilities: list[str]
    documentation_url: str | None = None


class AiConfigurationCreate(BaseModel):
    provider_id: str = Field(min_length=2, max_length=64)
    display_name: str | None = Field(default=None, max_length=120)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=1000)
    selected_model: str | None = Field(default=None, max_length=200)

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else value


class AiConfigurationPatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=1000)
    selected_model: str | None = Field(default=None, max_length=200)
    is_enabled: bool | None = None

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else value


class AiDiscoveredModel(BaseModel):
    id: str
    model_id: str
    display_name: str
    capabilities: list[str]
    # None 表示厂商未返回定价，前端不应把它当作付费模型隐藏。
    is_free: bool | None = None
    discovered_at: datetime


class AiConfigurationResponse(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    display_name: str
    base_url: str
    api_key_masked: str | None = None
    selected_model: str | None = None
    status: str
    last_tested_at: datetime | None = None
    last_error: str | None = None
    is_enabled: bool
    is_demo: bool
    models: list[AiDiscoveredModel] = []
    created_at: datetime
    updated_at: datetime


class AiConfigurationListResponse(BaseModel):
    items: list[AiConfigurationResponse]
    is_demo: bool


class AiConnectionTestResponse(BaseModel):
    status: str
    message: str
    configuration: AiConfigurationResponse
    models: list[AiDiscoveredModel]


class AiModelProbeResponse(BaseModel):
    status: str
    model_id: str
    message: str
    preview: str | None = None
    latency_ms: int | None = None
    is_demo: bool


class AssetType(StrEnum):
    COPY = "copy"
    IMAGE = "image"
    VIDEO_SCRIPT = "video_script"
    VIDEO = "video"
    TEMPLATE = "template"


class AssetStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"


class AssetVersionResponse(BaseModel):
    id: str
    version_number: int
    source: str
    content: str
    preview_url: str | None = None
    object_key: str | None = None
    content_type: str | None = None
    file_size: int | None = None
    quality_status: str
    quality_issues: list[str]
    created_at: datetime


class AssetResponse(BaseModel):
    id: str
    product_id: str | None
    title: str
    asset_type: AssetType
    status: AssetStatus
    current_version_id: str | None
    tags: list[str]
    versions: list[AssetVersionResponse]
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class AssetListResponse(BaseModel):
    items: list[AssetResponse]
    total: int
    is_demo: bool


class AssetCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    asset_type: AssetType
    product_id: str | None = Field(default=None, max_length=64)
    content: str = Field(min_length=1, max_length=20000)
    tags: list[str] = []


class GenerationJobCreate(BaseModel):
    asset_id: str | None = None
    asset_type: AssetType
    prompt: str = Field(min_length=3, max_length=4000)
    configuration_id: str | None = None
    model_id: str | None = None


class GenerationJobResponse(BaseModel):
    id: str
    asset_id: str | None
    asset_type: AssetType
    prompt: str
    model_id: str
    status: str
    progress: int
    result_version_id: str | None
    error_message: str | None
    is_demo: bool
    created_at: datetime
    updated_at: datetime

