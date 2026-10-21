# 一站式多平台电商运营 AI 工作台：整体实现方案

> **2026-10-15 最新范围**：产品升级为 EcomOps-MultiAgent 跨境运营辅助系统。新增 `/ecomops`、四层架构与四阶段的任务流核心；完整已实现/待接入矩阵见 [ECOMOPS_MULTIAGENT.md](ECOMOPS_MULTIAGENT.md)。旧文档中的“平台只保留抖店”“智能体只读”为国内模块历史合同，不限制新跨境域。跨境平台真实连接器未实现，不得将沙盒闭环描述为生产全自动系统。

> 状态：阶段 A、B、C 已完成；阶段 D 素材 AI MVP 已完成；阶段 E 数据诊断页与智能体复盘闭环已落地
>   
> 日期：2026-09-12
>   
> 基线：六张参考图与用户提供的业务说明是产品和视觉依据；当前仓库已完成阶段 B 两个代表性页面与阶段 C 订单售后演示闭环。

## 0. 实施状态（2026-09-13）

阶段 A 已完成并验证。阶段 B 当前状态：

- [x] 商品中心：服务端筛选、排序、分页，异常优先表格、批量确认、任务进度、部分失败/重试和详情抽屉；
- [x] 运营总览：指标定义与对比、7 日 ECharts 趋势、损失优先风险、任务进度、热销商品和上下文 AI 简报；
- [x] 全局店铺/平台上下文：支持多选店铺、平台筛选、常用店铺分组，并让运营总览、商品中心、订单与售后按范围刷新；
- [x] 投放与广告数据页（演示数据）：广告账户、计划监控、花费/成交趋势、预算告警和 AI 建议；
- [x] 建立统一只读连接器协议和凭证状态接口；
- [x] 真实平台只读同步（2026-10-12 更新）：抖店连接器已实现真实商品同步（`product.listV2`）与真实写入（`sku/editPrice`、`product/launchProduct`、`product/setOffline`），代码与契约测试端到端覆盖；真实联调需企业/个体户主体资质（官方文档核实），个人主体以 `tests/test_douyin_live.py` 的 MockTransport 契约测试为验证基线。

阶段 C 已完成订单售后风险操作闭环，并完成 C.4 持久化实施单元：商品/订单任务、订单审计和告警已读状态使用 SQLAlchemy 持久化，Alembic 管理版本，Celery 统一任务入口；本地开发使用 SQLite + eager，正式配置使用 PostgreSQL + RabbitMQ + Redis + 独立 worker。当前已完成生产模式基础链路验收；真实平台凭证与只读同步仍暂缓，下一实施单元转为生产可靠性与数据域建设。

2026-10-08 新增自动化中心任务闭环：规则、运行记录、暂停开关和运营任务已持久化；首批规则覆盖售后 SLA、库存安全线和商品质量，扫描命中按规则、对象和日期去重，支持负责人及处理状态。当前只对演示数据生成建议/人工确认任务，不允许自动写入平台。

## 0.6 智能体复盘闭环进度（2026-10-12）

按业务方提供的《从零到一落地完善与问题解决全过程》文档，落地目标驱动的智能体复盘链路：

- [x] 规划：`agent_orchestrator.plan_goal` 把自然语言目标解析为带波次的执行计划（数据汇总与竞品扫描同波次并行，自检复盘为硬约束），依赖自动传导；
- [x] 执行：`execute_run` 按波次推进，同波次步骤经 `asyncio.gather` + 独立 session 并行读取；每步落 `agent_steps`（状态、输入输出、耗时）；
- [x] 数据 Agent：`data_collect` 汇总范围內店铺商品并做质量校验（缺成本价、在线无销量、零转化），结果作为诊断与反思输入；
- [x] 竞品 Agent：`competitor_repository` 结构化沉淀竞品（标题/定价/卖点/评价痛点），以关键词权重向量（可演进为 pgvector）做余弦相似度检索，诊断阶段按商品标题对标；
- [x] 诊断反思 Agent：`diagnosis_engine` 规则诊断强制携带证据链（指标/实测值/阈值/来源）；`reflect` 丢弃无证据结论、竞品覆盖不足时降级置信度并触发补采，最多重跑一轮（`supplement_competitor` → `rediagnosis`）；
- [x] 人工确认边界：涉及改价、上下架、批量修改标题的建议 `risk_level=high`，初始 `pending`，经 `POST /agent/runs/{id}/diagnoses/{did}/decision` 确认或驳回后才算决策完成；确认只记录决策，不触发平台写入；
- [x] 只读约束：智能体运行不创建 `OperationJob`、不调用平台写接口（`test_agent_run_creates_no_platform_write_jobs` 兜底）；
- [x] 前端：`/agent` 智能体复盘页（目标输入与模板、波次时间线、反思记录、带证据表的诊断清单、确认/驳回、竞品库检索与录入），权限 `diagnostic:read`；
- [ ] 竞品真实采集源（当前为演示知识库）、向量检索换 pgvector、AI 真实模型生成方案文本（当前为规则模板汇总），均留作后续独立阶段。

## 0.7 数据诊断页进度（2026-10-12）

按本计划 6.6 节的设计约束落地「数据诊断」页（`/diagnostics`，权限 `diagnostic:read`）：

- [x] 首屏核心为问题清单而非图表：按「预计损失金额 × 紧迫度 × 置信度」排序，每条问题携带证据链（指标/实测值/阈值/来源）与估算口径说明；
- [x] 健康分可解释：五个分项（库存健康、转化效率、差评风险、价格竞争力、售后时效）各自输出得分、权重与人类可读明细，算法版本化（`health-score-v1`）；
- [x] 指标定义由服务端下发（`metric_definitions`），前端统一展示口径；
- [x] 对比模块：店铺对店铺的横向对比（健康分、问题分布、销售额、数据源），本期对上期待历史数据快照接入后支持；
- [x] AI 诊断报告双路径：规则模板永远可用；配置了可用模型且 `AI_LIVE_GENERATION_ENABLED=true` 时走真实模型，prompt 强制"只引用提供的数据点、区分事实/推测/建议"，模型失败自动降级并在报告首部如实说明；
- [x] 报告快照落库（`diagnostic_reports.snapshot`），报告与生成时数据严格对应，可复现；
- [x] 导出为后端真实文件：PDF（reportlab + 内置 CID 中文字体 STSong-Light，本地与容器输出一致）与 Excel（openpyxl，健康分/问题清单/店铺对比三个 sheet）；导出记录落库、下载需登录（`tests/test_diagnostics.py` 覆盖 14 个用例）；
- [ ] 本期对上期环比、组织级数据隔离、报告订阅推送留作后续阶段。

## 0.8 报表导出真实文件（2026-10-12）

- [x] `report_export_service.py`：后端生成真实 Excel（四 sheet：指标概览含环比、7 日趋势、主体明细、口径与边界声明）与 PDF（reportlab 表格渲染，复用内置 CID 中文字体）；文件名含模板名与店铺标签；
- [x] 导出记录从内存演示迁移到数据库（`report_exports` 表 + 迁移 `20261012_0013`），状态、文件大小、错误信息可追溯；
- [x] 下载端点 `GET /reports/exports/{id}/download`（登录鉴权，RFC 5987 中文文件名，对象键不回显）；
- [x] 前端：导出后自动触发下载；导出记录列表显示文件大小并提供历史文件「下载」按钮；
- [x] 共享 PDF 字体辅助模块 `pdf_render.py`（诊断导出与报表导出共用，注册幂等）；
- [x] 端到端验证：Excel 8129 字节四 sheet 结构正确、PDF 4561 字节 `%PDF-1.4` 且中文字体嵌入、中文文件名正确编码（`tests/test_report_exports.py` 覆盖 6 个用例）。

## 0.9 素材真实质检与图片生成（2026-10-12）

- [x] `asset_quality_service.py`：平台尺寸真实检查（Pillow 读图对照内置多平台主图规则表）、广告法违禁词真实扫描（内置词库，按词长降序去重命中）、版权检查占位跳过（不冒充通过）；
- [x] 质检记录落 `asset_quality_checks`，聚合更新版本 `quality_status` / `quality_issues`；上传与生成后自动执行，`POST /assets/versions/{id}/quality-checks` 支持手动重检；
- [x] `ai_image_generation.py`：OpenAI 兼容协议图片生成适配器（b64_json 与 url 两种返回，url 自动二次下载），非兼容协议如实报错不伪造；
- [x] 生成任务对 `image` 类型接真实图片生成：开关保护（`AI_LIVE_GENERATION_ENABLED`）、文件落对象存储、版本绑定 preview、生成后自动质检；失败如实报错；
- [x] 前端素材页质检清单改为数据驱动（动态渲染质检问题、三态标签、重新质检按钮）；
- [x] 测试隔离修复：导出/上传类测试统一使用临时素材目录，不再污染 `data/assets`（相关 29 个用例已覆盖验证）；
- [ ] 视频文件生成、真实版权库、跨平台分发留作后续阶段。

## 0.10 任务运维：超时、重试、死信与监控（2026-10-12）

- [x] 三类任务统一运维视图（`ops_task_service.py`）：操作任务、素材生成、智能体运行合并且保留各自状态词汇；`operation_jobs` / `generation_jobs` / `agent_runs` 统一增加 `attempts` / `max_attempts` / `started_at` / `dead_letter_at`（迁移 `20261012_0014`）；
- [x] 超时巡检：执行中超过阈值（操作任务 15 分钟、生成与智能体 10 分钟）的任务标记为失败并写明原因；`POST /ops/tasks/sweep` 手动触发，`ops.sweep_stale_tasks` Celery 入口供生产调度器周期调用；SQLite naive datetime 已做时区归一；
- [x] 重试：失败任务经 `POST /ops/tasks/{kind}/{id}/retry` 重新走原 Celery 入口，`attempts` 递增；失败且重试耗尽的在巡检时进入 `dead_letter`，拒绝继续重试（409）；
- [x] 丢弃：`POST /ops/tasks/{kind}/{id}/discard` 将失败/死信任务标记为 `dismissed`，保留记录不再重试；
- [x] 监控指标：`GET /ops/metrics` 汇总状态分布、失败率、平均耗时、按类型分布与最近失败；生成任务响应补充运维字段；
- [x] 前端「任务运维」页（`/ops`）：指标卡、类型与状态筛选、任务表（重试/丢弃）、最近失败列表、一键巡检；
- [x] 端到端演练：失败任务 → 重试两次（attempts 1→3）→ 巡检进死信 → 死信拒绝重试 → 丢弃 → 指标聚合正确（`tests/test_ops_tasks.py` 覆盖 9 个用例）。

## 0.11 个人可达真实数据路径（2026-10-12 新增）

在「深度优先、抖店单连接器」的总体取舍之外，本阶段新增两条**个人主体即可申请、无需企业/个体户店铺资质**的真实数据路径，把项目的「真实联调」边界从「只有企业资质的抖店电商」扩展到「个人可达的公开数据源与内容发布」：

### 0.11.1 淘宝客竞品导入（个人可达 ✅）

- [x] 入口：智能体复盘页（`/agent`）竞品库区「从淘宝客导入」对话框 → `POST /api/v1/agent/competitors/import-taobaoke`（请求体 `CompetitorImportRequest`：keyword/limit/category，返回 `CompetitorImportResult`：导入条数/来源/失败明细）；
- [x] 后端：
  - `app/integrations/taobao/client.py`：`TaobaokeClient`（淘宝联盟 TOP 网关 `taobao.tbk.dg.material.optional`），`sign_top_request`（MD5 首尾包 secret、大写）、`parse_materials`（佣金率万分位折算百分比、识别天猫）、`search_materials`（异步 + 可注入 `transport`）；
  - `app/services/competitor_repository.py`：`import_taobaoke_competitors`（去重写入竞品库，`is_demo=False`）；
  - `app/api/routes/agent.py`：路由接入，缺失 `TAOBAOKE_*` 服务端配置返回 `409 taobaoke_credentials_required`，网关错误返回 `502 taobaoke_api_error`（带 `retryable`）；
  - `core/config.py`：`TAOBAOKE_APP_KEY/APP_SECRET/ADZONE_ID` 配置项；
- [x] 前端：`AgentReviewView.vue` 导入对话框 + `api/index.ts` 的 `agentApi.importTaobaoke`（成功失效 `['agent-competitors']` 查询）；
- [x] 测试：`tests/test_taobaoke.py`（5 个用例：签名大写、解析提取、错误响应抛错、网关调用与解析、路由缺凭证返回 409），全部用 `httpx.MockTransport` 拦截网络；
- [ ] 真实联调需个人在阿里妈妈完成实名 + 媒体备案 + 推广位 PID 并创建开放平台应用；高级接口邀请制、连续 30 天无调用回收，以阿里妈妈后台为准。

### 0.11.2 抖音内容发布工作台（个人可达 ✅）

- [x] 入口：`/content-studio`（侧栏「内容发布」，权限 `diagnostic:read`），含连接状态面板、OAuth 授权/断开、草稿表单、发布队列（状态标签 + 「投稿到抖音」按钮）；
- [x] 后端：
  - `app/integrations/douyin_content/client.py`：`DouyinContentClient`（抖音开放平台 open.douyin.com），`build_authorization_url`（state + `video.create`/`renew_refresh_token` scope）、`exchange_code`（解析 access/refresh token + open_id + 过期时间）、`create_video`（multipart 上传 `video/create_video/`，返回 item_id/video_id/share_id，error_code≠0 抛 `DouyinContentApiError`）；
  - `app/schemas/common.py`：`Platform` 枚举新增 `DOUYIN_CONTENT = "douyin_content"`（与抖店电商 `douyin` 完全隔离，避免授权状态互相污染）；
  - `app/services/content_connections.py`：镜像 `douyin_connections` 的 OAuth state 机器 + Fernet 加密，平台值改用 `DOUYIN_CONTENT`；
  - `app/services/content_publish_service.py`：`create_draft` / `list_publishes` / `get_publish` / `publish_content`（校验草稿状态 → 检查 `douyin_content` 连接 ready 且 Token 可解密 → 拉取视频二进制 → 调用 `create_video` → 翻转 `is_demo=False`；缺配置/未授权/视频拉取失败均安全失败，不伪造）；
  - `app/api/routes/content_studio.py`：`/connect/status`、`/connect/authorize`、`/connect/callback`、`/connect/disconnect`、`/publishes`（POST 草稿 / GET 列表）、`/publishes/{id}/publish`；
  - 迁移 `20261012_0015_content_publish.py`：新建 `content_publishes` 表（organization_id/platform/title/text/video_url/cover_url/status/external_id/external_url/error_message/is_demo/时间戳）+ 索引 `ix_content_publishes_org_created`；
- [x] 前端：`ContentStudioView.vue` + `router.ts`（/content-studio）+ `SideNav.vue`（`VideoPlay` 图标）+ `api/index.ts` 的 `contentStudioApi`；
- [x] 测试：`tests/test_douyin_content.py`（7 个用例：授权 URL 含 state/scope、exchange_code 返回 token、create_video 上传并返回 item_id、API 错误上抛、草稿发布真实调用抖音并置 published、无连接安全失败、连接状态缺凭证返回 credentials_required），全部用 `httpx.MockTransport` 拦截网络；
- [ ] 真实联调需个人注册抖音开放平台应用（审核制、需真实应用载体），90 天无投稿回收；小程序/POI 锚点需企业。

### 0.11.3 边界澄清（与总体取舍一致）

- 抖店电商连接器仍是唯一「真实店铺读写」链路，需企业/个体户资质；淘宝、拼多多仅种子演示店铺。
- 淘宝客与抖音内容发布是**独立于电商 OAuth** 的个人可达公开路径，不依赖卖家店铺授权；二者都经过统一 OAuth state 机器 + Fernet 加密，未授权时安全失败，绝不把 Mock 数据描述成真实授权数据。
- 小红书、微信公众号对个人主体不可达，明确不做连接器（详见 `MEMORY.md`「抖店真实联调的准入现实」）。

## 1. 总体结论

建议采用“前后端分离的模块化单体 + 异步任务系统 + 平台适配层”的首版架构：

- 前端使用 Vue 3、TypeScript、Vite，构建单页 B 端工作台；
- 后端使用 FastAPI，统一提供业务 API、鉴权、数据聚合和 AI 编排；
- 平台差异收敛在服务端连接器和能力矩阵中，前端只面向统一领域模型；
- PostgreSQL 保存核心业务与配置，Redis 负责缓存、锁和短期状态；
- Celery 负责平台同步、批量操作、AI 生成、报表导出、素材处理等长任务；
- 素材文件进入 S3 兼容对象存储，不直接存数据库；
- 首版不要上微前端、Kubernetes、ClickHouse、Elasticsearch，达到明确规模阈值后再引入。

## 2. 为什么选择 Vue 3，而不是 Next.js/Nuxt

这是登录后使用的内部操作型产品，SEO 和服务端渲染价值很低。关键难点是复杂表格、筛选、抽屉、批量操作、共享店铺上下文和实时任务反馈，因此推荐轻量 SPA：

- Vue 3 Composition API 适合把筛选器、表格选择、平台能力、任务进度等逻辑抽为 composables；
- TypeScript 强制约束跨平台统一模型、表格字段、AI 上下文和操作状态；
- Vite 提供开发与构建工具链；
- Vue Router 管理六个业务域路由和权限路由；
- Pinia 只管理账号、组织、当前店铺、全局筛选、布局等客户端状态；
- 服务端列表、详情、指标和缓存统一交给 TanStack Vue Query，避免把所有接口数据塞入 Pinia。

Nuxt/Next 的 SSR 能力会增加鉴权、缓存边界和部署复杂度，但对本项目首版没有对应收益。未来若增加公开官网或公开报告页，可单独建立站点，不需要让中台本身承担 SSR。

## 3. 前端技术栈

| 层级      | 推荐选型                                    | 使用方式                        |
| ------- | --------------------------------------- | --------------------------- |
| 框架      | Vue 3 + TypeScript + `<script setup>`   | 六个业务域按模块拆分                  |
| 构建      | Vite                                    | SPA、按路由懒加载、环境配置             |
| 路由      | Vue Router                              | 路由元信息承载权限、菜单、面包屑、页面标题       |
| 客户端状态   | Pinia                                   | 用户、组织、店铺上下文、全局 UI 状态        |
| 服务端状态   | TanStack Vue Query                      | 请求缓存、失效刷新、轮询、分页、Mutation 状态 |
| 基础组件    | Element Plus                            | 表单、弹窗、抽屉、分页、日期、表格基础能力       |
| 设计系统    | CSS Variables + SCSS + 自有组件封装           | 不直接在业务页散落 Element Plus 样式覆盖 |
| 图表      | Apache ECharts                          | 趋势、漏斗、饼图、利润、广告与诊断图表         |
| 日期      | Day.js                                  | 时间范围、活动日历、售后倒计时             |
| API     | 基于 FastAPI OpenAPI 生成 TypeScript Client | API 类型由后端契约生成，减少手写漂移        |
| 单元/组件测试 | Vitest + Vue Test Utils                 | 领域函数、composables、复杂组件       |
| 端到端测试   | Playwright                              | 登录、切店、筛选、批量操作、抽屉、任务进度       |
| Mock    | Mock Service Worker 或本地 mock adapter    | 后端未完成前并行开发页面                |

### 3.1 组件库使用原则

Element Plus 只作为“底层交互零件”，不作为视觉成品。建立自己的业务组件层：

- `AppShell`、`SideNav`、`GlobalHeader`、`StoreSwitcher`；
- `MetricCard`、`RiskBadge`、`HealthScore`、`SyncStatus`；
- `FilterBar`、`DataTable`、`BatchActionBar`、`DetailDrawer`；
- `TaskPool`、`JobProgress`、`AiSuggestionPanel`；
- `ChartCard`、`EmptyState`、`PermissionGuard`、`CapabilityAction`。

业务页面只能使用这些统一封装或明确允许的基础组件，避免六个页面各自覆盖组件库样式，最终无法维护。

### 3.2 视觉系统落地

从六张参考图提取统一 Token，而不是逐页“照图写 CSS”：

- 布局：固定侧栏、固定顶部栏、主内容自适应；
- 色彩：深蓝导航、淡蓝页面底色、白色卡片、蓝/青主操作色；
- 风险：红色紧急、黄色待处理、绿色常规，但必须附带文字/图标；
- 圆角、阴影、间距、字号、表格密度全部 Token 化；
- 支持 1440px 主工作宽度和 1280px 最低桌面宽度；较窄窗口通过折叠侧栏、横向滚动表格和抽屉全屏化适配；
- 页面优先做桌面操作体验，不把复杂中台强行压成手机端同构页面。

## 4. 后端与基础设施技术栈

| 层级      | 推荐选型                           | 责任                                |
| ------- | ------------------------------ | --------------------------------- |
| Web API | FastAPI + Pydantic             | REST API、鉴权、校验、OpenAPI 契约、AI 流式响应 |
| ORM/迁移  | SQLAlchemy 2.x + Alembic       | 数据访问与数据库版本迁移                      |
| 主数据库    | PostgreSQL                     | 组织、店铺、商品、订单、活动、任务、规则、审计           |
| 缓存/锁    | Redis                          | 热点缓存、分布式锁、幂等键、短期任务状态              |
| 异步任务    | Celery + RabbitMQ（生产）          | 同步、批量动作、报表、AI、图像和素材处理             |
| 定时任务    | Celery Beat                    | 周期拉取、巡检、预警、日报周报                   |
| 对象存储    | MinIO（本地）/S3 兼容服务（生产）          | 图片、视频、导出文件、报告 PDF                 |
| 实时反馈    | SSE 优先，必要时 WebSocket           | 告警、任务进度、AI 流式输出                   |
| 可观测性    | OpenTelemetry + 日志/指标平台        | 请求链路、同步任务、平台错误和 AI 成本             |
| 部署      | Docker Compose 起步，Nginx/网关统一入口 | 本地、测试、首版生产部署                      |

### 4.1 为什么必须有平台适配层

淘宝、抖店、拼多多的字段、状态、授权和可执行动作不同。不能让六个页面分别判断平台差异，应定义统一接口：

```text
PlatformConnector
├── sync_products()
├── sync_orders()
├── sync_after_sales()
├── update_price()
├── change_listing_status()
├── reply_review()
├── sync_logistics()
└── publish_material()
```

每个连接器返回标准结果，并由“平台能力矩阵”声明某店铺当前是否支持某动作。前端按钮统一呈现为：

1. 可直接执行；
2. 提交异步任务；
3. 跳转平台后台；
4. 未授权/暂不支持。

这能避免界面承诺了“一键处理”，但实际平台 API 没有权限或能力。

## 5. 推荐领域模型

核心实体至少包括：

- `organization`、`user`、`role`、`shop`、`platform_account`；
- `product_spu`、`platform_sku`、`inventory_snapshot`、`price_history`；
- `order`、`order_item`、`shipment`、`after_sale`、`buyer_risk`；
- `campaign`、`campaign_schedule`、`coupon_rule`、`campaign_review`；
- `asset`、`asset_version`、`generation_job`、`distribution_job`；
- `metric_fact`、`health_score`、`diagnostic_issue`、`metric_definition`；
- `alert`、`operation_task`、`task_execution`、`audit_log`；
- `ai_session`、`ai_run`、`ai_suggestion`、`prompt_template`。

所有跨店铺实体都必须携带 `organization_id`、`shop_id`、`platform`；所有外部写操作记录操作者、请求参数摘要、平台响应、重试次数和最终状态。

## 6. 六个页面的前端模块设计

### 6.1 运营总览

路由：`/dashboard`

- `KpiSection`：时间范围切换、指标卡、环比、口径提示；
- `TaskPool`：后端按严重度、SLA、预计损失、发生时间综合排序；
- `OverviewCharts`：趋势、来源占比、广告消耗、热销 SKU；
- `AiOpsAssistant`：自动注入当前店铺、时间、选中 SKU 和可见指标；
- 告警与指标卡支持刷新时间和数据源提示。

### 6.2 商品中心

路由：`/products`

- 服务端筛选、排序、分页，禁止一次拉取全部 SKU；
- 表格列配置可保存到用户偏好；
- 批量选择支持“当前页选择”和“按当前筛选条件全选”两种语义；
- 异常字段不仅标红，还提供原因和检测时间；
- SKU 详情使用路由化抽屉，例如 `/products?sku=...`，刷新或分享后仍可恢复；
- 批量操作进入任务中心，展示总数、成功、失败、失败原因和重试。

### 6.3 订单与售后

路由：`/orders`、`/after-sales`

- 订单与售后分标签页，但共用筛选器和详情抽屉；
- 售后剩余时效由服务端返回截止时间，前端仅负责倒计时显示；
- 详情抽屉聚合买家脱敏信息、聊天上下文、商品、物流、售后记录；
- AI 回复必须是“建议草稿”，用户确认后才能发送；
- 明确不实现 ERP 波次、拣货、打单和仓库库存流程。

### 6.4 营销活动

路由：`/campaigns`

- 日历与列表共用同一查询条件和活动数据源；
- 日历使用领域化 CSS Grid 实现活动条和跨日跨度，避免为了简单月历引入过重排期系统；
- 冲突检测由后端规则引擎完成，包括价格底线、券叠加、时间重叠、库存和预算；
- 冲突结果区分阻断、强提醒和普通建议；
- 活动结束后自动生成待复盘任务。

### 6.5 素材 AI 中心

路由：`/assets`

- 三栏可调整布局：素材树/列表、生成工作区、预览与质检；
- 上传采用分片/直传对象存储，数据库只保存元数据和版本；
- 文案、图片、视频脚本生成全部采用异步任务；
- 素材分发前先运行平台尺寸、敏感词、版权和店铺授权检查；
- 生成历史可复制参数重新运行，避免只保存最终文本或图片。

### 6.6 数据诊断

路由：`/diagnostics`

- 首屏核心不是图表，而是按“预计损失金额 × 紧迫度 × 可信度”排序的问题清单；
- 健康分必须保留可解释的分项和版本化算法；
- 指标定义由服务端下发，前端统一使用 `MetricTooltip` 展示口径；
- 对比模块支持店铺对店铺、本期对上期；
- AI 报告引用确定的数据点，并区分事实、推测和建议；
- PDF 导出建议后端生成，保证格式稳定并保留报告快照。

## 7. AI 助手的正确实现方式

AI 不是一个悬浮聊天框，而是业务编排层。每次请求携带结构化上下文：

```json
{
  "organization_id": "...",
  "shop_ids": ["..."],
  "page": "product-center",
  "time_range": { "from": "...", "to": "..." },
  "selected_entities": [{ "type": "sku", "id": "..." }],
  "filters": {},
  "visible_metrics": [],
  "allowed_tools": []
}
```

后端 AI Gateway 负责：

- 模型供应商适配、超时、重试、限流和成本统计；
- 提示词模板与版本管理；
- 调用只读数据工具获取最新事实；
- 把“建议”转为待确认任务，而不是直接执行高风险写操作；
- 保存输入数据版本、模型、输出和用户采纳结果，便于评估；
- 对订单聊天、买家信息和平台凭证做脱敏与权限控制。

## 8. 数据同步与一致性

推荐数据流：

```text
平台开放 API / Webhook
  → 平台连接器
  → 原始响应留档（可选、脱敏、限期保存）
  → 统一领域模型
  → 指标聚合 / 规则检测
  → 告警与任务
  → 前端查询 / AI 工具调用
```

关键规则：

- Webhook 与定时补偿拉取并行，避免只依赖单一机制；
- 写操作使用幂等键，防止用户重复点击或任务重试造成重复执行；
- 批量任务允许部分成功，不用一个 SKU 失败回滚全部；
- 指标显示 `data_updated_at`，操作显示 `platform_confirmed_at`；
- 高风险操作不做盲目乐观更新，以平台确认结果为准。

## 9. 目录结构建议

```text
root/
├─ frontend/
│  ├─ src/
│  │  ├─ app/                 # 启动、路由、权限、Provider
│  │  ├─ layouts/             # AppShell、侧栏、顶部栏
│  │  ├─ modules/
│  │  │  ├─ dashboard/
│  │  │  ├─ products/
│  │  │  ├─ orders/
│  │  │  ├─ campaigns/
│  │  │  ├─ assets/
│  │  │  └─ diagnostics/
│  │  ├─ components/          # 通用业务组件
│  │  ├─ composables/
│  │  ├─ stores/
│  │  ├─ api/                 # 生成客户端与 Query hooks
│  │  ├─ styles/              # tokens、theme、global
│  │  └─ types/
│  └─ tests/
├─ backend/
│  ├─ app/
│  │  ├─ api/v1/
│  │  ├─ core/
│  │  ├─ domains/
│  │  ├─ integrations/        # taobao/douyin/pdd
│  │  ├─ workers/
│  │  ├─ ai/
│  │  └─ models/
│  ├─ alembic/
│  └─ tests/
├─ infra/
│  ├─ docker/
│  └─ compose.yaml
├─ docs/
└─ PRODUCT.md
```


首版坚持模块化单体：六个页面共享用户、店铺、权限、任务和指标上下文，拆成微前端或微服务只会提前制造接口与部署成本。等团队、发布节奏或数据规模确实分化后再拆。

## 10. 实施顺序

### 阶段 A：基础骨架与契约

1. 初始化 Vue/FastAPI 工程、质量工具和 Docker 本地环境；
2. 建立 Design Tokens、自有组件层和 `AppShell`；
3. 定义组织、店铺、平台能力、任务、告警、指标等基础契约；
4. 建立 Mock API，让前端先按真实响应结构开发；
5. 完成登录、权限、店铺切换、全局搜索和消息告警壳层。

### 阶段 B：先打通两个代表性页面（演示页面已完成）

- [x] 商品中心：复杂筛选、表格、批量操作和详情抽屉；
- [x] 运营总览：指标聚合、任务优先级、图表和 AI 上下文；
- [ ] 打通一个真实平台的只读商品/订单同步：
  - [x] 淘宝服务端 OAuth state、Token 加密持久化、连接状态、断开连接；
  - [x] 淘宝卖家/店铺身份官方 API 客户端与 MockTransport 契约测试；
  - [ ] 使用真实淘宝应用凭证完成授权联调；
  - [ ] 商品/订单分页、游标、幂等增量同步。

### 阶段 C：风险操作闭环（演示闭环已完成）

- [x] 订单售后与服务端 SLA 告警、脱敏详情和 AI 回复草稿；
- [x] 商品批量上下架/改价与订单处置演示任务，支持幂等、进度、部分失败和重试；
- [x] 操作审计、能力矩阵与现有告警中心联动边界；
- [x] 将任务、审计和消息状态迁移到 SQLAlchemy/Alembic/Celery；正式配置支持 PostgreSQL + RabbitMQ + Redis，本地使用 SQLite + eager；
- [ ] 接入真实平台授权与平台确认结果：淘宝安全授权框架已完成，等待真实应用凭证联调与同步任务。

### 阶段 D：营销与素材

- [ ] 活动日历、冲突规则和复盘；
- [x] 素材 AI MVP：素材资产与版本、AI 厂商配置、模型发现、候选生成任务和人工确认边界；
- [x] 素材文件上传、版本元数据、local/MinIO 对象存储与登录后预览；
- [ ] 真实图片/视频文件生成、平台规则质检和跨平台分发任务。

### 阶段 E：诊断与报告

1. 指标口径与健康分；
2. 损失估算和问题排序；
3. AI 报告、PDF 导出和多店铺对比。

## 11. 验收标准

- 六页共享统一店铺/平台/时间上下文，切换后数据不会串店；
- 所有高风险和批量写操作可审计、可查看进度、可处理部分失败；
- 页面明确展示同步时间、估算值和平台能力限制；
- 表格筛选、排序、分页由服务端完成，典型数据量下交互稳定；
- AI 输出能引用当前页面的真实实体和指标，不生成不存在的数据；
- 核心流程有 Playwright 端到端测试；
- 视觉一致性由 Design Tokens 和业务组件层保证，而不是逐页复制样式。

## 12. 当前最需要避免的坑

1. 直接照六张图各写一套页面，导致导航、卡片、筛选器和抽屉六套实现；
2. 前端直接调用各平台开放 API，泄露凭证且无法统一审计；
3. 把全部接口数据塞进 Pinia，造成缓存和请求状态混乱；
4. 一开始就上微前端、微服务、Kubernetes、ClickHouse，拖慢首个闭环；
5. 假设所有平台都支持一键改价、回复、分发，忽略授权和能力差异；
6. 只做漂亮图表，不先建立指标口径、同步时间与问题优先级；
7. AI 直接执行高风险操作，没有确认、权限和审计；
8. 售后倒计时只在前端计算，刷新或休眠后出现时效错误。

## 0.1 评论与舆情页面进度（2026-09-13）

在真实平台联调暂缓期间，已先完成页面 5 的本地演示闭环：

- [x] 评论筛选：店铺范围、平台、监控商品、评价类型、工单状态和关键词搜索；
- [x] 评价明细：好评/中评/差评、星级、用户原话、平台和关键词标签；
- [x] 差评工单：打开/创建工单、指派成员、更新状态、保存回复草稿与跟进记录；
- [x] 舆情词云：按正向/中性/风险关键词聚合展示；
- [x] 评论模板库：好评感谢、包装破损、敏感不适等场景模板，可套用到工单草稿；
- [x] 统一复用店铺上下文、演示数据标识和“不会自动发送”的能力边界提示；
- [ ] 真实平台评论抓取、平台回复发送和 Webhook/增量同步；这些仍等待各平台凭证与官方联调环境。

对应演示 API：`GET /api/v1/reviews`、`POST /api/v1/reviews/tickets`。

## 0.2 报表与复盘中心进度（2026-09-13）

在真实平台联调暂缓期间，已先完成页面 6 的本地演示闭环：

- [x] 报表模板：日报、周报、月报、商品业绩、广告、售后六类模板；
- [x] 报表参数：统一店铺范围、模板切换、自定义指标和演示数据更新时间；
- [x] 在线预览：指标卡、趋势图、主体明细表与报表范围提示；
- [x] 导出任务（2026-10-12 升级为真实文件）：后端生成真实 Excel（指标概览/7日趋势/主体明细/口径与边界四 sheet）与 PDF（内置 CID 中文字体），文件落对象存储、导出记录落库、下载需登录（`tests/test_report_exports.py`）；
- [x] 复盘笔记：结论、后续行动与报表模板绑定，并记录作者和时间；
- [x] 前后端接口与权限：`GET /api/v1/reports`、`POST /api/v1/reports/exports`、`GET /api/v1/reports/exports/{id}/download`、`POST /api/v1/reports/notes`，权限为 `report:read`；
- [ ] 真实平台数据、异步 worker 生成大报表、细粒度权限控制；这些仍需在真实数据与生产基础设施阶段完成。

当前六个业务页面均已具备可操作的本地演示闭环；素材 AI 还新增了文件上传、对象存储和预览链路。下一阶段优先进行真实图片/视频生成适配与平台规则质检，但真实平台数据联调继续暂缓。

## 0.3 跨页面验收与端到端测试进度（2026-09-13）

已补充本地演示环境的 Playwright 关键路径验收：

- [x] 登录后进入运营总览；
- [x] 从总览进入报表与复盘中心；
- [x] 切换广告报表模板并验证趋势预览；
- [x] 发起 PDF 导出任务并验证演示反馈；
- [x] 创建复盘笔记并验证页面回显；
- [x] 验证六个已完成业务页面均出现在主导航；
- [x] 商品中心详情查看、商品勾选、批量同步确认和任务进度反馈；
- [x] 订单售后脱敏详情、AI 回复建议区域和可审计处置任务确认；
- [x] 评论舆情差评工单打开、回复草稿与跟进记录保存；
- [x] 店铺与平台切换后统一工作区范围更新，并支持保存常用店铺分组；
- [x] Playwright 默认复用本机 Chrome，避免依赖额外下载浏览器包；
- [x] 异常接口、空状态和批量任务失败重试测试，已由 `frontend/e2e/resilience.e2e.ts` 覆盖。

测试入口：`frontend/playwright.config.ts`、`frontend/e2e/critical-path.e2e.ts`、`frontend/e2e/module-flows.e2e.ts`、`frontend/e2e/assets-ai.e2e.ts`，运行命令：`npm run test:e2e`。

## 0.4 生产模式基础链路验收进度（2026-09-13）

在真实平台联调暂缓期间，已完成本地生产配置的可重复验收：

- [x] Docker PostgreSQL、Redis、RabbitMQ 核心依赖健康运行；
- [x] Alembic 迁移版本 `20260913_0004 (head)` 已应用；
- [x] 生产 API 使用 PostgreSQL 且关闭 Celery eager；
- [x] Windows `solo` Celery Worker 已连接 RabbitMQ，并注册商品/订单任务；
- [x] 商品异步任务：API 创建、数据库落库、RabbitMQ 投递、Worker 执行、数据库回写；
- [x] 订单异步处置：部分成功结果和订单审计记录持久化；
- [x] 告警已读状态写入、读取和恢复；
- [x] 新增 `backend/scripts/production_smoke.py`，可重复执行上述验收；
- [x] 补充 API 重启后重新读取任务状态的验收流程；
- [x] 任务超时、自动重试、死信队列、监控告警（2026-10-12，见 0.10 节）；
- [ ] 商品/订单主数据落库、增量同步和正式组织数据隔离；
- [x] MinIO 对象存储已实现并完成本地容器烟囱测试；
- [ ] 真实 Excel/PDF 文件生成。

当前结论：项目已从“本地 Demo 闭环”推进到“本地生产模式基础设施可验收”，但商品、订单、评论、广告和报表主数据仍是明确标注的演示数据，真实平台尚未接入。

## 0.5 素材 AI 中心与模型配置进度（2026-09-14）

在真实电商平台联调继续暂缓的前提下，已完成素材生产链路的第一阶段，并把模型接入独立成可配置入口：

- [x] 素材资产、版本、生成任务、质检记录和分发任务的 SQLAlchemy 模型与 Alembic 迁移 `20260913_0004`；
- [x] 素材 AI 中心页面：素材目录、生成目标、输出类型、模型选择、任务进度、版本预览和人工确认边界；
- [x] AI 模型配置页面：OpenAI、Anthropic、Gemini、Ollama、自定义 OpenAI 兼容厂商和演示 Provider；
- [x] 选择厂商后自动填充默认 Base URL，API Key 只提交到后端并使用 Fernet 加密保存，接口只返回掩码；
- [x] 测试连接并按厂商协议拉取可用模型：OpenAI-compatible `/models`、Anthropic `/v1/models`、Gemini `/models`、Ollama `/api/tags`；
- [x] 默认模型选择、配置启停、删除和连接失败状态反馈；
- [x] Mock Provider 生成任务已通过生产 API + RabbitMQ + Celery Worker 验证，结果生成新版本且状态为待确认；
- [x] 素材版本确认接口：幂等地切换当前版本、更新素材状态并写入审计，仍不自动分发；
- [x] OpenAI-compatible、Anthropic、Gemini、Ollama 文本生成适配器与 HTTP Mock 测试；真实调用默认由 `AI_LIVE_GENERATION_ENABLED=false` 保护；
- [x] Playwright 覆盖“进入素材 AI → 配置演示模型 → 拉取 3 个模型 → 选择默认模型 → 生成候选素材”的关键路径；
- [x] Playwright 使用独立的 `8100/5174` 端口、隔离测试库和素材目录，并覆盖“页面上传文本素材 → 待确认/待质检 → 鉴权预览 → 未登录拒绝”的文件链路；
- [x] 素材文件上传、local/MinIO 对象存储、版本对象元数据和登录后预览；
- [ ] 真实图片/视频文件生成、平台尺寸/敏感词/版权质检；
- [ ] 素材确认后的跨平台分发、组织级密钥轮换审计和真实平台联调。

当前结论：素材 AI 已从“尚未开始”推进到“可配置、可发现模型、可生成候选版本并人工确认的 MVP”；真实文本模型适配器已具备，但默认关闭。图片/视频文件生成、真实质检和平台分发仍作为后续独立阶段接入，AI 不自动发布、不自动改价、不自动覆盖线上素材。
