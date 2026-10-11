# 生产化运行手册

## 当前实施单元

本阶段将原先的进程内任务、审计与消息状态迁移到了统一持久化层，并完成了本地生产模式验收：

- SQLAlchemy 2.0 领域持久化模型；
- Alembic 版本化数据库迁移；
- PostgreSQL 正式运行配置；
- Celery 任务入口（**单进程 `eager` 执行，无需 RabbitMQ / Redis / 独立 Worker**）；
- 本地 SQLite + Celery eager 降级模式；
- 告警单条已读、未读与全部已读持久化；
- 商品异步任务、订单异步处置与订单审计的生产链路烟囱测试；
- API 重启后从 PostgreSQL 重新读取任务状态的验收流程。

> 工程取舍（2026-10-11）：本项目已收敛为单进程 eager，移除 Redis / RabbitMQ / 独立 Worker 容器；
> 平台连接器只保留抖店（其 live 链路已端到端跑通）。淘宝、拼多多仅以种子演示店铺呈现，
> 不再提供 OAuth 授权闭环。

商品和订单主数据当前仍是明确标注的演示数据；抖店是唯一可真实接通的平台连接器。

## 本机当前端口

本项目默认使用以下端口：

| 服务 | 地址 |
| --- | --- |
| 前端开发服务 | `http://127.0.0.1:5173` |
| 开发模式 API | `http://127.0.0.1:8000` |
| 生产模式 API | `http://127.0.0.1:8001` |
| PostgreSQL（Docker 宿主机端口） | `127.0.0.1:5433` |
| MinIO（可选，素材存储） | `127.0.0.1:9000` |
| MinIO 管理台（可选） | `http://127.0.0.1:9001` |

如果本机原生 PostgreSQL 已经占用 `5432`，Docker PostgreSQL 使用宿主机 `5433`，容器内部端口仍然是 `5432`。不要停止或覆盖本机原生 PostgreSQL。

## 本地生产化启动

### 1. 启动 Docker Desktop

确认以下命令能够返回服务端信息：

```powershell
docker info
```

### 2. 准备配置

```powershell
Copy-Item .env.example .env
Copy-Item .env.example backend/.env
```

如果 `5432` 已被占用，两个配置文件都应使用 `POSTGRES_PORT=5433`，并将 `DATABASE_URL` 改为：

```text
postgresql+psycopg://ops_admin:ops_dev_password@127.0.0.1:5433/ops_command_center
```

不要把 `.env` 或 `backend/.env` 提交到 Git。正式环境必须更换示例密码，并通过密钥管理服务注入凭证。

### 3. 启动核心依赖

当前生产验收的核心任务链路不依赖 MinIO；素材文件存储验证另外启动 MinIO。先启动已验证的核心服务：

```powershell
docker compose --env-file .env -f infra/compose.yaml up -d postgres
docker compose --env-file .env -f infra/compose.yaml ps
```

不要使用 `docker compose down -v`，否则会删除 PostgreSQL 的本地数据卷。

### 4. 执行数据库迁移

```powershell
cd backend
uv sync --dev
uv run alembic upgrade head
uv run alembic current
```

当前预期迁移版本：`20261008_0007 (head)`。

### 5. 启动 API（单进程，任务 eager 执行）

生产模式使用 PostgreSQL，任务在 API 进程内以 `eager` 模式同步执行（无需独立 Worker）：

```powershell
$env:DATABASE_URL='postgresql+psycopg://ops_admin:ops_dev_password@127.0.0.1:5433/ops_command_center'
$env:DATABASE_AUTO_CREATE='false'
$env:CELERY_TASK_ALWAYS_EAGER='true'
# 真实模型生成默认关闭；确认预算、Key 和合规后才显式改为 true。
$env:AI_LIVE_GENERATION_ENABLED='false'
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8001/ready
```

`/ready` 在 PostgreSQL 不可连接时返回 HTTP 503；正常时返回数据库驱动和 `eager` 任务模式。它用于确认 API 与数据库配置正确。

## 自动化生产验收

在另一个 PowerShell 窗口执行：

```powershell
cd backend
uv run python scripts/production_smoke.py --base-url http://127.0.0.1:8001
```

脚本会验证：

- API 存活与 PostgreSQL 就绪；
- 演示账号登录和平台连接状态读取（当前仅抖店）；
- 商品列表读取；
- 商品任务写入 PostgreSQL、由 API 进程内 Celery eager 执行并回写 PostgreSQL；
- 订单处置任务的部分成功结果；
- 订单审计记录持久化；
- 告警已读状态写入、读取和恢复；
- AI 厂商配置持久化、演示模型发现、素材生成任务和人工确认审计。

该脚本只验证当前明确标注为 Demo 的主数据和 AI 演示 Provider，不调用真实模型，也不调用平台接口（除非你已配置抖店凭证并显式走 live 同步）。

## API 重启后的持久化验收

完成一次生产烟囱测试后，记录脚本输出中的商品任务或订单任务 ID。重启生产 API（不要停止 Docker 依赖）：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8001
Stop-Process -Id <生产 API 的 PID>
```

使用与启动 API 相同的环境变量重新执行 `uvicorn`，然后带演示令牌读取任务：

```powershell
$headers = @{ Authorization = 'Bearer demo-access-token' }
Invoke-RestMethod `
  -Headers $headers `
  http://127.0.0.1:8001/api/v1/products/jobs/<商品任务ID>
Invoke-RestMethod `
  -Headers $headers `
  http://127.0.0.1:8001/api/v1/orders/jobs/<订单任务ID>
```

如果仍能返回 `succeeded` 或 `partial` 的最终状态，即证明任务状态不是只存在于 API 进程内存中。

## Windows 停止命令

只停止本项目生产验收进程时，先用端口确认 PID，再执行：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8001
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
  Where-Object { $_.CommandLine -match 'uvicorn app.main:app.*8001' } |
  Select-Object ProcessId, CommandLine

Stop-Process -Id <生产 API PID>
```

不要停止 `5432` 对应的本机原生 PostgreSQL 进程，也不要通过模糊的 `Stop-Process` 命令误杀开发 API `8000` 或前端 `5173`。

## MinIO（素材文件存储后端，可选）

素材文件上传接口已支持 `local` 和 `minio` 两种后端。本地默认使用 `local`；生产或多人环境可将 `ASSET_STORAGE_BACKEND` 设为 `minio`。真实 Excel/PDF 文件生成仍未完成。需要验证 MinIO 时启动该服务：

```powershell
docker compose --env-file .env -f infra/compose.yaml pull minio
docker compose --env-file .env -f infra/compose.yaml up -d minio
docker compose --env-file .env -f infra/compose.yaml ps minio
```

如果 `quay.io/minio/minio:latest` 拉取长时间无响应，先检查镜像源或网络；不要删除已有 Docker volumes，也不要执行 `docker compose down -v`。

## 数据表

- `operation_jobs`：商品和订单任务、幂等键、进度、逐项结果与失败原因；
- `audit_logs`：订单操作审计与任务关联；
- `alert_states`：消息告警已读状态；
- `automation_rules`：自动化规则、运行模式和启停状态；
- `automation_runs`：规则扫描历史、命中数量和结果快照；
- `automation_tasks`：按日去重的运营任务、负责人、截止时间和处理状态；
- `platform_connections`：平台（当前仅抖店）授权状态与加密后的 Token；
- `oauth_states`：OAuth state 哈希、有效期和一次性消费状态。

## 回滚

数据库迁移回滚前必须先备份。开发环境可以执行：

```powershell
uv run alembic downgrade base
```

生产环境不应直接回滚包含业务数据的表，应优先发布向前修复迁移。

## 尚未完成

- 抖店之外的平台（淘宝、拼多多）当前仅以种子演示数据呈现，未提供 OAuth 授权闭环；
- 商品、订单主数据落库及增量同步；
- 任务超时、自动重试、死信队列与监控告警；
- 正式用户、组织、角色和数据隔离；
- 生产密钥管理、备份与恢复演练；
- 真实 Excel/PDF 文件生成；
- 平台规则质检、真实图片/视频生成和跨平台分发。
