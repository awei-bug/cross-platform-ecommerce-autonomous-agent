# 公开竞品浏览器采集

已实现并在本机实测：浏览器打开公开热销榜和商品页面 → 保存当前规格/价格/币种/来源/采集时间及截图 SHA256 → 入库跨境数据中台 → 费用假设下的成本空间分析。无需店铺、淘宝客凭证或付费模型。

首批真实结果见 [美国家居热销样本](research/2026-10-15-US-HOT-PRODUCTS.md)。页面入口为「跨境智能体中枢 → 数据中台 → 公开竞品与热销证据」，已写入日常使用的 `backend/data/ops_workbench.db`。

## 重复执行

先用项目的一键启动入口启动服务。在 `frontend` 目录执行：

```powershell
# 只采集，不写数据库；结果目录会自动按时间建立，保留历史截图。
node scripts/collect-competitors.mjs --manifest ../research/us-bestsellers.example.json

# 同时导入当前本机项目并生成分析。当前项目为演示登录，token 为现有鉴权机制。
$env:ECOMOPS_TOKEN = 'demo-access-token'
node scripts/collect-competitors.mjs --manifest ../research/us-bestsellers.example.json --api http://127.0.0.1:8011
```

增加 `--headed` 可观察新开的浏览器窗口。系统依次寻找 `--executable-path`、`RESEARCH_BROWSER_PATH`、系统 Chrome、Edge，否则使用 Playwright 自带 Chromium。采用独立浏览器上下文，不复用用户账号登录。

`research/us-bestsellers.example.json` 中的 URL 是此次从榜单筛出的固定候选链接。再次运行会刷新这些候选的页面及其当前榜单位置，**不会自动把固定清单替换成当天最热的商品**。扩大品类时先浏览相应公开榜单，再更新清单；榜单按站点/品类解释。

支持两类页面：美国 Amazon 商品详情的当前 ASIN 与可见主售价，以及只有一个 schema.org Product、一个明确 Offer 的公开商品页（已用 IKEA 美国站验证结构）。未对所有电商网站承诺通用解析。`research/us-storage.example.json` 仅为普通商品解析样例，没有热销依据。

## 产出与使用

默认结果目录：`backend/data/research/<collection_id>/<时间>/`。

- `observations.json`：可通过界面选择文件导入；最多50页/批。
- `rankings.json`、`rank-*.png`：榜单位置及对应卡片截图。
- 商品截图：采集时页面；截图 SHA256 用于后续文件比对，不代表第三方认证。
- `failures.json`：失败页面及原因，不用估计值补齐。
- `import-result.json`、`analysis.json`：提供 `--api` 时生成；包含新增/更新数量、币种隔离、费用假设、排除项及成本上限。
- `report.md`：本次可读结果；原始证据留在同一目录，不提交本机数据库和截图到 Git。

重复导入同一组织/批次/国家/来源 URL 更新同一条记录，历史原始文件保留。采集清单应保留一致的商品 URL，避免更换跟踪参数产生重复记录。跨境选品任务可选「竞品采集批次」，也可提交 `input.research_collection_id`；市场步骤只读取匹配该组织、批次、国家和币种的非演示证据。

接口沿用现有鉴权与权限：

- `POST /api/v1/ecomops/research/import`：`ResearchBatch`，要求 `automation:manage`，整批校验后入库并审计。
- `GET /api/v1/ecomops/research/collections`：当前组织的采集批次。
- `POST /api/v1/ecomops/research/analyze`：批次、国家、币种及佣金/广告/毛利假设；不要求初始化任务，不依赖店铺。

服务端不抓取外部 URL；采集由本机浏览器执行。导入文件是用户提供的证据，服务端校验字段与格式，不独立证明页面真实性。不读取/保存完整评论作者数据。

## 判断边界

热销排名是采集时该品类的榜单位置，不是增长速度、新品机会或精确销量。`90K+ bought in past month` 等保留为平台页面声明，不换算成销量数字。不会据榜单自动生成市场评分。

价格只取商品当前主报价，不用划线价、二手价、其他变体价、聚合最低价替代。缺少明确价格时仍保留商品证据，但不参与成本测算。遇到验证码、登录或访问拦截时记录失败；不绕过验证。

成本上限＝页面售价×（1－佣金率－广告率－目标毛利率）。它须覆盖采购、全程物流、税费、平台履约、包装、仓储与售后损耗等全部非比例单件成本；不等于可用于采购的金额。价格不是建议售价，费率不是已核验的平台报价。相框和浴帘不能当作同规格产品比较均价。

原有跨境选品综合评分仍基于人工参数/默认分数，本次未把它改造成销量预测。浏览器证据补全调研与成本筛查，不证明候选可以盈利，也不代替专利、商标、认证核验。

验收包括后端组织/币种/批次隔离与整批校验，解析器价格歧义测试，界面文件导入/重算/来源链接/手机布局，以及实际外网页面采集和日常库入库；测试样本与外网真实采集分开保存。

前端解析器用 `pnpm test:research` 运行；原有单测用 `CI=true pnpm test`。Node原生测试文件使用 `.checks.mjs` 后缀，避免被 Vitest 的浏览器环境误收集。浏览器验收使用 `CI=true pnpm test:e2e e2e/browser-research.e2e.ts e2e/ecomops.e2e.ts --workers=1 --retries=0 --output=test-results/browser-research-confirmed`，沿用既有脚本清理隔离测试库，保留日常数据库和其他证据目录。

采集退出码0表示价格/币种与所要求榜单均完成；部分失败或必需字段缺失返回2，已成功采集的证据仍保存，分析会排除无效价格记录。

本次验收：后端153项测试及ruff通过；前端lint/build、10项原有单测、5项解析器测试、3项浏览器闭环通过。实际外网采集3页、日常库新增3条，重复导入更新3条且新增0条。开发服务器在原有窗口缩放用例仍出现 ResizeObserver 通知警告，构建仍有大包提示；没有把这些警告表述为“控制台完全干净”。
