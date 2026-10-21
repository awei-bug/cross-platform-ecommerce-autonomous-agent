from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "运营中枢 API"
    app_version: str = "0.2.0"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # 本地默认使用可持久化 SQLite，生产环境通过 DATABASE_URL 切换 PostgreSQL。
    database_url: str = "sqlite+pysqlite:///./data/ops_workbench.db"
    database_echo: bool = False
    database_auto_create: bool = True

    # 单进程 eager 任务执行：无需 RabbitMQ/Redis，适合本项目的实际负载。
    # 保留 Celery 以承载 product/order/asset 任务，但默认在 API 进程内同步执行。
    celery_broker_url: str = "memory://"
    celery_result_backend: str = "cache+memory://"
    celery_task_always_eager: bool = True
    celery_task_eager_propagates: bool = True

    # 抖店开放平台（op.jinritemai.com）。Token 由 OAuth 获取后加密保存。
    douyin_app_key: str | None = None
    douyin_app_secret: str | None = None
    douyin_redirect_uri: str | None = None
    douyin_auth_base_url: str = "https://openweb.douyin.com/platform/oauth/connect"
    douyin_token_base_url: str = "https://openapi-fxg.jinritemai.com"
    douyin_api_base_url: str = "https://openapi-fxg.jinritemai.com"
    douyin_http_timeout_seconds: float = 10.0
    douyin_http_max_attempts: int = 3

    # 淘宝客公开商品数据源（阿里妈妈 / 淘宝开放平台）。
    # 个人实名可申请，无需卖家店铺授权；凭证与推广位 PID 在阿里妈妈后台获取。
    taobaoke_app_key: str | None = None
    taobaoke_app_secret: str | None = None
    taobaoke_adzone_id: str | None = None
    taobaoke_api_base_url: str = "https://eco.taobao.com/router/rest"
    taobaoke_http_timeout_seconds: float = 10.0
    taobaoke_http_max_attempts: int = 2

    # 抖音开放平台内容投稿（open.douyin.com，「投稿到抖音」能力）。
    # 个人可注册申请；审核通过后配置应用凭证，用户授权后代替用户发布内容。
    douyin_content_client_key: str | None = None
    douyin_content_client_secret: str | None = None
    douyin_content_redirect_uri: str | None = None
    douyin_content_api_base_url: str = "https://open.douyin.com"
    douyin_content_timeout_seconds: float = 15.0

    # 商品记忆库（data-hub）只读连接。本项目是**只读消费者**：
    # 不在本地复制知识字段，避免出现第二份真相。未配置时所有调用降级为空，
    # 不影响既有商品、订单与抖店链路。
    data_hub_url: str | None = None
    data_hub_token: str | None = None
    data_hub_tenant_slug: str | None = None
    data_hub_timeout_seconds: float = 10.0
    data_hub_http_max_attempts: int = 2

    # 逗号分隔的 Fernet 密钥；首个密钥用于加密，其余密钥仅用于解密旧数据。
    token_encryption_keys: str | None = None
    oauth_state_ttl_seconds: int = 600

    # 真实模型生成默认关闭，避免开发环境误调用并产生费用；启用前请确认 Key、预算和数据合规。
    ai_live_generation_enabled: bool = False

    # 素材文件存储：开发默认落本地，生产可切换到 MinIO（见 infra/compose.yaml 注释）。
    asset_storage_backend: str = "local"
    minio_endpoint: str = "http://127.0.0.1:9000"
    minio_access_key: str = "ops_admin"
    minio_secret_key: str = "ops_dev_password"
    minio_bucket: str = "ops-assets"
    minio_region: str = "us-east-1"
    asset_storage_local_path: str = "./data/assets"
    asset_preview_expiry_seconds: int = 900
    asset_upload_max_bytes: int = 25 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
