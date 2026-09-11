# 一站式多平台电商运营 AI 工作台

面向淘宝、抖店、拼多多等多店铺运营团队的统一操作与经营诊断中台。当前正在按 `docs/IMPLEMENTATION_PLAN.md` 分阶段实施。

## 当前进度

**阶段 A：基础骨架与契约**

- Vue 3 + TypeScript + Vite 前端工程；
- FastAPI + Pydantic Mock API；
- 登录、路由权限、组织/店铺上下文；
- 固定侧栏、全局顶部栏、跨店铺搜索、消息告警；
- 平台能力矩阵与六个业务模块路由；
- PostgreSQL、Redis、RabbitMQ、MinIO 本地基础设施定义。

当前页面和接口中的业务数据均为**演示数据**。

## 目录

```text
.
├── frontend/                # Vue 3 SPA
├── backend/                 # FastAPI API
├── infra/compose.yaml       # 本地依赖服务
├── docs/IMPLEMENTATION_PLAN.md
└── PRODUCT.md               # 产品范围与业务职责
```

## 本地启动

### 1. 准备配置

```powershell
Copy-Item .env.example .env
Copy-Item .env.example backend/.env
```

### 2. 启动基础设施（后续真实持久化阶段需要）

```powershell
docker compose --env-file .env -f infra/compose.yaml up -d
```

阶段 A 的 Mock API 不依赖这些服务，因此也可以先跳过此步骤。

### 3. 启动后端

```powershell
cd backend
uv sync --dev
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API 文档：`http://127.0.0.1:8000/docs`

### 4. 启动前端

```powershell
cd frontend
pnpm install
pnpm dev
```

浏览器访问：`http://127.0.0.1:5173`

演示账号：`demo`
演示密码：`demo1234`

## 质量检查

```powershell
# 前端
cd frontend
pnpm typecheck
pnpm lint
pnpm test
pnpm build

# 后端
cd backend
uv run ruff check .
uv run pytest
```

## 架构约束

- Element Plus 只作为底层交互原语，业务页面优先复用项目自有组件；
- Pinia 管理客户端工作区状态，TanStack Vue Query 管理服务端状态；
- 平台差异只能进入后端连接器与能力矩阵；
- 长任务通过 Celery 执行，前端不能假设所有平台动作都能同步完成；
- 首版保持模块化单体，不提前拆微服务或微前端。
