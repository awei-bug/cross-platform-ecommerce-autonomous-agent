from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OperationJobModel(Base):
    __tablename__ = "operation_jobs"
    __table_args__ = (
        UniqueConstraint("kind", "idempotency_key", name="uq_operation_jobs_kind_idempotency"),
        Index("ix_operation_jobs_kind_created_at", "kind", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    entity_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AutomationRuleModel(Base):
    __tablename__ = "automation_rules"
    __table_args__ = (
        UniqueConstraint("organization_id", "rule_type", name="uq_automation_rules_org_type"),
        Index("ix_automation_rules_organization_enabled", "organization_id", "is_enabled"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(48), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AutomationRunModel(Base):
    __tablename__ = "automation_runs"
    __table_args__ = (
        Index("ix_automation_runs_rule_created", "rule_id", "created_at"),
        Index("ix_automation_runs_organization_created", "organization_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AutomationTaskModel(Base):
    __tablename__ = "automation_tasks"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "dedupe_key", name="uq_automation_tasks_org_dedupe"
        ),
        Index("ix_automation_tasks_org_status_created", "organization_id", "status", "created_at"),
        Index("ix_automation_tasks_run_id", "run_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(180), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reference: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    suggested_action: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    assignee: Mapped[str | None] = mapped_column(String(80), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_domain_entity_created", "domain", "entity_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    domain: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    action_label: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(80), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AlertStateModel(Base):
    __tablename__ = "alert_states"

    alert_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ShopModel(Base):
    __tablename__ = "shops"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_label: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    data_source: Mapped[str] = mapped_column(String(32), nullable=False, default="seeded")
    capabilities: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)


class ProductModel(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_organization_shop", "organization_id", "shop_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    platform_item_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_label: Mapped[str] = mapped_column(String(32), nullable=False)
    shop_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_labels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    price: Mapped[float] = mapped_column(nullable=False)
    cost: Mapped[float] = mapped_column(nullable=False)
    stock: Mapped[int] = mapped_column(nullable=False, default=0)
    sales_7d: Mapped[int] = mapped_column(nullable=False, default=0)
    revenue_7d: Mapped[float] = mapped_column(nullable=False, default=0.0)
    conversion_rate: Mapped[float] = mapped_column(nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AlertModel(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    shop_id: Mapped[str] = mapped_column(String(64), nullable=False)
    shop_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkspaceStatsModel(Base):
    __tablename__ = "workspace_stats"

    organization_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    today_sales: Mapped[int] = mapped_column(nullable=False, default=0)
    paid_orders: Mapped[int] = mapped_column(nullable=False, default=0)
    active_alerts: Mapped[int] = mapped_column(nullable=False, default=0)
    pending_tasks: Mapped[int] = mapped_column(nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlatformConnectionModel(Base):
    __tablename__ = "platform_connections"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "platform", name="uq_platform_connections_org_platform"
        ),
        Index("ix_platform_connections_platform_state", "platform", "state"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    app_key_reference: Mapped[str | None] = mapped_column(String(32), nullable=True)
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    platform_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    platform_user_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    platform_shop_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    platform_shop_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OAuthStateModel(Base):
    __tablename__ = "oauth_states"
    __table_args__ = (Index("ix_oauth_states_platform_expires", "platform", "expires_at"),)

    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiConfigurationModel(Base):
    __tablename__ = "ai_configurations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "provider_id", name="uq_ai_configurations_org_provider"
        ),
        Index("ix_ai_configurations_organization_id", "organization_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_tested")
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AiDiscoveredModelModel(Base):
    __tablename__ = "ai_discovered_models"
    __table_args__ = (
        UniqueConstraint(
            "configuration_id", "model_id", name="uq_ai_discovered_models_config_model"
        ),
        Index("ix_ai_discovered_models_configuration_id", "configuration_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    configuration_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # None 表示厂商未返回定价信息，无法判断是否免费。
    is_free: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssetModel(Base):
    __tablename__ = "assets"
    __table_args__ = (
        Index("ix_assets_organization_updated", "organization_id", "updated_at"),
        Index("ix_assets_organization_type", "organization_id", "asset_type"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    current_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssetVersionModel(Base):
    __tablename__ = "asset_versions"
    __table_args__ = (Index("ix_asset_versions_asset_created", "asset_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    preview_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    quality_issues: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GenerationJobModel(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        Index("ix_generation_jobs_organization_created", "organization_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    configuration_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssetQualityCheckModel(Base):
    __tablename__ = "asset_quality_checks"
    __table_args__ = (Index("ix_asset_quality_checks_version_created", "version_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    check_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DistributionJobModel(Base):
    __tablename__ = "distribution_jobs"
    __table_args__ = (
        Index("ix_distribution_jobs_organization_created", "organization_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

