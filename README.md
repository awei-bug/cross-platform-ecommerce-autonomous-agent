# EcomOps-MultiAgent 跨境电商运营辅助系统

## 跨境多智能体改造（2026-10-15）

新增侧栏 **跨境智能体中枢**（`/ecomops`）：初始化与六类核心运营业务共 7 种持久化任务流；9 个核心 Agent 与平台/数据治理角色共享数据，统一事件总线驱动依赖推进，支持分级风控、强制审批、人工接管、定时任务与审计。可选复用现有真实文本模型适配器。

**当前交付为可运行的核心与沙盒流程。Amazon、AliExpress、Temu、Shopee、TikTok Shop 的官方连接器尚未实现，当前流程产出草稿、测算、建议与审核结果，不执行上架、广告、退款或发货。** 生产身份认证、法规/知识产权数据与生产并发验收也尚未完成。完整需求对照、架构图、验证与后续接入条件见 [跨境系统实现说明](docs/ECOMOPS_MULTIAGENT.md)。

启动后，先在“数据中台”导入产品/供应商等记录，再运行“初始化与基础配置”，即可执行本地业务流程。数据库新增迁移至 `20261015_0017`；原国内业务能力保留。

以下为原有国内业务模块的历史说明，其中“只保留抖店”仅描述已有国内连接器，不再限制跨境产品目标。

面向多店铺运营团队的统一操作与经营诊断中台。当前按 `docs/IMPLEMENTATION_PLAN.md` 分阶段实施。

## 垂类定位与能力冻结（2026-12，阶段 0 已执行）

本项目属于**电商垂类产品线**，角色是**跨平台运营中台**（选品 / 商品中心 / 订单售后 / 营销 / 素材 / 数据诊断）。
它已是 100% 电商项目（12 个 Agent 全为电商角色），阶段 0 的目标是停止在无资质平台上的无效投入。
整合方案见 [电商垂类整合计划](../电商垂类整合计划/README.md)。

以下能力已冻结：后续迭代不再投入、不对外演示、验收不计入。**冻结不等于删除**，代码与测试全部保留，恢复条件见冻结清单。

| 冻结项 | 代码落点 | 原因 | 恢复条件 |
| --- | --- | --- | --- |
| Amazon / AliExpress / Temu / Shopee / TikTok Shop 连接器入口 | `backend/app/services/ecomops_catalog.py` 的 `PLATFORMS`（全部 `status: adapter_required` / `live: False`） | 官方连接器未实现，继续做前端入口只会制造「已连接」假象 | 任一平台完成开放平台资质审核 + OAuth 授权闭环 + 端到端验证 |
| 无真实凭证下的「生产并发验收」承诺 | README 自述的未完成边界 | 项目边界声明，不需要再投入装饰性文档 | 真实店铺授权跑通一次完整链路 |

**不冻结（电商核心，继续投入）**：11 个电商 Agent 与事件总线、商品中心、订单与售后风险台、自动化中心、
素材 AI、抖店 OAuth 闭环与真实读写、公开竞品浏览器采集与热销证据。

冻结清单全文：[阶段0-电商无关能力冻结清单.md](../电商垂类整合计划/阶段0-电商无关能力冻结清单.md)。

> 工程取舍（2026-10-11 收敛）：本项目按"深度优先"裁剪后，平台连接器**只保留抖店**，并移除
> Redis / RabbitMQ / 独立 Celery Worker，任务改为单进程 `eager` 执行。淘宝、拼多多在演示数据中仍以
> 种子店铺呈现（用于多平台看板与筛选），但不再提供 OAuth 授权闭环——这样把有限精力压在一条
> 真正能跑通的 live 链路上，而不是用三个未验证的连接器制造"看似生产级"的假象。

## 当前进度（2026-10-11）

**阶段 A、阶段 B 代表性页面、阶段 C 操作闭环和阶段 D 素材 AI MVP 已完成；阶段 C.4 持久化任务基础设施已落地并通过本地生产模式烟囱验收。抖店 live 链路（真实只读同步 + 真实写入）已端到端跑通；真实文本模型已完成适配，但默认关闭，避免误调用产生费用。**

已落地：

- Vue 3 + TypeScript + Vite 前端与 FastAPI + Pydantic 后端；
- 登录、路由权限、组织/店铺上下文、搜索、告警与平台能力矩阵；
- 正式运营总览：经营指标、7 日趋势、风险优先级、任务进度、热销商品与上下文 AI 简报；
- 正式商品中心：服务端筛选/排序/分页、异常台账、批量任务、部分失败与重试、详情抽屉、竞品快照和 AI 建议；
- 订单与售后风险处置台：服务端 SLA、跨店筛选、脱敏详情、AI 回复草稿、高风险确认、能力限制、可追踪任务、部分失败重试和操作审计；
- **抖店 OAuth 授权闭环**（state 防 CSRF、Fernet 加密 Token、店铺身份校验与状态机）与凭证状态接口；淘宝、拼多多以种子演示店铺呈现，用于跨平台看板与筛选；
- SQLAlchemy 2.0 持久化模型、Alembic 数据库迁移、Celery 任务入口，以及 PostgreSQL 与可选 MinIO 的本地基础设施定义；
- 商品/订单任务、订单审计与告警已读状态已从进程内字典迁移到数据库；
- 自动化中心任务闭环：售后 SLA、库存安全线和商品质量规则，支持启停、扫描、按日去重任务、负责人、处理状态与执行历史；
- 素材 AI 中心与独立 AI 模型配置入口：厂商默认 Base URL、服务端 Fernet 密钥保存、连接测试、模型发现、默认模型和候选版本任务；
- 平台连接页（`/integrations`，侧栏「平台连接」）：集中展示抖店的连接器状态：只读范围、缺失的服务端凭证、已授权店铺与账号、Token 过期/授权时间、最近错误，并可发起或解除 OAuth 授权（前端只展示状态，不接触任何密钥）；

运营主数据（商品/店铺/告警/看板/自动化）现已持久化到数据库，不再是代码内硬编码元组；空库自动写入"种子演示店"，通过 `is_demo` 标志区分种子店与实时授权店铺。任务、审计和消息已读状态早已持久化：默认开发模式使用本地 SQLite，生产化配置使用 PostgreSQL；任务统一通过 Celery task 入口执行，**默认单进程 `eager` 模式（无需 RabbitMQ / Redis / 独立 Worker）**。真实平台**读取**（抖店 `product.listV2` 商品同步）与**写入**（抖店 `sku/editPrice` / `product/launchProduct` / `product/setOffline`）已在安全写路径中实现（幂等键 + 审计 + 部分失败重试），仅在目标店铺为实时授权连接时才真正调用平台 API；真实模型生成适配器已完成但由 `AI_LIVE_GENERATION_ENABLED=false` 默认保护。

自动化中心扫描数据库中的商品风险并生成可指派、可跟进的建议/人工确认任务，不会自动改价、退款、上下架或发送消息。真实写操作仅在店铺完成平台授权后才会真正执行，规则执行模式在授权前保持受限。

## 平台连接器 live 验证边界

抖店连接器使用统一的 OAuth state 机器与加密 Token 存储，代码与单元测试已用 `httpx.MockTransport` 拦截网络、无需真实店铺或凭证即可端到端验证（见 `tests/test_douyin_live.py`）。真实联调的能力边界：

- **抖店**：开放平台为开发者提供官方测试店铺（`op.jinritemai.com` 控制台 → 常用工具 → 测试账号管理 复制授权 code 或店铺 id），无需自有店铺即可换到真实 access_token、调真实 API，是个人开发者联调演示的最佳入口。**抖店已实现真实商品同步（`product.listV2`）与真实写入（`sku/editPrice`、`product/launchProduct`、`product/setOffline`）**，在 `/integrations` 页授权后点「同步商品」即可把真实店铺数据拉进系统，之后的改价/上下架会真实调用平台 API 并落审计。完整操作流程、测试店铺限制与验收清单见 `docs/DOUYIN_LIVE_SETUP.md`。
- **淘宝 / 拼多多**：当前仅以种子演示店铺呈现（看板、筛选、报表仍可见其演示数据），**不再提供 OAuth 授权闭环**。若后续要补回连接器，只需在 `backend/app/integrations/`、`app/services/*_connections.py` 与 `app/api/routes/integrations.py` 中按抖店同构模式登记，调度逻辑与写安全层无需改动。

## 素材 AI 当前边界

- 进入 `素材 AI` 页面即可创建文案、图片创意、短视频脚本和模板候选任务；
- 进入 `AI 配置` 页面选择厂商，系统自动填充 Base URL；保存 API Key 后由服务端加密保存，再测试连接即可拉取账号实际可用模型；
- 已接入 OpenAI-compatible、Anthropic、Gemini、Ollama 文本生成适配器；真实调用默认关闭，开启后仍只由后端调用，API Key 不进入日志或响应；
- 已验证演示 Provider 的生成任务会经过 API、单进程 Celery eager 任务和数据库回写，结果进入新版本；新增人工确认接口并记录审计；
- 真实图片/视频文件的 AI 生成、平台尺寸/敏感词/版权质检和跨平台分发仍未完成；文件上传、对象存储与登录后预览已接入。AI 不会自动发布、改价或覆盖线上素材。

## 架构与工程亮点

本项目不是玩具 demo，而是按生产级约束搭建的模块化单体，可作为面试作品集讲解：

- **抖店授权闭环**：统一的 OAuth state 防 CSRF、Token 经 Fernet 加密入库、卖家/店铺身份校验与状态机（`credentials_required → authorization_required → ready → revoked`）；抖店走抖音授权页 + 抖店 TOP 风格网关。
- **真实数据层（去硬编码）**：商品/店铺/告警/看板/自动化主数据持久化在数据库，空库自动种子化，读路径全部走 SQLAlchemy，而非写死的 Python 元组。
- **可演进的数据库**：SQLAlchemy 2.0 模型 + Alembic 迁移，开发用 SQLite、生产用 PostgreSQL，迁移脚本统一驱动。
- **单进程异步与审计**：批量/生成/订单动作统一经 Celery 任务入口（默认 `eager`，无外部 broker/result backend），每次写操作落审计日志，支持部分失败与重试。
- **能力矩阵驱动的平台动作**：前端不直接调平台 API，平台差异收敛在后端连接器与能力矩阵；高风险/批量动作必须确认、幂等、可追踪；平台连接页把连接器状态可视化，区分「缺服务端配置 / 待授权 / 已连接 / 已过期 / 异常」。
- **安全写路径**：真实改价/上下架仅在目标店铺为实时授权连接时调用平台 API，否则仅创建可审计的模拟任务；`is_demo` 标志明确区分，绝不把模拟数据描述成真实授权数据。
- **可容器化部署**：后端多阶段 Docker 镜像（非 root + 健康检查），根级 `docker-compose.yml` 编排 Postgres 与可选 MinIO + API + 前端 Nginx，浏览器同源反代 `/api`。

## 目录

```text
.
├── frontend/                # Vue 3 SPA
├── backend/                 # FastAPI API 与连接器边界（含 Dockerfile）
├── infra/compose.yaml       # 本地依赖服务（Postgres 与可选 MinIO）
├── docker-compose.yml       # 生产级全栈编排（API + 前端，任务单进程 eager）
├── .github/workflows/ci.yml # 后端 ruff+pytest、前端 lint+typecheck+build
├── docs/IMPLEMENTATION_PLAN.md
├── docs/PRODUCTION_RUNBOOK.md
├── docs/DOUYIN_LIVE_SETUP.md
├── DESIGN.md                # 设计系统与交互规则
└── PRODUCT.md               # 产品范围与业务职责
```

## 本地启动

### 1. 准备配置

```powershell
Copy-Item .env.example .env
Copy-Item .env.example backend/.env
```

### 2. 启动生产化基础设施

```powershell
docker compose --env-file .env -f infra/compose.yaml up -d postgres
```

若只做本地开发，可以不复制 `.env`，后端会使用 SQLite + Celery eager 模式。生产模式已验证 PostgreSQL 任务链路（单进程 eager，无需 RabbitMQ/Redis）；按 `docs/PRODUCTION_RUNBOOK.md` 启动 API 并运行生产烟囱验收。MinIO 已作为素材文件的可选存储后端接入（默认 local，需对象存储时再启动）；若想一键拉起完整生产栈（含后端 API 与前端 Nginx），在项目根目录执行 `docker compose --env-file .env up --build`，随后访问 `http://localhost:8080`（前端同源反代 `/api`）。

### 3. 启动后端

```powershell
cd backend
uv sync --dev
uv run alembic upgrade head
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

- 演示账号：`demo`
- 演示密码：`demo1234`

Windows 也可以直接双击项目根目录的 `一键启动.bat`。该脚本是本地开发快捷入口，会临时将后端切换到项目内 SQLite 和 Celery eager 模式，不使用 `backend/.env` 中的 PostgreSQL 生产配置；生产化启动请按 `docs/PRODUCTION_RUNBOOK.md` 执行。脚本会在启动前检查 `8000` 和 `5173` 端口，并在 API 与前端首页都可访问后才打开浏览器。

## 真实平台只读同步

连接状态接口：`GET /api/v1/integrations/connectors`（当前仅返回抖店）。

抖店已实现服务端 OAuth state、Token 加密持久化、卖家/店铺身份读取、授权状态和断开连接接口。没有完整服务端配置时返回 `credentials_required`；配置完成但未授权时返回 `authorization_required`；只有完成 Token 交换与官方身份 API 校验后才返回 `ready`。系统不再要求人工填写长期 `TAOBAO_ACCESS_TOKEN`。

配置、接口和真实联调验收见 `docs/DOUYIN_LIVE_SETUP.md`。商品/订单主数据目前仍是演示数据，真实分页同步尚未启用。

## 质量检查

```powershell
# 前端
cd frontend
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build

# 后端
cd backend
uv run ruff check .
uv run pytest
```

## 架构约束

无需店铺的公开竞品浏览器采集与入库流程见 [浏览器采集说明](docs/BROWSER_RESEARCH.md)；首批真实榜单、价格与分析见 [美国热销样本](docs/research/2026-10-15-US-HOT-PRODUCTS.md)。入口为「跨境智能体中枢 → 数据中台 → 公开竞品与热销证据」。

- Element Plus 只作为底层交互原语，业务页面复用项目自有组件；
- Pinia 管理客户端工作区状态，TanStack Vue Query 管理服务端状态；
- 前端不直接调用平台 API，平台差异收敛在后端连接器与能力矩阵；
- 高风险和批量动作必须确认、幂等、可追踪、允许部分成功并支持失败重试；
- 首版保持模块化单体，不提前拆微服务或微前端。
