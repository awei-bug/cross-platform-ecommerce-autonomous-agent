<script setup lang="ts">
import {
  ArrowRight,
  Clock,
  Connection,
  MoreFilled,
  Refresh,
  Search,
  View,
} from '@element-plus/icons-vue'
import { useMutation, useQuery } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { productApi } from '../api'
import BatchActionBar from '../components/business/BatchActionBar.vue'
import EmptyState from '../components/business/EmptyState.vue'
import FilterBar from '../components/business/FilterBar.vue'
import JobProgress from '../components/business/JobProgress.vue'
import RiskBadge from '../components/business/RiskBadge.vue'
import { useSessionStore } from '../stores/session'
import { useWorkspaceStore } from '../stores/workspace'
import type {
  BatchAction,
  BatchJob,
  CapabilityMode,
  Platform,
  ProductListItem,
  ProductRisk,
  ProductStatus,
} from '../types/api'

const route = useRoute()
const session = useSessionStore()
const workspace = useWorkspaceStore()
const tableRef = ref()
const selectedRows = ref<ProductListItem[]>([])
const detailId = ref('')
const detailOpen = ref(false)
const currentJob = ref<BatchJob | null>(null)
let jobTimer: ReturnType<typeof setTimeout> | null = null

const filters = reactive({
  q: typeof route.query.sku === 'string' ? route.query.sku : '',
  platform: 'all' as Platform,
  status: '' as ProductStatus | '',
  risk: (typeof route.query.risk === 'string' ? route.query.risk : '') as ProductRisk | '',
  sort_by: 'risk',
  sort_order: 'desc' as 'asc' | 'desc',
  page: 1,
  page_size: 10,
})

const queryKey = computed(() => [
  'products',
  workspace.currentShopId,
  filters.platform,
  filters.q,
  filters.status,
  filters.risk,
  filters.sort_by,
  filters.sort_order,
  filters.page,
  filters.page_size,
])

const productsQuery = useQuery({
  queryKey,
  queryFn: () =>
    productApi.list(session.token!, {
      shop_id: workspace.currentShopId,
      platform: filters.platform,
      q: filters.q,
      status: filters.status,
      risk: filters.risk,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
      page: filters.page,
      page_size: filters.page_size,
    }),
  enabled: computed(() => Boolean(session.token)),
})

const detailQuery = useQuery({
  queryKey: computed(() => ['product-detail', detailId.value]),
  queryFn: () => productApi.detail(session.token!, detailId.value),
  enabled: computed(() => Boolean(session.token && detailId.value && detailOpen.value)),
})

const batchMutation = useMutation({
  mutationFn: (request: {
    action: BatchAction
    productIds: string[]
    payload?: Record<string, unknown>
  }) =>
    productApi.createBatchJob(session.token!, {
      action: request.action,
      product_ids: request.productIds,
      payload: request.payload,
      idempotency_key: `${request.action}-${Date.now()}-${request.productIds.join('-')}`,
    }),
})

const currency = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  maximumFractionDigits: 0,
})

const statusLabels: Record<ProductStatus, string> = {
  online: '销售中',
  offline: '已下架',
  draft: '草稿',
}

const capabilityByKey = computed(() =>
  Object.fromEntries(workspace.capabilities.map((item) => [item.key, item])),
)

const disabledBatchActions = computed<BatchAction[]>(() => {
  if (!workspace.isSingleShop) return ['publish', 'unpublish', 'update_price']
  const actions: BatchAction[] = []
  const statusMode = capabilityByKey.value['product.change_status']?.mode
  const priceMode = capabilityByKey.value['product.update_price']?.mode
  if (!isExecutable(statusMode)) actions.push('publish', 'unpublish')
  if (!isExecutable(priceMode)) actions.push('update_price')
  return actions
})

const capabilityMessage = computed(() => {
  if (!workspace.isSingleShop) return '全部店铺视角仅支持读取与同步；写操作需切换到单个店铺。'
  const limited = workspace.capabilities.filter((item) => !isExecutable(item.mode))
  if (!limited.length) return '当前店铺商品操作支持直接或异步执行。'
  return limited.map((item) => `${item.label}：${item.reason ?? '需前往平台处理'}`).join('；')
})

function isExecutable(mode: CapabilityMode | undefined) {
  return mode === 'direct' || mode === 'async'
}

function applySearch() {
  filters.page = 1
}

function selectRisk(risk: ProductRisk | '') {
  filters.risk = risk
  filters.page = 1
}

function resetFilters() {
  filters.q = ''
  filters.platform = 'all'
  filters.status = ''
  filters.risk = ''
  filters.sort_by = 'risk'
  filters.sort_order = 'desc'
  filters.page = 1
}

function handleSelectionChange(rows: ProductListItem[]) {
  selectedRows.value = rows
}

function clearSelection() {
  tableRef.value?.clearSelection()
  selectedRows.value = []
}

function handleSortChange({ prop, order }: { prop: string; order: string | null }) {
  filters.sort_by = prop || 'risk'
  filters.sort_order = order === 'ascending' ? 'asc' : 'desc'
  filters.page = 1
}

function openDetail(product: ProductListItem) {
  detailId.value = product.id
  detailOpen.value = true
}

async function confirmBatch(
  action: BatchAction,
  productIds = selectedRows.value.map((item) => item.id),
) {
  if (!productIds.length) return
  const labels: Record<BatchAction, string> = {
    publish: '批量上架',
    unpublish: '批量下架',
    update_price: '批量改价',
    sync: '立即同步',
  }
  let payload: Record<string, unknown> | undefined
  if (action === 'update_price') {
    const result = await ElMessageBox.prompt(
      '请输入统一调整后的演示价格。任务不会写入真实平台。',
      labels[action],
      {
        confirmButtonText: '创建任务',
        cancelButtonText: '取消',
        inputPattern: /^\d+(\.\d{1,2})?$/,
        inputErrorMessage: '请输入有效价格',
      },
    ).catch(() => null)
    if (!result) return
    payload = { price: Number(result.value) }
  } else {
    const confirmed = await ElMessageBox.confirm(
      `将对 ${productIds.length} 个商品执行“${labels[action]}”。系统会创建可追踪任务，并保留部分失败结果。`,
      `${labels[action]}确认`,
      {
        confirmButtonText: '确认创建任务',
        cancelButtonText: '取消',
        type: action === 'sync' ? 'info' : 'warning',
      },
    ).catch(() => false)
    if (!confirmed) return
  }

  try {
    currentJob.value = await batchMutation.mutateAsync({ action, productIds, payload })
    clearSelection()
    ElMessage.success('演示批量任务已创建')
    scheduleJobPoll()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '任务创建失败')
  }
}

function scheduleJobPoll() {
  if (jobTimer) clearTimeout(jobTimer)
  if (!currentJob.value || ['succeeded', 'partial', 'failed'].includes(currentJob.value.status))
    return
  jobTimer = setTimeout(async () => {
    if (!currentJob.value) return
    try {
      currentJob.value = await productApi.job(session.token!, currentJob.value.id)
      if (['succeeded', 'partial'].includes(currentJob.value.status)) {
        await productsQuery.refetch()
      }
    } finally {
      scheduleJobPoll()
    }
  }, 900)
}

function retryFailed() {
  if (!currentJob.value) return
  const failedIds = currentJob.value.results
    .filter((item) => !item.success)
    .map((item) => item.product_id)
  void confirmBatch(currentJob.value.action, failedIds)
}

watch(
  () => workspace.currentShopId,
  () => {
    filters.page = 1
    clearSelection()
  },
)

watch(
  () => route.query,
  (query) => {
    if (typeof query.sku === 'string') filters.q = query.sku
    if (typeof query.risk === 'string') filters.risk = query.risk as ProductRisk
    filters.page = 1
  },
)

onBeforeUnmount(() => {
  if (jobTimer) clearTimeout(jobTimer)
})
</script>

<template>
  <div class="product-center">
    <header class="page-heading">
      <div>
        <div class="page-heading__eyebrow">
          <span>商品中心</span>
          <b>演示数据</b>
        </div>
        <h1>跨平台商品运营台账</h1>
        <p>异常优先查看、服务端筛选与分页；批量动作保留确认、进度和部分失败结果。</p>
      </div>
      <div class="page-heading__meta">
        <el-icon><Clock /></el-icon>
        <span
          >更新于
          <strong>{{
            productsQuery.data.value
              ? dayjs(productsQuery.data.value.data_updated_at).format('MM-DD HH:mm')
              : '同步中'
          }}</strong></span
        >
        <el-button
          :icon="Refresh"
          :loading="productsQuery.isFetching.value"
          @click="productsQuery.refetch()"
          >刷新</el-button
        >
      </div>
    </header>

    <section class="exception-strip" aria-label="商品异常摘要">
      <button type="button" :class="{ active: !filters.risk }" @click="selectRisk('')">
        <span>当前结果</span><strong>{{ productsQuery.data.value?.summary.total ?? '—' }}</strong>
      </button>
      <button
        type="button"
        class="critical"
        :class="{ active: filters.risk === 'critical' }"
        @click="selectRisk('critical')"
      >
        <span>紧急风险</span
        ><strong>{{ productsQuery.data.value?.summary.critical ?? '—' }}</strong>
      </button>
      <button
        type="button"
        class="warning"
        :class="{ active: filters.risk === 'warning' }"
        @click="selectRisk('warning')"
      >
        <span>待处理</span><strong>{{ productsQuery.data.value?.summary.warning ?? '—' }}</strong>
      </button>
      <div class="exception-strip__context">
        <el-icon><Connection /></el-icon>
        <span><strong>能力限制</strong>{{ capabilityMessage }}</span>
      </div>
    </section>

    <JobProgress
      v-if="currentJob"
      :job="currentJob"
      @close="currentJob = null"
      @retry="retryFailed"
    />

    <FilterBar>
      <el-input
        v-model="filters.q"
        class="search-input"
        clearable
        placeholder="搜索 SKU / 商品标题"
        :prefix-icon="Search"
        @keyup.enter="applySearch"
        @clear="applySearch"
      />
      <el-select v-model="filters.platform" aria-label="平台筛选" @change="filters.page = 1">
        <el-option label="全部平台" value="all" />
        <el-option label="淘宝" value="taobao" />
        <el-option label="抖店" value="douyin" />
        <el-option label="拼多多" value="pinduoduo" />
      </el-select>
      <el-select
        v-model="filters.status"
        aria-label="状态筛选"
        placeholder="全部状态"
        clearable
        @change="filters.page = 1"
      >
        <el-option label="销售中" value="online" />
        <el-option label="已下架" value="offline" />
        <el-option label="草稿" value="draft" />
      </el-select>
      <el-select
        v-model="filters.risk"
        aria-label="风险筛选"
        placeholder="全部风险"
        clearable
        @change="filters.page = 1"
      >
        <el-option label="紧急风险" value="critical" />
        <el-option label="待处理" value="warning" />
        <el-option label="正常" value="normal" />
      </el-select>
      <template #actions>
        <el-button @click="resetFilters">重置</el-button>
        <el-button type="primary" @click="applySearch">查询</el-button>
      </template>
    </FilterBar>

    <section class="table-surface" :aria-busy="productsQuery.isFetching.value">
      <el-alert
        v-if="productsQuery.isError.value"
        type="error"
        :closable="false"
        show-icon
        title="商品数据加载失败，请重试。"
      />
      <EmptyState
        v-else-if="!productsQuery.isLoading.value && !productsQuery.data.value?.items.length"
        title="没有符合条件的商品"
        description="尝试清空部分筛选条件，或切换店铺后重新查询。"
        action-label="重置筛选"
        @action="resetFilters"
      />
      <div v-else class="table-scroll">
        <el-table
          ref="tableRef"
          v-loading="productsQuery.isLoading.value"
          :data="productsQuery.data.value?.items ?? []"
          row-key="id"
          height="540"
          table-layout="fixed"
          @selection-change="handleSelectionChange"
          @sort-change="handleSortChange"
          @row-dblclick="openDetail"
        >
          <el-table-column type="selection" width="44" reserve-selection />
          <el-table-column label="风险" prop="risk" width="112" sortable="custom">
            <template #default="scope"><RiskBadge :risk="scope.row.risk" compact /></template>
          </el-table-column>
          <el-table-column label="商品 / SKU" min-width="260">
            <template #default="scope">
              <button class="product-cell" type="button" @click="openDetail(scope.row)">
                <span class="product-cell__thumb">{{ scope.row.title.slice(0, 1) }}</span>
                <span
                  ><strong>{{ scope.row.title }}</strong
                  ><small>{{ scope.row.sku }} · {{ scope.row.shop_name }}</small></span
                >
              </button>
            </template>
          </el-table-column>
          <el-table-column label="平台" prop="platform" width="90">
            <template #default="scope"
              ><span class="platform-label">{{ scope.row.platform_label }}</span></template
            >
          </el-table-column>
          <el-table-column label="状态" prop="status" width="90">
            <template #default="scope"
              ><span class="status-label" :class="`status-label--${scope.row.status}`">{{
                statusLabels[scope.row.status as ProductStatus]
              }}</span></template
            >
          </el-table-column>
          <el-table-column label="风险原因" min-width="180">
            <template #default="scope">
              <span v-if="scope.row.risk_labels.length" class="risk-reason">{{
                scope.row.risk_labels.join(' · ')
              }}</span>
              <span v-else class="muted">暂无异常</span>
            </template>
          </el-table-column>
          <el-table-column label="售价" prop="price" width="105" align="right" sortable="custom">
            <template #default="scope">{{ currency.format(scope.row.price) }}</template>
          </el-table-column>
          <el-table-column label="库存" prop="stock" width="90" align="right" sortable="custom">
            <template #default="scope"
              ><b :class="{ 'stock-risk': scope.row.stock < 25 }">{{
                scope.row.stock
              }}</b></template
            >
          </el-table-column>
          <el-table-column
            label="7 日销量"
            prop="sales_7d"
            width="110"
            align="right"
            sortable="custom"
          />
          <el-table-column
            label="7 日成交"
            prop="revenue_7d"
            width="125"
            align="right"
            sortable="custom"
          >
            <template #default="scope">{{ currency.format(scope.row.revenue_7d) }}</template>
          </el-table-column>
          <el-table-column
            label="转化率"
            prop="conversion_rate"
            width="105"
            align="right"
            sortable="custom"
          >
            <template #default="scope">{{ scope.row.conversion_rate.toFixed(1) }}%</template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" width="92" align="center">
            <template #default="scope">
              <el-button
                text
                :icon="View"
                aria-label="查看商品详情"
                @click="openDetail(scope.row)"
              />
              <el-button text :icon="MoreFilled" aria-label="更多操作" />
            </template>
          </el-table-column>
        </el-table>
      </div>

      <footer class="table-footer">
        <span>双击行可查看详情；筛选、排序、分页均由服务端完成。</span>
        <el-pagination
          :current-page="filters.page"
          :page-size="filters.page_size"
          :total="productsQuery.data.value?.pagination.total ?? 0"
          layout="total, prev, pager, next"
          size="small"
          @current-change="filters.page = $event"
        />
      </footer>
    </section>

    <BatchActionBar
      v-if="selectedRows.length"
      :count="selectedRows.length"
      :disabled-actions="disabledBatchActions"
      @action="confirmBatch"
      @clear="clearSelection"
    />

    <el-drawer
      v-model="detailOpen"
      class="product-drawer"
      direction="rtl"
      size="min(620px, 100%)"
      destroy-on-close
    >
      <template #header>
        <div class="drawer-heading">
          <span>商品详情 · 演示数据</span>
          <strong>{{ detailQuery.data.value?.title ?? '正在加载商品' }}</strong>
        </div>
      </template>
      <div v-loading="detailQuery.isLoading.value" class="drawer-content">
        <el-alert
          v-if="detailQuery.isError.value"
          title="商品详情加载失败"
          type="error"
          :closable="false"
          show-icon
        />
        <template v-else-if="detailQuery.data.value">
          <section class="drawer-summary">
            <div class="drawer-summary__thumb">{{ detailQuery.data.value.title.slice(0, 1) }}</div>
            <div>
              <RiskBadge :risk="detailQuery.data.value.risk" />
              <h2>{{ detailQuery.data.value.title }}</h2>
              <p>
                {{ detailQuery.data.value.sku }} · {{ detailQuery.data.value.platform_label }} ·
                {{ detailQuery.data.value.shop_name }}
              </p>
            </div>
          </section>
          <div class="drawer-kpis">
            <span
              ><small>售价</small
              ><strong>{{ currency.format(detailQuery.data.value.price) }}</strong></span
            >
            <span
              ><small>库存</small><strong>{{ detailQuery.data.value.stock }}</strong></span
            >
            <span
              ><small>7 日销量</small><strong>{{ detailQuery.data.value.sales_7d }}</strong></span
            >
            <span
              ><small>转化率</small
              ><strong>{{ detailQuery.data.value.conversion_rate.toFixed(1) }}%</strong></span
            >
          </div>
          <section class="drawer-section">
            <h3>基础规格</h3>
            <dl>
              <div v-for="spec in detailQuery.data.value.specs" :key="spec.label">
                <dt>{{ spec.label }}</dt>
                <dd>{{ spec.value }}</dd>
              </div>
            </dl>
          </section>
          <section class="drawer-section">
            <h3>竞品快照</h3>
            <div
              v-for="item in detailQuery.data.value.competitors"
              :key="item.name"
              class="competitor-row"
            >
              <strong>{{ item.name }}</strong
              ><span>{{ currency.format(item.price) }}</span
              ><span>7 日 {{ item.sales_7d }} 件</span><b>{{ item.difference }}</b>
            </div>
          </section>
          <section class="drawer-section ai-section">
            <div class="drawer-section__heading">
              <h3>AI 优化建议</h3>
              <span>绑定当前 SKU 上下文</span>
            </div>
            <article v-for="item in detailQuery.data.value.ai_suggestions" :key="item.title">
              <strong>{{ item.title }}</strong>
              <p>{{ item.detail }}</p>
              <small>{{ item.impact }}</small
              ><button type="button">
                {{ item.action }} <el-icon><ArrowRight /></el-icon>
              </button>
            </article>
          </section>
          <p class="capability-note">
            <el-icon><Connection /></el-icon>{{ detailQuery.data.value.capability_note }}
          </p>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.product-center {
  min-width: 0;
}
.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 16px;
}
.page-heading__eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--primary);
  font-size: var(--font-size-label);
  font-weight: 700;
}
.page-heading__eyebrow b {
  padding: 3px 6px;
  color: var(--success-dark);
  background: var(--success-soft);
  border-radius: 5px;
  font-size: var(--font-size-caption);
}
.page-heading h1 {
  margin: 7px 0 5px;
  font-size: 27px;
  letter-spacing: -0.04em;
}
.page-heading p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-body);
}
.page-heading__meta {
  display: flex;
  align-items: center;
  gap: 9px;
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
}
.page-heading__meta strong {
  color: var(--text-secondary);
}
.exception-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(116px, 160px)) 1fr;
  min-height: 82px;
  margin-bottom: 14px;
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}
.exception-strip > button {
  display: grid;
  align-content: center;
  gap: 3px;
  padding: 14px 18px;
  color: var(--text-secondary);
  background: transparent;
  border: 0;
  border-right: 1px solid var(--border-soft);
  text-align: left;
  cursor: pointer;
}
.exception-strip > button:hover,
.exception-strip > button.active {
  background: var(--primary-softer);
}
.exception-strip > button span {
  font-size: var(--font-size-meta);
}
.exception-strip > button strong {
  color: var(--text-primary);
  font-size: 25px;
}
.exception-strip > button.critical strong {
  color: var(--danger-dark);
}
.exception-strip > button.warning strong {
  color: var(--warning-dark);
}
.exception-strip__context {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 18px;
  color: var(--text-secondary);
  font-size: var(--font-size-label);
  line-height: 1.5;
}
.exception-strip__context .el-icon {
  flex: none;
  color: var(--primary);
}
.exception-strip__context strong {
  display: block;
  color: var(--text-primary);
}
.search-input {
  width: min(320px, 100%);
}
:deep(.filter-bar .el-select) {
  width: 150px;
}
.table-surface {
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-top: 0;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}
.table-scroll {
  min-width: 0;
  overflow-x: auto;
}
:deep(.el-table) {
  min-width: 1120px;
  color: var(--text-secondary);
}
:deep(.el-table th.el-table__cell) {
  height: 46px;
  color: var(--text-secondary);
  background: var(--surface-subtle);
  font-size: var(--font-size-label);
  font-weight: 700;
}
:deep(.el-table td.el-table__cell) {
  padding-block: 9px;
  border-bottom-color: var(--border-soft);
}
:deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--primary-softer) !important;
}
.product-cell {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 10px;
  padding: 0;
  color: inherit;
  background: transparent;
  border: 0;
  text-align: left;
  cursor: pointer;
}
.product-cell__thumb,
.drawer-summary__thumb {
  display: grid;
  flex: none;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 8px;
  font-weight: 800;
}
.product-cell__thumb {
  width: 38px;
  height: 38px;
}
.product-cell strong,
.product-cell small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.product-cell strong {
  max-width: 220px;
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.product-cell small {
  max-width: 240px;
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.platform-label,
.status-label {
  display: inline-flex;
  padding: 4px 7px;
  border-radius: 5px;
  font-size: var(--font-size-meta);
  font-weight: 700;
}
.platform-label {
  color: var(--primary);
  background: var(--primary-soft);
}
.status-label--online {
  color: var(--success-dark);
  background: var(--success-soft);
}
.status-label--offline {
  color: var(--danger-dark);
  background: var(--danger-soft);
}
.status-label--draft {
  color: var(--text-secondary);
  background: var(--surface-muted);
}
.risk-reason {
  color: var(--danger-dark);
  font-size: var(--font-size-label);
}
.muted {
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
}
.stock-risk {
  color: var(--danger-dark);
}
.table-footer {
  display: flex;
  min-height: 58px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 16px;
  color: var(--text-tertiary);
  border-top: 1px solid var(--border-soft);
  font-size: var(--font-size-meta);
}
.drawer-heading span,
.drawer-heading strong {
  display: block;
}
.drawer-heading span {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.drawer-heading strong {
  margin-top: 4px;
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
}
.drawer-content {
  min-height: 420px;
}
.drawer-summary {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border-soft);
}
.drawer-summary__thumb {
  width: 64px;
  height: 64px;
  font-size: 22px;
}
.drawer-summary h2 {
  margin: 9px 0 4px;
  font-size: 19px;
}
.drawer-summary p {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
}
.drawer-kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin: 18px 0;
  background: var(--surface-subtle);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
}
.drawer-kpis span {
  padding: 13px;
  border-right: 1px solid var(--border-soft);
}
.drawer-kpis span:last-child {
  border-right: 0;
}
.drawer-kpis small,
.drawer-kpis strong {
  display: block;
}
.drawer-kpis small {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.drawer-kpis strong {
  margin-top: 5px;
  font-size: var(--font-size-subtitle);
}
.drawer-section {
  padding: 18px 0;
  border-top: 1px solid var(--border-soft);
}
.drawer-section h3 {
  margin: 0 0 12px;
  font-size: var(--font-size-body);
}
dl {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 20px;
  margin: 0;
}
dl div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: var(--font-size-label);
}
dt {
  color: var(--text-tertiary);
}
dd {
  margin: 0;
  color: var(--text-primary);
  font-weight: 600;
}
.competitor-row {
  display: grid;
  grid-template-columns: 1fr 90px 110px 90px;
  gap: 8px;
  padding: 9px 0;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-soft);
  font-size: var(--font-size-label);
}
.competitor-row:last-child {
  border-bottom: 0;
}
.competitor-row b {
  color: var(--warning-dark);
}
.drawer-section__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.drawer-section__heading span {
  color: var(--primary);
  font-size: var(--font-size-meta);
}
.ai-section article {
  position: relative;
  padding: 13px 124px 13px 14px;
  background: var(--primary-softer);
  border: 1px solid #dce8fb;
  border-radius: var(--radius-md);
}
.ai-section article + article {
  margin-top: 9px;
}
.ai-section article strong {
  font-size: var(--font-size-body);
}
.ai-section article p {
  margin: 5px 0;
  color: var(--text-secondary);
  font-size: var(--font-size-label);
  line-height: 1.5;
}
.ai-section article small {
  color: var(--success-dark);
  font-size: var(--font-size-meta);
}
.ai-section article button {
  position: absolute;
  top: 50%;
  right: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 7px 9px;
  color: var(--primary);
  background: #fff;
  border: 1px solid #cbdcf6;
  border-radius: 6px;
  font-size: var(--font-size-meta);
  font-weight: 700;
  transform: translateY(-50%);
  cursor: pointer;
}
.capability-note {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin: 0;
  padding: 12px;
  color: var(--warning-dark);
  background: var(--warning-soft);
  border-radius: var(--radius-md);
  font-size: var(--font-size-label);
  line-height: 1.5;
}
@media (max-width: 900px) {
  .exception-strip {
    grid-template-columns: repeat(3, 1fr);
  }
  .exception-strip__context {
    grid-column: 1 / -1;
    justify-content: flex-start;
    border-top: 1px solid var(--border-soft);
  }
}
@media (max-width: 820px) {
  .search-input,
  :deep(.filter-bar .el-select) {
    width: 100%;
  }
}
@media (max-width: 680px) {
  .page-heading {
    flex-direction: column;
  }
  .page-heading__meta {
    width: 100%;
    justify-content: space-between;
  }
  .exception-strip > button {
    padding: 11px;
  }
  .exception-strip > button strong {
    font-size: 21px;
  }
  .table-footer {
    align-items: flex-start;
    flex-direction: column;
  }
  .drawer-kpis {
    grid-template-columns: 1fr 1fr;
  }
  .drawer-kpis span:nth-child(2) {
    border-right: 0;
  }
  .drawer-kpis span:nth-child(-n + 2) {
    border-bottom: 1px solid var(--border-soft);
  }
  .competitor-row {
    grid-template-columns: 1fr 1fr;
  }
  .ai-section article {
    padding-right: 14px;
    padding-bottom: 52px;
  }
  .ai-section article button {
    inset: auto auto 12px 14px;
    transform: none;
  }
}
</style>
