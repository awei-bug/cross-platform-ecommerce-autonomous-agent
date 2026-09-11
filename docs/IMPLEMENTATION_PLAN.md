# 一站式多平台电商运营 AI 工作台：整体实现方案

> 状态：阶段 A 基础骨架已完成，下一步进入阶段 B 商品中心
> 日期：2026-09-11
> 基线：六张参考图与用户提供的业务说明是产品和视觉依据；当前仓库已完成阶段 A 工程化落地。

## 0. 实施状态（2026-09-11）

阶段 A 已完成并验证：

- 前端 Vue 3 / TypeScript / Vite、后端 FastAPI / Pydantic 工程；
- Design Tokens、固定侧栏、顶部全局栏、店铺工作区；
- 演示登录、Bearer 鉴权、路由权限守卫；
- 组织、店铺、指标、告警、平台能力矩阵和搜索契约；
- 跨店铺搜索、告警轮询、店铺切换与六模块路由；
- Vitest、ESLint、Prettier、Pytest、Ruff 和 Docker Compose 基础设施定义。

下一实施单元为阶段 B：先建立商品中心业务组件模板，再完成正式运营总览。
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

| 层级 | 推荐选型 | 使用方式 |
|---|---|---|
| 框架 | Vue 3 + TypeScript + `<script setup>` | 六个业务域按模块拆分 |
| 构建 | Vite | SPA、按路由懒加载、环境配置 |
| 路由 | Vue Router | 路由元信息承载权限、菜单、面包屑、页面标题 |
| 客户端状态 | Pinia | 用户、组织、店铺上下文、全局 UI 状态 |
| 服务端状态 | TanStack Vue Query | 请求缓存、失效刷新、轮询、分页、Mutation 状态 |
| 基础组件 | Element Plus | 表单、弹窗、抽屉、分页、日期、表格基础能力 |
| 设计系统 | CSS Variables + SCSS + 自有组件封装 | 不直接在业务页散落 Element Plus 样式覆盖 |
| 图表 | Apache ECharts | 趋势、漏斗、饼图、利润、广告与诊断图表 |
| 日期 | Day.js | 时间范围、活动日历、售后倒计时 |
| API | 基于 FastAPI OpenAPI 生成 TypeScript Client | API 类型由后端契约生成，减少手写漂移 |
| 单元/组件测试 | Vitest + Vue Test Utils | 领域函数、composables、复杂组件 |
| 端到端测试 | Playwright | 登录、切店、筛选、批量操作、抽屉、任务进度 |
| Mock | Mock Service Worker 或本地 mock adapter | 后端未完成前并行开发页面 |

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

| 层级 | 推荐选型 | 责任 |
|---|---|---|
| Web API | FastAPI + Pydantic | REST API、鉴权、校验、OpenAPI 契约、AI 流式响应 |
| ORM/迁移 | SQLAlchemy 2.x + Alembic | 数据访问与数据库版本迁移 |
| 主数据库 | PostgreSQL | 组织、店铺、商品、订单、活动、任务、规则、审计 |
| 缓存/锁 | Redis | 热点缓存、分布式锁、幂等键、短期任务状态 |
| 异步任务 | Celery + RabbitMQ（生产） | 同步、批量动作、报表、AI、图像和素材处理 |
| 定时任务 | Celery Beat | 周期拉取、巡检、预警、日报周报 |
| 对象存储 | MinIO（本地）/S3 兼容服务（生产） | 图片、视频、导出文件、报告 PDF |
| 实时反馈 | SSE 优先，必要时 WebSocket | 告警、任务进度、AI 流式输出 |
| 可观测性 | OpenTelemetry + 日志/指标平台 | 请求链路、同步任务、平台错误和 AI 成本 |
| 部署 | Docker Compose 起步，Nginx/网关统一入口 | 本地、测试、首版生产部署 |

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
  "time_range": {"from": "...", "to": "..."},
  "selected_entities": [{"type": "sku", "id": "..."}],
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

### 阶段 B：先打通两个代表性页面

1. 商品中心：验证复杂筛选、表格、批量操作和详情抽屉；
2. 运营总览：验证指标聚合、任务优先级、图表和 AI 上下文；
3. 打通一个真实平台的只读商品/订单同步，验证统一模型。

### 阶段 C：风险操作闭环

1. 订单售后与 SLA 告警；
2. 批量上下架/改价等异步任务；
3. 操作审计、失败重试、能力矩阵和消息中心。

### 阶段 D：营销与素材

1. 活动日历、冲突规则和复盘；
2. 素材库、对象存储、AI 生成、质检和分发任务。

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
