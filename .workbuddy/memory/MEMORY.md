# 项目长期记忆（2026-10-15 精简版）

## 用户核心偏好（长期有效）
- 业务价值优先：不能拿界面、Agent 数量或测试通过冒充经营效果。功能按业务输入、可执行动作、可用输出判断价值。
- 用户无自有店铺是事实，但不得据此擅自裁剪功能范围；删除功能前必须先明确本轮边界。
- 删除文件一律彻底删除、不进回收站（/usr/bin/rm -f 或 PowerShell Remove-Item -Force；详见用户级记忆）。

## 产品现状（2026-10-15）
- 定位 EcomOps-MultiAgent 跨境运营：1 总调度 + N 专项 Agent + 统一数据中台 + 合规风控；跨境任务收敛为初始化+六类核心业务 7 种，DAG 以本地草稿/测算/审核为终点。
- 技术栈：FastAPI/Pydantic、SQLAlchemy 2/Alembic、Celery eager（memory:// broker，无独立 Worker）、Vue 3 + Vue Query。数据库迁移到 0017。文档 docs/ECOMOPS_MULTIAGENT.md。
- Amazon/AliExpress/Temu/Shopee/TikTok Shop 官方连接器未实现；外部写步骤必须停在 waiting_integration。AI 生成需 AI_LIVE_GENERATION_ENABLED 与任务 use_ai 双开关。
- 人工审批须展示金额/阈值/对象并绑定规则版本；冻结输入缺失走复制修订。

## 已验证业务缺口（详见 docs/BUSINESS_VALUE_AUDIT.md）
- 数据断点：淘宝客导入写 CompetitorModel，跨境调研读 OpsRecord(kind=competitor)，两库未打通；跨境文案任务输出未自动成为素材版本或发布草稿，需人工转录。
- 选品非利润维度默认 70 分等权平均；营销预算固定 70/20/10。均为模板规则，无证据来源，须如实说明。
- 合规仅为词规则与阈值；专利/税务/清关需外部证据。省时、可采用输出比例、选品准确率均未测量。
- 下一步建议链路：真实候选商品+供应商报价 → 可追溯竞品 → 利润测算 → 人工决策 → 文案入库，并测量效果。尚未实施。

## 公开热销商品浏览器研究（2026-10-15 验收）
- 流程：浏览 Amazon US Home & Kitchen 榜单+商品页，存排名/主售价/购买量声明/截图 SHA256/时间，写入日常 SQLite。报告 docs/research/2026-10-15-US-HOT-PRODUCTS.md，复跑见 docs/BROWSER_RESEARCH.md，证据 backend/data/research/us-home-bestsellers-20261015/verified-live/。
- 复跑：frontend/scripts/collect-competitors.mjs --manifest ../research/us-bestsellers.example.json --api http://127.0.0.1:8011，凭证 ECOMOPS_TOKEN。
- 规则：只取当前主报价（同页有二手/其他规格价）；购买量声明不能换算精确销量；利润需供应商与全程履约报价。价格/排名是当时事实，复用必须重采。
- 采集器测试用 .checks.mjs + pnpm test:research；E2E 走 test:e2e 重置隔离库。

## 国内模块历史约定（2026-10-11/12）
- 抖店是唯一 live 连接器（OAuth+同步+写动作+审计）。淘宝/拼多多仅作种子演示店铺（services/seed.py），无连接器，不要"补回"。
- 准入现实：抖店电商开放平台个人主体不可入驻；小红书电商个人全部不可达；抖音生活服务测试店铺不能验证电商链路。MockTransport 契约测试（tests/test_douyin_live.py）为验证基线。
- 个人可达路径已落地：淘宝客竞品导入（POST /api/v1/agent/competitors/import-taobaoke，tests/test_taobaoke.py）；抖音内容投稿 /content-studio（integrations/douyin_content/，tests/test_douyin_content.py）。90 天无调用/无投稿会被回收。

## 验证基线（2026-10-12 定版）
- 一键启动.bat 用 backend/data/ops_workbench.db（SQLite）+ eager；直接在 backend 启动读 backend/.env。测试库通过不代表日常库已升级。
- 命令一律 python -m 形式（本机 uv trampoline 对 Anaconda uv 报错）：backend\.venv\Scripts\python.exe -m。
- 前端：CI=true pnpm typecheck/build/test；重建 build 需 CODEBUDDY_SAFE_DELETE_ENABLED=0（safe-delete 垫片拦 Vite emptyDir）。
- 生产烟囱：no_proxy="127.0.0.1,localhost" + scripts/production_smoke.py（否则 502）。后台起 API 用 Bash run_in_background。
- 布局改造（2026-10-15）：五组导航（工作台/业务运营/内容/分析/系统），手机 Drawer；跨境首页任务台账+两步创建 Drawer；验收含 4+1 项浏览器测试与 detector layout 0 发现。缩放流程仍有 ResizeObserver 开发告警。

## 工具教训
- 同一消息里对同一文件的多个 Edit 会竞争覆盖，须分轮串行并复核。
- SQLite naive datetime 与 aware now 相减会 TypeError，比较前 replace(tzinfo=SHANGHAI)。
- Windows 项目目录改名后 pnpm junction 可能失效，用 CI=true pnpm install --frozen-lockfile 重建。

## 辅助模块速记
- /ops 任务运维：三域统一视图，超时阈值在 ops_task_service.STALE_TIMEOUTS，dead_letter 只能 discard。
- /diagnostics 数据诊断：健康分 health-score-v1（权重 diagnostics_service.HEALTH_WEIGHTS），导出用 reportlab STSong-Light + openpyxl。
- /agent 智能体复盘：诊断必带 evidence；智能体只读不建 OperationJob；竞品检索是轻量关键词向量（非 pgvector）；竞品库是演示数据（is_demo=True）。
