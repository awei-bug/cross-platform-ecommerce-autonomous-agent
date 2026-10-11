# 后端

FastAPI 模块化单体。当前已经接入 SQLAlchemy、Alembic 和 Celery：商品/订单操作任务、订单审计与告警已读状态可持久化；真实平台数据与写操作仍需开放平台凭证。

## 快速开发模式

默认使用 `backend/data/ops_workbench.db`（SQLite）和 Celery eager 模式，不依赖 Docker：

```powershell
uv sync --dev
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

本模式用于本地开发，任务仍通过正式 Celery task 入口执行，但会在 API 进程内立即完成。

## PostgreSQL 模式

1. 从项目根目录复制配置并启动基础设施：

```powershell
Copy-Item .env.example .env
Copy-Item .env.example backend/.env
docker compose --env-file .env -f infra/compose.yaml up -d postgres
```

2. 初始化数据库：

```powershell
uv run alembic upgrade head
```

3. 启动 API（任务在 API 进程内以 `eager` 模式同步执行，无需独立 Worker）：

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 运维检查

```powershell
uv run alembic current
uv run alembic check
uv run ruff check .
uv run pytest
```

- 存活检查：`GET /health`
- 就绪检查：`GET /ready`，会验证数据库连接并返回任务执行模式。

演示令牌由登录接口签发；除登录、存活和就绪检查外，当前接口均要求 `Bearer demo-access-token`。生产模式烟囱验收可运行 `uv run python scripts/production_smoke.py --base-url http://127.0.0.1:8001`。


## AI 模型配置与素材生成

模型配置和素材 AI 接口均由后端代理，前端不会直接请求厂商：

```text
GET  /api/v1/ai/providers
GET  /api/v1/ai/configurations
POST /api/v1/ai/configurations
PATCH /api/v1/ai/configurations/{id}
POST /api/v1/ai/configurations/{id}/test
POST /api/v1/ai/configurations/{id}/discover-models
DELETE /api/v1/ai/configurations/{id}

GET  /api/v1/assets
POST /api/v1/assets
POST /api/v1/assets/uploads
GET  /api/v1/assets/versions/{version_id}/preview
POST /api/v1/assets/generation-jobs
GET  /api/v1/assets/generation-jobs/{id}
POST /api/v1/assets/{asset_id}/versions/{version_id}/confirm
```

当前支持 OpenAI-compatible、Anthropic、Gemini、Ollama、自定义 OpenAI-compatible、Mock Provider。配置保存时 API Key 使用 Fernet 加密，序列化响应只返回掩码；连接测试按厂商协议拉取模型列表。演示 Provider 已验证 API → 单进程 Celery eager 任务 → 数据库回写链路。

演示 Provider 会创建新的候选版本并保持待确认；候选版本可通过确认接口人工入库，接口会记录审计且不自动发布、不自动改价、不覆盖历史版本。OpenAI-compatible、Anthropic、Gemini、Ollama 的真实文本生成适配器已完成，但必须显式设置 `AI_LIVE_GENERATION_ENABLED=true` 才会调用；图片/视频文件的 AI 生成、平台规则质检和跨平台分发尚未启用；文件上传与预览已支持 local/MinIO 存储后端。
