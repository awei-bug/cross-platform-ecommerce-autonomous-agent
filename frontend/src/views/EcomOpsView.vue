<script setup lang="ts">
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, createCommentVNode, nextTick, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ecomApi, type EcomPolicy, type EcomRun, type EcomTask } from '../api/ecomops'
import BrowserResearchPanel from '../components/business/BrowserResearchPanel.vue'
import { useSessionStore } from '../stores/session'

const session = useSessionStore()
const route = useRoute()
const client = useQueryClient()
const tab = ref(route.query.tab === 'policy' ? 'policy' : 'workflows')
const busy = ref(false)
const drawer = ref(false)
const createOpen = ref(false)
const createStep = ref(0)
const managementNote = ref('')
const reviewTaskId = ref('')
const expandedTasks = ref<string[]>([])
const selectedId = ref('')
const filter = ref('all')
const workflow = ref('initialization')
const title = ref('')
const sku = ref('')
const productTitle = ref('')
const content = ref('')
const price = ref(30)
const procurement = ref(8)
const quantity = ref(100)
const platform = ref('amazon')
const country = ref('US')
const language = ref('en')
const useAi = ref(false)
const researchCollectionId = ref('')
const advancedInput = ref('{}')
const policyDraft = ref<EcomPolicy>()
const policyVersion = ref(0)
const rulesDraft = ref('[]')
const interventionNote = ref('')
const priority = ref(5)
const scheduleHours = ref(24)
const importText = ref('')
const business = reactive({
  freight: 0,
  tax: 0,
  loss: 0,
  commission_pct: 15,
  ad_rate_pct: 10,
  budget_before: 100,
  budget_after: 100,
  ad_spend: 0,
  service_intent: 'consultation',
  refund_amount: 0,
  order_key: '',
  destination_address: '',
  stock: 100,
  safety_stock: 20,
  daily_sales: 5,
  lead_days: 14,
  tracking_status: 'unknown',
})
const workflowFields = computed(() => {
  const fields: Record<string, string[]> = {
    selection: ['freight', 'tax', 'loss', 'commission_pct', 'ad_rate_pct'],
    marketing: ['budget_before', 'budget_after', 'ad_spend'],
    service: ['service_intent', 'refund_amount', 'order_key'],
    fulfillment: [
      'order_key',
      'destination_address',
      'stock',
      'safety_stock',
      'daily_sales',
      'lead_days',
      'tracking_status',
    ],
  }
  return fields[workflow.value] ?? []
})
const extraBusinessInput = computed(() =>
  Object.fromEntries(
    Object.entries(business).filter(([key]) => workflowFields.value.includes(key)),
  ),
)
const reviews = computed(
  () => detail.value?.tasks?.filter((task) => task.status === 'waiting_review') ?? [],
)
const reviewTask = computed(
  () => reviews.value.find((task) => task.id === reviewTaskId.value) ?? reviews.value[0],
)
const runSearch = ref('')
const needsAttention = (run: EcomRun) =>
  [
    'waiting_review',
    'waiting_data',
    'waiting_integration',
    'waiting_initialization',
    'failed',
    'dead_letter',
    'terminated',
    'taken_over',
  ].includes(run.status)
const runCounts = computed(() => ({
  attention: overview.value?.runs.filter(needsAttention).length ?? 0,
  running:
    overview.value?.runs.filter((run) => ['queued', 'pending', 'running'].includes(run.status))
      .length ?? 0,
  completed: overview.value?.runs.filter((run) => run.status === 'succeeded').length ?? 0,
}))
const DesignContract = () =>
  createCommentVNode(`
THESIS: 直接处置任务依赖、风险和执行证据。
OWN-WORLD: 现有浅蓝工作区、白色台账、深蓝侧栏和 Element Plus 原语。
STORY: 导入数据，初始化，提交业务，审核并追溯。
FIRST VIEWPORT: 待办与任务台账为主，新建入口常驻，流程说明按需查看。
FORM: 现有 Operate 工作台扩展，保留全局视觉规范。
`)

const overviewQuery = useQuery({
  queryKey: ['ecomops', 'overview'],
  queryFn: () => ecomApi.overview(session.token!),
  refetchInterval: 5000,
})
const overview = computed(() => overviewQuery.data.value)
const detailQuery = useQuery({
  queryKey: ['ecomops', 'run', selectedId],
  queryFn: () => ecomApi.run(session.token!, selectedId.value),
  enabled: computed(() => Boolean(selectedId.value)),
  refetchInterval: 3000,
})
const detail = computed(() => detailQuery.data.value)
watch(
  () => route.query.tab,
  (value) => {
    if (value === 'policy') tab.value = 'policy'
  },
)
watch(
  () => detail.value?.id,
  () => {
    expandedTasks.value =
      detail.value?.tasks
        ?.filter((task) =>
          ['failed', 'waiting_data', 'waiting_integration', 'running'].includes(task.status),
        )
        .map((task) => task.id) ?? []
  },
)
watch(
  () => reviewTask.value?.id,
  () => {
    interventionNote.value = ''
  },
)
const recordsQuery = useQuery({
  queryKey: ['ecomops', 'data'],
  queryFn: () => ecomApi.records(session.token!),
  enabled: computed(() => tab.value === 'data'),
})
const researchCollectionsQuery = useQuery({
  queryKey: ['ecomops', 'research-collections'],
  queryFn: () => ecomApi.researchCollections(session.token!),
  enabled: computed(() => createOpen.value && workflow.value === 'selection'),
})
const schedulesQuery = useQuery({
  queryKey: ['ecomops', 'schedules'],
  queryFn: () => ecomApi.schedules(session.token!),
  enabled: computed(() => tab.value === 'iteration'),
})
const performanceQuery = useQuery({
  queryKey: ['ecomops', 'performance'],
  queryFn: () => ecomApi.performance(session.token!),
  enabled: computed(() => tab.value === 'iteration'),
})
const visibleRuns = computed(() =>
  (overview.value?.runs ?? []).filter(
    (r) =>
      (filter.value === 'all' ||
        (filter.value === 'review' && r.status === 'waiting_review') ||
        (filter.value === 'attention' && needsAttention(r)) ||
        (filter.value === 'running' && ['queued', 'pending', 'running'].includes(r.status)) ||
        (filter.value === 'completed' && r.status === 'succeeded')) &&
      `${r.title} ${workflowName(r.workflow)}`
        .toLowerCase()
        .includes(runSearch.value.trim().toLowerCase()),
  ),
)
const names: Record<string, string> = {
  queued: '已排队',
  pending: '待依赖完成',
  running: '执行中',
  succeeded: '已完成',
  waiting_review: '待人工审核',
  waiting_data: '等待补充数据',
  waiting_integration: '等待平台接入',
  waiting_initialization: '等待初始化',
  terminated: '高风险熔断',
  rejected: '已驳回',
  taken_over: '人工接管',
  cancelled: '已取消',
  failed: '执行失败',
  dead_letter: '重试耗尽',
}
function statusName(status: string) {
  return names[status] ?? status
}
function statusType(status: string) {
  if (status === 'succeeded') return 'success'
  if (['terminated', 'failed', 'dead_letter', 'rejected'].includes(status)) return 'danger'
  if (['waiting_review', 'waiting_data', 'waiting_integration'].includes(status)) return 'warning'
  return 'info'
}
function agentName(id: string) {
  return overview.value?.agents.find((a) => a.id === id)?.name ?? id
}
function workflowName(id: string) {
  if (id === 'iteration' || id === 'expansion') return '已停用的历史流程'
  return overview.value?.workflows.find((w) => w.id === id)?.name ?? id
}
function dependencyNames(keys: string[]) {
  const steps = overview.value?.workflows.find((item) => item.id === workflow.value)?.steps
  return keys.map((key) => steps?.find((step) => step.key === key)?.title ?? key).join('、')
}
function formatTime(value: string) {
  return dayjs(value).format('MM-DD HH:mm:ss')
}
function openRun(run: EcomRun) {
  interventionNote.value = ''
  managementNote.value = ''
  reviewTaskId.value = ''
  priority.value = run.priority
  selectedId.value = run.id
  drawer.value = true
}
function openCreate() {
  createStep.value = 0
  createOpen.value = true
}
function openData() {
  createOpen.value = false
  tab.value = 'data'
}
function blockingReason(run: EcomRun) {
  return (
    run.tasks?.find((task) => task.reason && task.status !== 'succeeded')?.reason ??
    statusName(run.status)
  )
}
function reviewFacts(task: EcomTask): Array<{ label: string; value: string | number }> {
  return Array.isArray(task.output.review_facts) ? task.output.review_facts : []
}
async function showReviews() {
  tab.value = 'workflows'
  filter.value = 'review'
  await nextTick()
  document.getElementById('runs-title')?.scrollIntoView({ block: 'center' })
}
async function copyRun() {
  const run = detail.value
  if (!run?.input || !overview.value?.workflows.some((w) => w.id === run.workflow)) return
  const input = run.input
  workflow.value = run.workflow
  title.value = `${run.title.slice(0, 190)}（修订）`
  sku.value = String(input.sku ?? '')
  productTitle.value = String(input.title ?? '')
  content.value = String(input.content ?? '')
  price.value = Number(input.price ?? 0)
  procurement.value = Number(input.procurement ?? 0)
  quantity.value = Number(input.quantity ?? 1)
  platform.value = String(input.platform ?? 'amazon')
  country.value = String(input.country ?? 'US')
  language.value = String(input.language ?? 'en')
  useAi.value = Boolean(input.use_ai)
  researchCollectionId.value = String(input.research_collection_id ?? '')
  const basicFields = new Set([
    'sku',
    'platform',
    'title',
    'content',
    'price',
    'procurement',
    'quantity',
    'country',
    'language',
    'use_ai',
    'research_collection_id',
    ...Object.keys(business),
  ])
  for (const key of Object.keys(business) as Array<keyof typeof business>) {
    if (input[key] !== undefined && input[key] !== '***') {
      Object.assign(business, { [key]: input[key] })
    } else if (key === 'destination_address') business.destination_address = ''
  }
  const extra = Object.fromEntries(
    Object.entries(input).filter(([k, v]) => !basicFields.has(k) && v !== '***'),
  )
  advancedInput.value = JSON.stringify(extra, null, 2)
  drawer.value = false
  tab.value = 'workflows'
  openCreate()
  ElMessage.info('已复制可见参数。请修订缺失信息后提交新任务，脱敏地址需重新填写。')
}
function isActive(run: EcomRun) {
  return !['succeeded', 'cancelled', 'terminated', 'rejected'].includes(run.status)
}
async function action(work: () => Promise<unknown>, message: string) {
  if (busy.value) return
  busy.value = true
  try {
    await work()
    ElMessage.success(message)
    await client.invalidateQueries({ queryKey: ['ecomops'] })
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '操作失败，请重试')
  } finally {
    busy.value = false
  }
}
async function createRun() {
  await action(async () => {
    const extra = JSON.parse(advancedInput.value)
    if (!extra || Array.isArray(extra) || typeof extra !== 'object')
      throw new Error('补充参数必须是 JSON 对象')
    const run = await ecomApi.create(session.token!, {
      workflow: workflow.value,
      title: title.value.trim() || workflowName(workflow.value),
      idempotency_key: crypto.randomUUID(),
      input: {
        use_ai: useAi.value,
        ...(workflow.value === 'selection'
          ? { research_collection_id: researchCollectionId.value }
          : {}),
        sku: sku.value,
        platform: platform.value,
        title: productTitle.value,
        content: content.value,
        price: price.value,
        procurement: procurement.value,
        quantity: quantity.value,
        country: country.value,
        language: language.value,
        ...extraBusinessInput.value,
        ...extra,
      },
    })
    createOpen.value = false
    filter.value = 'all'
    runSearch.value = ''
    tab.value = 'workflows'
    openRun(run)
  }, '任务已提交，执行状态已保存')
}
async function intervene(kind: string, task?: EcomTask, note = interventionNote.value) {
  if (note.trim().length < 2) {
    ElMessage.warning('请填写至少两个字的处理依据，便于审计追溯')
    return
  }
  await action(async () => {
    const updated = await ecomApi.intervene(session.token!, selectedId.value, {
      action: kind,
      review_version: detail.value?.config_version,
      task_id: task?.id,
      note: note.trim(),
      priority: priority.value,
    })
    interventionNote.value = ''
    managementNote.value = ''
    priority.value = updated.priority
    return updated
  }, '干预操作已保存到审计记录')
}
function editPolicy() {
  if (!overview.value) return
  policyDraft.value = JSON.parse(JSON.stringify(overview.value.configuration.payload)) as EcomPolicy
  policyVersion.value = overview.value.configuration.version
  rulesDraft.value = JSON.stringify(policyDraft.value.rules, null, 2)
}
async function savePolicy() {
  if (!policyDraft.value) return
  await action(async () => {
    const rules = JSON.parse(rulesDraft.value)
    if (!Array.isArray(rules)) throw new Error('规则必须是 JSON 数组')
    await ecomApi.configure(session.token!, policyVersion.value, { ...policyDraft.value!, rules })
    policyDraft.value = undefined
  }, '规则已保存为新版本，后续执行会重新校验审批')
}
async function importData() {
  await action(async () => {
    const records = JSON.parse(importText.value)
    if (!Array.isArray(records)) throw new Error('请导入 JSON 记录数组')
    const result = await ecomApi.import(session.token!, records)
    ElMessage.info(`新增 ${result.inserted}，更新 ${result.updated}，去重 ${result.deduplicated}`)
  }, '共享数据已入库')
}
function fillExample() {
  importText.value = JSON.stringify(
    [
      {
        kind: 'product',
        key: 'DEMO-SKU-01',
        data: { title: '便携收纳盒', currency: 'USD' },
        source: '人工演示样例',
        is_demo: true,
      },
      {
        kind: 'supplier',
        key: 'DEMO-SUPPLIER-01',
        data: { name: '演示供应商' },
        source: '人工演示样例',
        is_demo: true,
      },
      {
        kind: 'competitor',
        key: 'DEMO-COMP-01',
        data: { title: '同类收纳盒', price: 29, pain_points: ['尺寸说明不足'] },
        source: '人工演示样例',
        is_demo: true,
      },
      {
        kind: 'metric',
        key: 'DEMO-2026-10',
        data: {
          currency: 'USD',
          revenue: 3000,
          cost: 1600,
          orders: 100,
          ad_spend: 500,
          refunds: 5,
          customers: 90,
          repeat_customers: 10,
          visits: 2000,
          conversions: 100,
        },
        source: '人工演示样例，独立指标区间',
        is_demo: true,
      },
    ],
    null,
    2,
  )
}
</script>

<template>
  <section class="ecomops" aria-labelledby="ecom-title">
    <DesignContract />
    <!-- THESIS: 让运营人员看到任务依赖、风险与执行证据，并直接处理阻塞。
         OWN-WORLD: 延续现有浅蓝工作区、白色台账、深蓝侧栏与 Element Plus 原语。
         STORY: 导入基础数据，初始化，提交业务任务，审核并追溯。
         FIRST VIEWPORT: 左标题右刷新，运行边界提示，下方阶段页签和任务提交表单。
         FORM: 现有 Operate 工作台扩展；无独立视觉世界替换。 -->
    <header class="page-heading">
      <div>
        <h1 id="ecom-title">跨境多智能体运营中枢</h1>
        <p>从选品到履约，按任务依赖推进；风险、审批与执行证据全程可追踪。</p>
      </div>
      <div class="heading-actions">
        <el-button
          :loading="overviewQuery.isFetching.value"
          @click="client.invalidateQueries({ queryKey: ['ecomops'] })"
          >刷新状态</el-button
        >
        <el-button type="primary" :disabled="!overview" @click="openCreate">新建任务</el-button>
      </div>
    </header>
    <el-alert
      v-if="overviewQuery.isError.value"
      title="工作台加载失败，请刷新状态重试"
      type="error"
      show-icon
      :closable="false"
    />
    <div v-if="overviewQuery.isPending.value" aria-live="polite">
      <el-skeleton :rows="6" animated />
    </div>
    <template v-if="overview">
      <div class="environment-summary">
        <el-tag type="warning">本地沙盒</el-tag>
        <span>当前为本地沙盒流程，跨境平台尚未接入</span>
        <details>
          <summary>运行边界</summary>
          <p>
            可运行本地计算、草稿、内部工单和人工审批。上架、投放、退款与出库须等待官方连接器，不产生真实平台操作。
          </p>
        </details>
      </div>
      <div class="readiness" role="status">
        <span
          >基础初始化：<strong>{{
            overview.initialization_ready ? '已完成（沙盒）' : '待完成'
          }}</strong></span
        >
        <span>生产接入：<strong>待接入验证</strong></span>
        <span
          >规则版本：<strong>v{{ overview.configuration.version }}</strong></span
        >
        <button type="button" class="review-shortcut" @click="showReviews">
          查看待审核
          <strong>{{ overview.runs.filter((r) => r.status === 'waiting_review').length }}</strong>
        </button>
      </div>
      <el-tabs v-model="tab" class="surface">
        <el-tab-pane label="任务协同" name="workflows">
          <section class="run-panel" aria-labelledby="runs-title">
            <div class="section-heading">
              <div>
                <h2 id="runs-title">任务台账</h2>
                <p class="helper">
                  待处理 {{ runCounts.attention }} · 进行中 {{ runCounts.running }} · 已完成
                  {{ runCounts.completed }}
                </p>
              </div>
              <div class="run-filters">
                <el-input
                  v-model="runSearch"
                  clearable
                  aria-label="搜索运营任务"
                  placeholder="搜索任务名称或流程"
                />
                <el-select v-model="filter" aria-label="任务状态筛选">
                  <el-option value="all" label="全部任务" />
                  <el-option value="attention" label="待我处理" />
                  <el-option value="review" label="待人工审核" />
                  <el-option value="running" label="进行中" />
                  <el-option value="completed" label="已完成" />
                </el-select>
              </div>
            </div>
            <div class="desktop-runs">
              <el-table
                :data="visibleRuns"
                row-key="id"
                empty-text="没有符合条件的任务，可调整筛选或新建任务。"
                @row-click="openRun"
              >
                <el-table-column prop="title" label="任务 / 流程" min-width="220"
                  ><template #default="{ row }"
                    ><button type="button" class="task-link" @click.stop="openRun(row)">
                      {{ row.title }}
                    </button>
                    <div class="helper">{{ workflowName(row.workflow) }}</div></template
                  ></el-table-column
                >
                <el-table-column label="执行状态" min-width="150"
                  ><template #default="{ row }"
                    ><el-tag :type="statusType(row.status)">{{
                      statusName(row.status)
                    }}</el-tag></template
                  ></el-table-column
                >
                <el-table-column prop="priority" label="优先级" width="80" />
                <el-table-column label="提交时间" width="150"
                  ><template #default="{ row }">{{
                    formatTime(row.created_at)
                  }}</template></el-table-column
                >
                <el-table-column label="操作" width="120"
                  ><template #default="{ row }"
                    ><el-button link type="primary" @click.stop="openRun(row)"
                      >查看详情</el-button
                    ></template
                  ></el-table-column
                >
              </el-table>
            </div>
            <div class="mobile-runs">
              <button
                v-for="run in visibleRuns"
                :key="run.id"
                type="button"
                class="run-card"
                @click="openRun(run)"
              >
                <span class="run-card__top"
                  ><strong>{{ run.title }}</strong
                  ><el-tag :type="statusType(run.status)" size="small">{{
                    statusName(run.status)
                  }}</el-tag></span
                >
                <span class="helper">{{ workflowName(run.workflow) }}</span>
                <span v-if="needsAttention(run)" class="run-card__reason">{{
                  blockingReason(run)
                }}</span>
                <span class="run-card__meta"
                  >优先级 {{ run.priority }} · {{ formatTime(run.created_at) }}
                  <span>查看详情 ›</span></span
                >
              </button>
              <el-empty v-if="!visibleRuns.length" description="没有符合条件的任务" />
            </div>
            <div v-if="!overview.runs.length" class="empty-start">
              <p>先导入基础数据，再新建初始化任务，建立协同基础。</p>
              <el-button @click="tab = 'data'">导入基础数据</el-button
              ><el-button type="primary" @click="openCreate">新建任务</el-button>
            </div>
          </section>
        </el-tab-pane>
        <el-tab-pane label="数据中台" name="data">
          <BrowserResearchPanel v-if="tab === 'data'" />
          <h2>共享数据导入</h2>
          <p>
            产品编码自动去空格并大写；按组织、类型和编码去重。指标请导入不重叠的 USD
            汇总区间，并在来源中保留汇率依据。
          </p>
          <div class="data-counts">
            <span v-for="(count, kind) in overview.data_counts" :key="kind"
              >{{ kind }} <strong>{{ count }}</strong></span
            >
          </div>
          <label for="data-import">记录数组（kind、key、data、source、is_demo）</label>
          <el-input
            id="data-import"
            v-model="importText"
            type="textarea"
            :rows="9"
            placeholder="粘贴带来源的 JSON 数据数组"
          />
          <div class="actions">
            <el-button
              type="primary"
              :loading="busy"
              :disabled="!importText.trim()"
              @click="importData"
              >校验并导入</el-button
            ><el-button @click="fillExample">填入演示样例</el-button>
          </div>
          <el-alert
            v-if="recordsQuery.isError.value"
            title="数据读取失败，请刷新重试"
            type="error"
            :closable="false"
          />
          <el-table :data="recordsQuery.data.value ?? []" empty-text="尚无共享数据"
            ><el-table-column prop="kind" label="数据类型" width="120" /><el-table-column
              prop="key"
              label="标准编码"
              min-width="180"
            /><el-table-column prop="source" label="数据来源" min-width="220" /><el-table-column
              label="真实性"
              width="120"
              ><template #default="{ row }"
                ><el-tag :type="row.is_demo ? 'warning' : 'info'">{{
                  row.is_demo
                    ? '演示数据'
                    : row.source.startsWith('browser_public:')
                      ? '公开页面采集'
                      : '人工导入'
                }}</el-tag></template
              ></el-table-column
            ></el-table
          >
        </el-tab-pane>
        <el-tab-pane label="角色与平台" name="roles">
          <h2>一个总调度、八个核心业务角色与两个基础服务角色</h2>
          <el-table :data="overview.agents"
            ><el-table-column prop="name" label="智能体" width="210" /><el-table-column
              prop="responsibility"
              label="职责边界"
              min-width="280"
          /></el-table>
          <h3>跨境平台接入状态</h3>
          <p>
            现有国内平台连接器继续可用。下列平台必须分别完成官方适配、资质授权、六类数据同步及故障重连验证。
          </p>
          <el-table :data="overview.platforms"
            ><el-table-column prop="name" label="平台" width="150" /><el-table-column
              prop="message"
              label="接入边界"
              min-width="320"
            /><el-table-column label="官方文档" width="120"
              ><template #default="{ row }"
                ><a :href="row.official_docs" target="_blank" rel="noopener"
                  >查看文档 ↗</a
                ></template
              ></el-table-column
            ></el-table
          >
        </el-tab-pane>
        <el-tab-pane label="风控与授权" name="policy">
          <div class="section-heading">
            <div>
              <h2>分级风控与强制复核阈值</h2>
              <p>低风险自动修正并留痕；中风险暂停审核；高风险终止任务。金额统一按 USD 判断。</p>
            </div>
            <el-button :disabled="busy" @click="editPolicy">编辑当前规则</el-button>
          </div>
          <template v-if="policyDraft">
            <el-alert
              v-if="policyVersion !== overview.configuration.version"
              title="规则已被其他操作更新，请重新加载后编辑"
              type="warning"
              :closable="false"
            />
            <el-form label-position="top" class="policy-fields"
              ><el-form-item label="单款备货金额上限（USD）"
                ><el-input-number v-model="policyDraft.stock_amount_limit" :min="0" /></el-form-item
              ><el-form-item label="单日预算变动上限（%）"
                ><el-input-number
                  v-model="policyDraft.budget_change_limit_pct"
                  :min="0"
                  :max="100" /></el-form-item
              ><el-form-item label="自动退款上限（USD）"
                ><el-input-number v-model="policyDraft.refund_limit" :min="0" /></el-form-item
              ><el-form-item label="最低选品评分"
                ><el-input-number
                  v-model="policyDraft.selection_min_score"
                  :min="0"
                  :max="100" /></el-form-item
              ><el-form-item label="最低毛利率（%）"
                ><el-input-number
                  v-model="policyDraft.min_margin_pct"
                  :min="0"
                  :max="99" /></el-form-item
              ><el-form-item label="失败最大尝试次数"
                ><el-input-number
                  v-model="policyDraft.max_attempts"
                  :min="1"
                  :max="10" /></el-form-item
            ></el-form>
            <label for="rules-json"
              >五维规则 JSON（ID、dimension、pattern、level、replacement）</label
            ><el-input id="rules-json" v-model="rulesDraft" type="textarea" :rows="12" />
            <div class="actions">
              <el-button
                type="primary"
                :loading="busy"
                :disabled="policyVersion !== overview.configuration.version"
                @click="savePolicy"
                >保存为新版本</el-button
              ><el-button @click="policyDraft = undefined">取消编辑</el-button>
            </div>
          </template>
          <template v-else
            ><div class="data-counts">
              <span
                >备货上限
                <strong>${{ overview.configuration.payload.stock_amount_limit }}</strong></span
              ><span
                >预算变动
                <strong>{{ overview.configuration.payload.budget_change_limit_pct }}%</strong></span
              ><span
                >退款上限 <strong>${{ overview.configuration.payload.refund_limit }}</strong></span
              >
            </div>
            <el-table :data="overview.configuration.payload.rules"
              ><el-table-column prop="id" label="规则" width="150" /><el-table-column
                prop="dimension"
                label="维度"
                min-width="180" /><el-table-column
                prop="pattern"
                label="匹配内容"
                min-width="170" /><el-table-column
                prop="level"
                label="风险等级"
                width="120" /></el-table
          ></template>
        </el-tab-pane>
        <el-tab-pane label="定时与绩效" name="iteration">
          <h2>定时运营复盘与智能体绩效</h2>
          <p>
            配置计划后，由 Celery Beat 每分钟检查到期任务。本地 eager
            模式可点击扫描执行；重复扫描按计划时段去重。
          </p>
          <div class="schedule-controls">
            <span>运营复盘</span
            ><el-input-number
              v-model="scheduleHours"
              aria-label="执行间隔小时"
              :min="1"
              :max="8784"
            /><span>小时执行一次</span
            ><el-button
              :loading="busy"
              @click="
                action(
                  () =>
                    ecomApi.schedule(session.token!, {
                      workflow: 'analytics',
                      interval_hours: scheduleHours,
                      input: {},
                    }),
                  '计划已保存',
                )
              "
              >创建计划</el-button
            ><el-button
              :loading="busy"
              @click="action(() => ecomApi.tick(session.token!), '扫描已提交')"
              >扫描到期任务与恢复事件</el-button
            >
          </div>
          <el-alert
            v-if="schedulesQuery.isError.value || performanceQuery.isError.value"
            title="计划或评估读取失败，请刷新状态重试"
            type="error"
            :closable="false"
          />
          <el-table :data="schedulesQuery.data.value ?? []" empty-text="尚未配置定时任务"
            ><el-table-column label="流程" min-width="180"
              ><template #default="{ row }">{{
                workflowName(row.workflow)
              }}</template></el-table-column
            ><el-table-column
              prop="interval_hours"
              label="间隔（小时）"
              width="140"
            /><el-table-column label="下次执行" width="170"
              ><template #default="{ row }">{{
                formatTime(row.next_run_at)
              }}</template></el-table-column
            ><el-table-column label="操作" width="120"
              ><template #default="{ row }"
                ><el-button
                  link
                  :disabled="busy || !overview.workflows.some((w) => w.id === row.workflow)"
                  @click="
                    action(
                      () => ecomApi.toggleSchedule(session.token!, row.id, !row.enabled),
                      '计划状态已更新',
                    )
                  "
                  >{{ row.enabled ? '暂停计划' : '启用计划' }}</el-button
                ></template
              ></el-table-column
            ></el-table
          >
          <h3>最近 30 天智能体表现</h3>
          <p>{{ performanceQuery.data.value?.limitation }}</p>
          <el-table :data="performanceQuery.data.value?.agents ?? []"
            ><el-table-column prop="name" label="智能体" min-width="180" /><el-table-column
              prop="tasks"
              label="任务数"
              width="100"
            /><el-table-column label="完成率" width="130"
              ><template #default="{ row }">{{
                row.completion_rate === null
                  ? '暂无样本'
                  : `${(row.completion_rate * 100).toFixed(1)}%`
              }}</template></el-table-column
            ><el-table-column label="平均执行时间" min-width="150"
              ><template #default="{ row }">{{
                row.avg_duration_ms === null ? '暂无样本' : `${row.avg_duration_ms} ms`
              }}</template></el-table-column
            ></el-table
          >
        </el-tab-pane>
      </el-tabs>
    </template>

    <el-drawer
      v-model="createOpen"
      title="新建运营任务"
      size="min(680px, 100%)"
      class="create-drawer"
      destroy-on-close
      :close-on-click-modal="false"
      :before-close="
        (done: () => void) => {
          if (!busy) done()
        }
      "
    >
      <template v-if="overview">
        <el-steps :active="createStep" simple class="create-steps"
          ><el-step title="选择业务" /><el-step title="填写参数"
        /></el-steps>
        <el-form
          label-position="top"
          @submit.prevent="createStep === 0 ? (createStep = 1) : createRun()"
        >
          <div v-show="createStep === 0">
            <el-form-item label="业务流程"
              ><el-select v-model="workflow" aria-label="业务流程"
                ><el-option
                  v-for="w in overview.workflows"
                  :key="w.id"
                  :label="w.name"
                  :value="w.id" /></el-select
            ></el-form-item>
            <el-form-item label="任务名称"
              ><el-input v-model="title" maxlength="200" placeholder="可选，默认使用流程名称"
            /></el-form-item>
            <p class="helper">
              提交后按依赖自动推进；需要人工审核的步骤会暂停，并保留执行与处理记录。
            </p>
            <details class="workflow-guide">
              <summary>查看流程 · {{ workflowName(workflow) }}</summary>
              <ol class="dependency-list">
                <li
                  v-for="step in overview.workflows.find((w) => w.id === workflow)?.steps"
                  :key="step.key"
                >
                  <strong>{{ step.title }}</strong
                  ><span
                    >{{ agentName(step.agent) }} ·
                    {{
                      step.dependencies.length
                        ? `等待 ${dependencyNames(step.dependencies)}`
                        : '起始节点'
                    }}</span
                  >
                </li>
              </ol>
            </details>
          </div>
          <div v-show="createStep === 1">
            <h2>{{ workflowName(workflow) }}</h2>
            <template v-if="workflow === 'initialization'"
              ><el-alert
                title="初始化使用数据中台的产品、供应商与当前规则"
                type="info"
                :closable="false"
              />
              <p>请先导入基础数据。初始化完成代表本地沙盒就绪，生产接入仍需验证。</p>
              <el-button @click="openData">前往数据中台</el-button></template
            >
            <template v-else-if="workflow === 'analytics'"
              ><el-alert
                title="复盘使用数据中台已导入的指标与执行记录"
                type="info"
                :closable="false"
              />
              <p>请确认指标为不重叠的 USD 汇总区间，并保留数据来源。</p></template
            >
            <template v-else>
              <div class="paired">
                <el-form-item label="目标平台"
                  ><el-select v-model="platform" aria-label="目标平台"
                    ><el-option
                      v-for="p in overview.platforms"
                      :key="p.id"
                      :label="p.name"
                      :value="p.id" /></el-select
                ></el-form-item>
                <el-form-item label="标准 SKU"
                  ><el-input v-model="sku" placeholder="例如 DEMO-SKU-01"
                /></el-form-item>
              </div>
              <el-form-item label="产品标题"
                ><el-input v-model="productTitle" maxlength="200"
              /></el-form-item>
              <el-form-item v-if="workflow === 'selection'" label="竞品采集批次">
                <el-select
                  v-model="researchCollectionId"
                  clearable
                  aria-label="竞品采集批次"
                  placeholder="可选，使用公开采集证据"
                  :loading="researchCollectionsQuery.isFetching.value"
                >
                  <el-option
                    v-for="c in researchCollectionsQuery.data.value?.filter(
                      (c) => c.country === country,
                    )"
                    :key="`${c.collection_id}:${c.country}`"
                    :value="c.collection_id"
                    :label="`${c.category} · ${c.count}件`"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="产品事实 / 业务上下文"
                ><el-input
                  v-model="content"
                  type="textarea"
                  :rows="3"
                  maxlength="10000"
                  placeholder="产品参数、用户需求或需要校验的文案"
              /></el-form-item>
              <div class="paired">
                <el-form-item
                  v-if="['selection', 'listing', 'marketing'].includes(workflow)"
                  label="售价（USD）"
                  ><el-input-number
                    v-model="price"
                    aria-label="售价（USD）"
                    :min="0"
                    :precision="2"
                /></el-form-item>
                <el-form-item v-if="workflow === 'selection'" label="采购单价（USD）"
                  ><el-input-number
                    v-model="procurement"
                    aria-label="采购单价（USD）"
                    :min="0"
                    :precision="2"
                /></el-form-item>
                <el-form-item
                  v-if="['selection', 'fulfillment'].includes(workflow)"
                  label="备货 / 订单数量"
                  ><el-input-number
                    v-model="quantity"
                    aria-label="备货 / 订单数量"
                    :min="1"
                    :precision="0"
                /></el-form-item>
                <el-form-item label="目标国家代码"
                  ><el-input v-model="country" maxlength="2" placeholder="例如 US、DE"
                /></el-form-item>
                <el-form-item
                  v-if="['selection', 'listing', 'service', 'marketing'].includes(workflow)"
                  label="文案目标语言"
                  ><el-select v-model="language" aria-label="文案目标语言"
                    ><el-option
                      v-for="l in [
                        { id: 'en', name: '英语' },
                        { id: 'zh', name: '中文' },
                        { id: 'de', name: '德语' },
                        { id: 'ja', name: '日语' },
                        { id: 'fr', name: '法语' },
                        { id: 'es', name: '西班牙语' },
                      ]"
                      :key="l.id"
                      :value="l.id"
                      :label="l.name" /></el-select
                ></el-form-item>
              </div>
              <details v-if="workflow === 'selection'" class="workflow-guide">
                <summary>物流、税费与销售费率</summary>
                <div class="paired">
                  <el-form-item label="单件头程物流（USD）"
                    ><el-input-number
                      v-model="business.freight"
                      :min="0"
                      :precision="2" /></el-form-item
                  ><el-form-item label="单件税费（USD）"
                    ><el-input-number
                      v-model="business.tax"
                      :min="0"
                      :precision="2" /></el-form-item
                  ><el-form-item label="单件损耗（USD）"
                    ><el-input-number
                      v-model="business.loss"
                      :min="0"
                      :precision="2" /></el-form-item
                  ><el-form-item label="平台佣金（%）"
                    ><el-input-number
                      v-model="business.commission_pct"
                      :min="0"
                      :max="99" /></el-form-item
                  ><el-form-item label="广告费率（%）"
                    ><el-input-number v-model="business.ad_rate_pct" :min="0" :max="99"
                  /></el-form-item>
                </div>
              </details>
              <div v-if="workflow === 'marketing'" class="paired">
                <el-form-item label="调整前日预算（USD）"
                  ><el-input-number
                    v-model="business.budget_before"
                    aria-label="调整前日预算（USD）"
                    :min="0"
                    :precision="2" /></el-form-item
                ><el-form-item label="调整后日预算（USD）"
                  ><el-input-number
                    v-model="business.budget_after"
                    aria-label="调整后日预算（USD）"
                    :min="0"
                    :precision="2" /></el-form-item
                ><el-form-item label="累计消耗（USD）"
                  ><el-input-number
                    v-model="business.ad_spend"
                    aria-label="累计消耗（USD）"
                    :min="0"
                    :precision="2"
                /></el-form-item>
              </div>
              <template v-if="workflow === 'service'"
                ><el-form-item label="咨询 / 售后类型"
                  ><el-select v-model="business.service_intent" aria-label="咨询 / 售后类型"
                    ><el-option
                      v-for="intent in [
                        { id: 'consultation', name: '产品咨询' },
                        { id: 'refund', name: '退款申请' },
                        { id: 'review', name: '评论反馈' },
                        { id: 'logistics', name: '物流查询' },
                      ]"
                      :key="intent.id"
                      :value="intent.id"
                      :label="intent.name" /></el-select></el-form-item
                ><el-form-item v-if="business.service_intent === 'refund'" label="退款金额（USD）"
                  ><el-input-number
                    v-model="business.refund_amount"
                    aria-label="退款金额（USD）"
                    :min="0"
                    :precision="2" /></el-form-item
              ></template>
              <el-form-item v-if="['service', 'fulfillment'].includes(workflow)" label="订单编码"
                ><el-input v-model="business.order_key" maxlength="120"
              /></el-form-item>
              <template v-if="workflow === 'fulfillment'"
                ><el-form-item label="目的地地址"
                  ><el-input
                    v-model="business.destination_address"
                    type="textarea"
                    :rows="2"
                    maxlength="500"
                /></el-form-item>
                <div class="paired">
                  <el-form-item label="可用库存"
                    ><el-input-number
                      v-model="business.stock"
                      :min="0"
                      :precision="0" /></el-form-item
                  ><el-form-item label="安全库存"
                    ><el-input-number
                      v-model="business.safety_stock"
                      :min="0"
                      :precision="0" /></el-form-item
                  ><el-form-item label="日均销量"
                    ><el-input-number v-model="business.daily_sales" :min="0" /></el-form-item
                  ><el-form-item label="补货周期（天）"
                    ><el-input-number v-model="business.lead_days" :min="0" :precision="0"
                  /></el-form-item>
                </div>
                <el-form-item label="物流状态"
                  ><el-select v-model="business.tracking_status" aria-label="物流状态"
                    ><el-option
                      v-for="item in [
                        { id: 'unknown', name: '暂无轨迹' },
                        { id: 'in_transit', name: '运输中' },
                        { id: 'delayed', name: '延误' },
                        { id: 'lost', name: '丢件' },
                        { id: 'damaged', name: '破损' },
                        { id: 'customs', name: '清关异常' },
                      ]"
                      :key="item.id"
                      :label="item.name"
                      :value="item.id" /></el-select></el-form-item
              ></template>
              <el-form-item label="模型辅助生成"
                ><el-switch
                  v-model="useAi"
                  aria-label="启用模型辅助生成"
                  active-text="生成候选建议"
                />
                <p class="helper">
                  需要 AI 配置及服务端真实生成开关；失败保留本地输出，审批权限由风控规则决定。
                </p></el-form-item
              >
              <details class="workflow-guide">
                <summary>高级补充参数（JSON）</summary>
                <p class="helper">
                  仅在需要额外业务字段或多币种时使用。JSON 中的同名参数会覆盖表单值；完整字段见业务
                  API 文档。
                </p>
                <el-input
                  v-model="advancedInput"
                  type="textarea"
                  :rows="5"
                  aria-label="业务补充参数 JSON"
                />
              </details>
            </template>
            <p
              v-if="!overview.initialization_ready && workflow !== 'initialization'"
              class="helper"
            >
              基础初始化尚未完成，其他任务会等待初始化就绪。
            </p>
          </div>
        </el-form>
      </template>
      <template #footer
        ><div class="drawer-actions">
          <el-button :disabled="busy" @click="createOpen = false">取消</el-button
          ><el-button v-if="createStep === 1" :disabled="busy" @click="createStep = 0"
            >上一步</el-button
          ><el-button v-if="createStep === 0" type="primary" @click="createStep = 1"
            >下一步：填写参数</el-button
          ><el-button v-else type="primary" :loading="busy" @click="createRun"
            >创建并执行任务</el-button
          >
        </div></template
      >
    </el-drawer>

    <el-drawer
      v-model="drawer"
      title="任务协同与人工处置"
      size="min(900px, 100%)"
      class="task-drawer"
      destroy-on-close
    >
      <el-alert
        v-if="detailQuery.isError.value"
        title="任务详情读取失败，请关闭后重试"
        type="error"
        :closable="false"
      />
      <el-skeleton v-if="detailQuery.isPending.value" :rows="6" animated />
      <template v-if="detail">
        <div class="detail-heading">
          <h2>{{ detail.title }}</h2>
          <el-tag :type="statusType(detail.status)">{{ statusName(detail.status) }}</el-tag>
        </div>
        <p class="helper">
          业务对象：{{ detail.input?.order_key || detail.input?.sku || '未提供' }} · 平台：{{
            detail.input?.platform
          }}
          · 站点：{{ detail.input?.country }} · 规则 v{{ detail.config_version }}
        </p>
        <section v-if="reviewTask" class="review-focus" aria-labelledby="review-title">
          <div class="section-heading">
            <h3 id="review-title">待确认事项</h3>
            <el-select
              v-if="reviews.length > 1"
              :model-value="reviewTask.id"
              aria-label="选择待审事项"
              :placeholder="reviewTask.title"
              @update:model-value="reviewTaskId = $event"
              ><el-option
                v-for="task in reviews"
                :key="task.id"
                :label="task.title"
                :value="task.id"
            /></el-select>
          </div>
          <h2>{{ reviewTask.title }}</h2>
          <el-alert
            :title="reviewTask.reason || '此步骤需要人工核验后继续'"
            type="warning"
            :closable="false"
          />
          <el-descriptions
            v-if="reviewFacts(reviewTask).length"
            title="审批金额与权限依据"
            :column="1"
            border
            class="review-evidence"
            ><el-descriptions-item
              v-for="fact in reviewFacts(reviewTask)"
              :key="fact.label"
              :label="fact.label"
              >{{ fact.value }}</el-descriptions-item
            ></el-descriptions
          >
          <p class="helper">
            请核对业务对象、触发规则及证据。审批会再次校验规则版本，处理结果全程留痕。
          </p>
        </section>
        <h3>执行进度与业务结果</h3>
        <el-collapse v-model="expandedTasks" class="task-details">
          <el-collapse-item v-for="task in detail.tasks" :key="task.id" :name="task.id">
            <template #title
              ><span class="task-heading"
                ><el-tag :type="statusType(task.status)">{{ statusName(task.status) }}</el-tag
                ><strong>{{ task.title }}</strong
                ><span>{{ agentName(task.agent) }}</span></span
              ></template
            >
            <p class="helper">
              前置步骤：{{
                task.dependencies
                  .map((key) => detail?.tasks?.find((item) => item.key === key)?.title ?? key)
                  .join(' → ') || '无'
              }}
              · 尝试 {{ task.attempts }} 次
            </p>
            <el-alert
              v-if="task.reason && task.status !== 'waiting_review'"
              :title="task.reason"
              :type="statusType(task.status) === 'danger' ? 'error' : 'warning'"
              :closable="false"
            />
            <p v-if="task.status === 'waiting_review'" class="helper">
              请在上方“待确认事项”查看依据，并在底部提交审核。
            </p>
            <p v-if="task.output.recovery === 'new_run_required'" class="helper">
              本任务输入已冻结。请使用“修订输入并新建任务”补齐参数，原任务保留审计记录。
            </p>
            <div
              v-if="
                isActive(detail) &&
                ['failed', 'waiting_data', 'waiting_integration'].includes(task.status) &&
                task.output.recovery !== 'new_run_required'
              "
              class="recovery-actions"
            >
              <label :for="`retry-note-${task.id}`">重试依据</label
              ><el-input
                :id="`retry-note-${task.id}`"
                v-model="managementNote"
                placeholder="说明已补充的条件"
              /><el-button :loading="busy" @click="intervene('retry', task, managementNote)"
                >补充条件后重试</el-button
              >
            </div>
            <details class="technical-output">
              <summary>执行输出与证据</summary>
              <pre>{{ JSON.stringify(task.output, null, 2) }}</pre>
            </details>
          </el-collapse-item>
        </el-collapse>
        <details class="management-section">
          <summary>任务管理</summary>
          <p class="helper">优先级 {{ detail.priority }} · 规则 v{{ detail.config_version }}</p>
          <el-button
            v-if="overview?.workflows.some((w) => w.id === detail?.workflow)"
            :disabled="busy"
            @click="copyRun"
            >修订输入并新建任务</el-button
          >
          <p v-else class="helper">此流程已停用，历史结果仍可查看。</p>
          <section v-if="isActive(detail)" class="intervention">
            <label for="management-note">处理依据 / 接管说明</label
            ><el-input
              id="management-note"
              v-model="managementNote"
              type="textarea"
              :rows="2"
              maxlength="2000"
              placeholder="说明接管、取消或调整优先级的依据"
            />
            <div class="actions">
              <el-button
                v-if="detail.status !== 'taken_over'"
                :loading="busy"
                @click="intervene('takeover', undefined, managementNote)"
                >人工接管</el-button
              ><el-button
                v-else
                :loading="busy"
                @click="intervene('resume', undefined, managementNote)"
                >恢复自动流转</el-button
              ><el-button
                type="danger"
                plain
                :loading="busy"
                @click="intervene('cancel', undefined, managementNote)"
                >取消任务</el-button
              ><el-input-number
                v-model="priority"
                aria-label="任务优先级"
                :min="1"
                :max="10"
              /><el-button :loading="busy" @click="intervene('priority', undefined, managementNote)"
                >更新优先级</el-button
              >
            </div>
          </section>
        </details>
        <details class="management-section">
          <summary>人工干预记录 · {{ detail.audits?.length ?? 0 }}</summary>
          <el-table :data="detail.audits ?? []" empty-text="暂无人工干预"
            ><el-table-column prop="actor" label="操作人" width="110" /><el-table-column
              prop="action"
              label="操作"
              width="110" /><el-table-column prop="note" label="依据" min-width="260"
          /></el-table>
        </details>
        <details class="management-section">
          <summary>技术记录 · 消息总线事件</summary>
          <ol class="event-list">
            <li v-for="event in detail.events" :key="event.id">
              <time>{{ formatTime(event.created_at) }}</time
              ><span>{{ event.topic }}</span
              ><span>{{ event.status === 'delivered' ? '已消费' : '待消费' }}</span>
            </li>
          </ol>
        </details>
      </template>
      <template v-if="detail && reviewTask && isActive(detail)" #footer
        ><div class="review-decision">
          <label for="intervention-note">审核依据（必填） · {{ reviewTask.title }}</label
          ><el-input
            id="intervention-note"
            v-model="interventionNote"
            type="textarea"
            :rows="2"
            maxlength="2000"
            placeholder="说明核验依据、驳回原因或人工接管计划"
          />
          <div class="drawer-actions">
            <el-button :loading="busy" @click="intervene('reevaluate', reviewTask)"
              >重新评估规则</el-button
            ><el-button type="danger" plain :loading="busy" @click="intervene('reject', reviewTask)"
              >驳回任务</el-button
            ><el-button type="primary" :loading="busy" @click="intervene('approve', reviewTask)"
              >通过审核并继续</el-button
            >
          </div>
        </div></template
      >
    </el-drawer>
  </section>
</template>

<style scoped lang="scss">
.ecomops {
  display: grid;
  gap: 20px;
  min-width: 0;
}
.review-evidence {
  margin: 20px 0;
}
.review-shortcut {
  padding: 0;
  border: 0;
  background: none;
  color: var(--primary-active);
  cursor: pointer;
  font: inherit;
  text-decoration: underline;
  text-underline-offset: 4px;
}
.page-heading,
.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
h1 {
  margin: 0;
  font-size: 26px;
  line-height: 1.35;
}
h2 {
  margin: 0 0 16px;
  font-size: 20px;
}
h3 {
  margin: 28px 0 12px;
  font-size: 17px;
}
h4 {
  margin: 20px 0 8px;
}
p {
  color: var(--text-secondary);
  line-height: 1.65;
}
.page-heading p {
  margin: 8px 0 0;
}
.readiness,
.data-counts {
  display: flex;
  flex-wrap: wrap;
  gap: 14px 28px;
  color: var(--text-secondary);
}
.readiness strong,
.data-counts strong {
  color: var(--text-primary);
}
.surface {
  padding: 10px 24px 24px;
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  min-width: 0;
}
.run-panel {
  min-width: 0;
}
.paired {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 12px;
}
.paired :deep(.el-input-number) {
  width: 100%;
}
.helper {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 8px 0;
}
.task-link {
  padding: 6px 0;
  background: none;
  border: 0;
  color: var(--primary-active);
  cursor: pointer;
  font: inherit;
  text-align: left;
}
.task-link:hover,
a:hover {
  text-decoration: underline;
}
.task-link:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 3px;
}
.dependency-list {
  display: grid;
  gap: 0;
  margin: 0;
  padding-left: 24px;
}
.dependency-list li {
  padding: 12px 4px;
  border-bottom: 1px solid var(--border-soft);
}
.dependency-list span {
  display: block;
  color: var(--text-secondary);
  margin-top: 5px;
  font-size: 13px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 16px 0;
}
.actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
.data-counts {
  padding: 20px 0;
}
label {
  display: block;
  margin-bottom: 10px;
  color: var(--text-secondary);
}
.policy-fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.schedule-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin: 24px 0;
}
.schedule-controls :deep(.el-select) {
  width: 180px;
}
.intervention {
  padding: 20px 0;
  margin-top: 16px;
  border-block: 1px solid var(--border);
}
.task-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 8px 12px 0;
  line-height: 1.5;
}
.task-heading > span:last-child {
  color: var(--text-secondary);
  font-size: 13px;
}
.task-details :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 60px;
}
pre {
  margin: 0;
  padding: 16px;
  background: var(--surface-muted);
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.event-list {
  padding: 0;
  list-style: none;
}
.event-list li {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-soft);
  font-size: 13px;
}
.event-list time {
  color: var(--text-secondary);
}
@media (max-width: 1100px) {
  .policy-fields {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .page-heading,
  .section-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .surface {
    padding: 8px 12px 20px;
  }
  h1 {
    font-size: 23px;
  }
  .policy-fields,
  .paired {
    grid-template-columns: 1fr;
  }
}

.heading-actions,
.run-filters,
.drawer-actions,
.environment-summary,
.detail-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}
.heading-actions,
.drawer-actions {
  flex-wrap: wrap;
}
.environment-summary {
  flex-wrap: wrap;
  gap: 8px 12px;
  color: var(--text-secondary);
  font-size: 14px;
}
.environment-summary p {
  margin: 8px 0 0;
}
summary {
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1.6;
}
summary:focus-visible,
.run-card:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 3px;
}
.run-panel .section-heading {
  margin: 12px 0 20px;
}
.run-panel h2 {
  margin: 0;
}
.run-filters {
  max-width: 100%;
}
.run-filters :deep(.el-input) {
  width: 220px;
}
.run-filters :deep(.el-select) {
  width: 150px;
}
.mobile-runs {
  display: none;
}
.empty-start {
  padding: 16px 0;
}
.create-steps {
  margin-bottom: 28px;
}
.workflow-guide {
  margin: 16px 0 24px;
}
.workflow-guide > summary {
  margin-bottom: 12px;
}
.workflow-guide .paired {
  margin-top: 16px;
}
.drawer-actions {
  justify-content: flex-end;
  margin-top: 12px;
}
.drawer-actions :deep(.el-button + .el-button),
.heading-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
.detail-heading {
  justify-content: space-between;
  align-items: flex-start;
}
.detail-heading h2 {
  overflow-wrap: anywhere;
}
.review-focus {
  margin-top: 24px;
}
.review-focus h3 {
  margin: 0 0 16px;
}
.review-focus .el-select {
  width: 240px;
}
.review-decision {
  text-align: left;
}
.review-decision label {
  margin-bottom: 8px;
}
.review-evidence :deep(.el-descriptions__content) {
  overflow-wrap: anywhere;
}
.review-evidence :deep(.el-descriptions__label) {
  width: 160px;
}
.technical-output {
  margin-top: 16px;
}
.technical-output summary {
  margin-bottom: 8px;
}
.management-section {
  padding: 16px 0;
  border-bottom: 1px solid var(--border-soft);
}
.management-section > summary {
  font-weight: 600;
  color: var(--text-primary);
}
.management-section[open] > summary {
  margin-bottom: 16px;
}
.recovery-actions {
  display: grid;
  gap: 12px;
  margin: 16px 0;
  justify-items: start;
}
@media (max-width: 1100px) {
  .run-panel .section-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
@media (max-width: 640px) {
  .ecomops {
    gap: 16px;
  }
  .heading-actions {
    width: 100%;
  }
  .heading-actions > :last-child {
    margin-left: auto;
  }
  .run-filters {
    flex-wrap: wrap;
    width: 100%;
  }
  .run-filters :deep(.el-input),
  .run-filters :deep(.el-select) {
    width: 100%;
  }
  .desktop-runs {
    display: none;
  }
  .mobile-runs {
    display: grid;
  }
  .run-card {
    display: grid;
    width: 100%;
    gap: 8px;
    padding: 16px 0;
    color: var(--text-primary);
    text-align: left;
    background: transparent;
    border: 0;
    border-bottom: 1px solid var(--border-soft);
    cursor: pointer;
    font: inherit;
  }
  .run-card__top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }
  .run-card__top strong {
    overflow-wrap: anywhere;
  }
  .run-card__top .el-tag {
    flex-shrink: 0;
  }
  .run-card .helper {
    margin: 0;
  }
  .run-card__reason {
    color: var(--warning-dark);
    font-size: 13px;
    overflow-wrap: anywhere;
  }
  .run-card__meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: space-between;
    color: var(--text-secondary);
    font-size: 13px;
  }
  .run-card__meta > span {
    color: var(--primary-active);
  }
  .drawer-actions {
    gap: 8px;
  }
  .drawer-actions .el-button {
    min-height: 44px;
    flex: 1;
    padding-inline: 8px;
  }
  .review-evidence :deep(.el-descriptions__label) {
    width: 120px;
  }
}
:global(.create-drawer .el-drawer__header),
:global(.task-drawer .el-drawer__header) {
  margin-bottom: 0;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-soft);
}
:global(.create-drawer .el-drawer__body),
:global(.task-drawer .el-drawer__body) {
  padding: 24px;
}
:global(.create-drawer .el-drawer__footer),
:global(.task-drawer .el-drawer__footer) {
  padding: 12px 24px max(16px, env(safe-area-inset-bottom));
  border-top: 1px solid var(--border);
  background: var(--surface);
}
@media (max-width: 640px) {
  :global(.create-drawer .el-drawer__header),
  :global(.task-drawer .el-drawer__header),
  :global(.create-drawer .el-drawer__body),
  :global(.task-drawer .el-drawer__body) {
    padding: 16px;
  }
  :global(.create-drawer .el-drawer__footer),
  :global(.task-drawer .el-drawer__footer) {
    padding-inline: 16px;
  }
}
</style>
