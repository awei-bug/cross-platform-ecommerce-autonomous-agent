# 项目长期记忆

## 架构约定（2026-10-11 收敛后）
- **平台连接器只保留抖店（douyin）**，且已端到端跑通 live 链路（OAuth + `product.listV2` 同步 + `sku/editPrice`/`product/launchProduct`/`product/setOffline` 真实写入 + 审计）。
- **淘宝/拼多多不再有 OAuth 连接器**。它们在代码里仅作为**种子演示店铺**存在（见 `services/seed.py` 及 order/review/campaign 仓库），用于多平台看板与筛选。`Platform` 枚举仍保留 `TAOBAO`/`PINDUODUO` 值，前端 AppShell 及各视图的平台筛选器也保留——这些是筛种子数据的入口，不是连接器。
- **任务执行 = 单进程 Celery eager**，无 RabbitMQ/Redis/独立 Worker。`core/config.py` 默认 `task_always_eager=True`、broker `memory://`；`docker-compose.yml` 仅编排 postgres + 可选 minio + api + frontend。
- **不要"补回"淘宝/拼多多连接器**当作缺失项——这是刻意的深度优先取舍。若要恢复，按抖店同构模式在 `integrations/`、`*_connections.py`、`routes/integrations.py` 登记即可，调度逻辑不变。

## 验证基线
- 后端：`uv run ruff check .` + `uv run pytest`（49 passed）。
- 前端：`pnpm typecheck` + `pnpm build`。
- 生产烟囱：`uv run python scripts/production_smoke.py --base-url http://127.0.0.1:8001`。

## 删除文件约定（2026-10-11）
- 用户要求彻底删除、**不进回收站**。WorkBuddy 的 `rm` 是 safe-delete 垫片（移到回收站）。
- 彻底删除用 `/usr/bin/rm -f <path>`（绕过 rm 函数垫片）；个人目录删文件先说明再删。
