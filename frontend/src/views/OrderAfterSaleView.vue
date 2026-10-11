<script setup lang="ts">
import {
  Bell,
  ChatDotRound,
  Clock,
  DocumentChecked,
  Refresh,
  Search,
  Select,
  WarningFilled,
} from '@element-plus/icons-vue'
import { useMutation, useQuery } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { orderApi } from '../api'
import ActionJobPanel from '../components/business/ActionJobPanel.vue'
import EmptyState from '../components/business/EmptyState.vue'
import FilterBar from '../components/business/FilterBar.vue'
import RiskBadge from '../components/business/RiskBadge.vue'
import { useSessionStore } from '../stores/session'
import { useWorkspaceStore } from '../stores/workspace'
import type {
  AfterSaleStatus,
  CapabilityMode,
  OrderAction,
  OrderActionJob,
  OrderListItem,
  OrderRisk,
  OrderStatus,
  Platform,
} from '../types/api'
import { getSlaDisplay } from '../utils/orders'

const route = useRoute()
const session = useSessionStore()
const workspace = useWorkspaceStore()
const tableRef = ref()
const selectedRows = ref<OrderListItem[]>([])
const detailId = ref('')
const detailOpen = ref(false)
const replyDraft = ref('')
const currentJob = ref<OrderActionJob | null>(null)
const actionBusy = ref(false)
const deepLinkHandled = ref(false)
let jobTimer: ReturnType<typeof setTimeout> | null = null

const deepLinkedOrder = computed(() =>
  typeof route.query.order === 'string' ? route.query.order.trim() : '',
)
const searchInput = ref(deepLinkedOrder.value)
const filters = reactive({
  q: deepLinkedOrder.value,
  platform: 'all' as Platform,
  status: '' as OrderStatus | '',
  after_sale_status: '' as AfterSaleStatus | '',
  risk: '' as OrderRisk | '',
  sla: '' as '' | 'overdue' | 'two_hours' | 'today',
  sort_by: 'risk',
  sort_order: 'desc' as 'asc' | 'desc',
  page: 1,
  page_size: 10,
})

const queryKey = computed(() => [
  'orders',
  workspace.currentShopId,
  filters.platform,
  filters.q,
  filters.status,
  filters.after_sale_status,
  filters.risk,
  filters.sla,
  filters.sort_by,
  filters.sort_order,
  filters.page,
  filters.page_size,
])
const ordersQuery = useQuery({
  queryKey,
  queryFn: () =>
    orderApi.list(session.token!, {
      shop_id: workspace.currentShopId,
      platform: filters.platform,
      q: filters.q,
      status: filters.status,
      after_sale_status: filters.after_sale_status,
      risk: filters.risk,
      sla: filters.sla,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
      page: filters.page,
      page_size: filters.page_size,
    }),
  enabled: computed(() => Boolean(session.token)),
})
const detailQuery = useQuery({
  queryKey: computed(() => ['order-detail', detailId.value]),
  queryFn: () => orderApi.detail(session.token!, detailId.value),
  enabled: computed(() => Boolean(session.token && detailId.value && detailOpen.value)),
})
const auditQuery = useQuery({
  queryKey: computed(() => ['order-audit', detailId.value]),
  queryFn: () => orderApi.audit(session.token!, detailId.value),
  enabled: computed(() => Boolean(session.token && detailId.value && detailOpen.value)),
})
const actionMutation = useMutation({
  mutationFn: (request: {
    action: OrderAction
    orderIds: string[]
    payload?: Record<string, unknown>
  }) =>
    orderApi.createActionJob(session.token!, {
      action: request.action,
      order_ids: request.orderIds,
      payload: request.payload,
      idempotency_key: `${request.action}-${Date.now()}-${request.orderIds.join('-')}`,
    }),
})

const currency = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  maximumFractionDigits: 0,
})
const orderStatusLabels: Record<OrderStatus, string> = {
  pending_shipment: '待发货',
  shipped: '已发货',
  completed: '已完成',
  closed: '已关闭',
}
const afterSaleLabels: Record<AfterSaleStatus, string> = {
  none: '无售后',
  requested: '售后申请中',
  merchant_processing: '商家处理中',
  buyer_returning: '买家退货中',
  refund_processing: '退款处理中',
  resolved: '售后完结',
}
const actionLabels: Record<OrderAction, string> = {
  remind_ship: '催促发货',
  approve_refund: '同意退款',
  reject_refund: '拒绝退款',
  send_reply: '发送回复',
  mark_follow_up: '标记跟进',
}
const capabilityByKey = computed(() =>
  Object.fromEntries(workspace.capabilities.map((item) => [item.key, item])),
)
const isSingleShop = computed(() => workspace.isSingleShop)
const canOperate = computed(() => isSingleShop.value && session.hasPermission('after_sale:operate'))
const capabilityMessage = computed(() => {
  if (!isSingleShop.value) return '全部店铺视角仅支持监控与筛选；执行动作前请切换到单个店铺。'
  if (!session.hasPermission('after_sale:operate')) return '当前账号没有订单售后操作权限。'
  const limits = workspace.capabilities.filter(
    (item) => item.key.startsWith('order.') && !isExecutable(item.mode),
  )
  return limits.length
    ? limits.map((item) => `${item.label}：${item.reason ?? '请前往平台处理'}`).join('；')
    : '当前店铺支持订单动作直接执行或进入异步队列。'
})

function isExecutable(mode: CapabilityMode | undefined) {
  return mode === 'direct' || mode === 'async'
}
function actionCapabilityKey(action: OrderAction) {
  if (action === 'remind_ship') return 'order.remind_ship'
  if (action === 'mark_follow_up') return ''
  return 'order.after_sale'
}
function isActionAllowed(action: OrderAction) {
  if (!canOperate.value) return false
  const key = actionCapabilityKey(action)
  return !key || isExecutable(capabilityByKey.value[key]?.mode)
}
function actionDisabledReason(action: OrderAction) {
  if (!isSingleShop.value) return '请先切换到单个店铺'
  if (!session.hasPermission('after_sale:operate')) return '当前账号没有操作权限'
  const key = actionCapabilityKey(action)
  const capability = key ? capabilityByKey.value[key] : null
  return capability && !isExecutable(capability.mode)
    ? (capability.reason ?? '当前平台不支持此操作')
    : ''
}
function applySearch() {
  filters.q = searchInput.value.trim()
  filters.page = 1
  deepLinkHandled.value = false
}
function resetFilters() {
  searchInput.value = ''
  filters.q = ''
  filters.platform = 'all'
  filters.status = ''
  filters.after_sale_status = ''
  filters.risk = ''
  filters.sla = ''
  filters.sort_by = 'risk'
  filters.sort_order = 'desc'
  filters.page = 1
}
function setSlaFilter(value: '' | 'overdue' | 'two_hours') {
  filters.sla = filters.sla === value ? '' : value
  filters.page = 1
}
function setOrderStatus(value: OrderStatus | '') {
  filters.status = filters.status === value ? '' : value
  filters.page = 1
}
function handleSelectionChange(rows: OrderListItem[]) {
  selectedRows.value = rows
}
function clearSelection() {
  tableRef.value?.clearSelection()
  selectedRows.value = []
}
function handleSortChange({ prop, order }: { prop: string; order: string | null }) {
  filters.sort_by = order ? prop : 'risk'
  filters.sort_order = order === 'ascending' ? 'asc' : 'desc'
  filters.page = 1
}
function openDetail(row: OrderListItem) {
  detailId.value = row.id
  replyDraft.value = ''
  detailOpen.value = true
}
function closeDetail() {
  detailOpen.value = false
  replyDraft.value = ''
}
function fillReply(content: string) {
  replyDraft.value = content
  ElMessage.success('AI 建议已填入待确认回复，请核对后再发送。')
}

async function confirmAction(action: OrderAction, count: number) {
  const highRisk = ['approve_refund', 'reject_refund', 'send_reply'].includes(action)
  const message = highRisk
    ? `${actionLabels[action]}会创建可审计任务。请再次确认订单、金额和回复内容；演示环境不会写入真实平台。`
    : `确认对 ${count} 个订单执行“${actionLabels[action]}”吗？任务会记录逐项结果。`
  try {
    await ElMessageBox.confirm(message, highRisk ? '高风险操作确认' : '确认执行', {
      confirmButtonText: highRisk ? '已核对，创建任务' : '创建任务',
      cancelButtonText: '取消',
      type: highRisk ? 'warning' : 'info',
    })
    return true
  } catch {
    return false
  }
}
async function runAction(
  action: OrderAction,
  orderIds: string[],
  payload?: Record<string, unknown>,
) {
  if (!orderIds.length) return
  if (!isActionAllowed(action)) {
    ElMessage.warning(actionDisabledReason(action))
    return
  }
  if (action === 'send_reply' && !String(payload?.content ?? '').trim()) {
    ElMessage.warning('请先填写并核对回复内容。')
    return
  }
  if (!(await confirmAction(action, orderIds.length))) return
  actionBusy.value = true
  try {
    currentJob.value = await actionMutation.mutateAsync({ action, orderIds, payload })
    ElMessage.success('任务已进入演示队列，可在页面查看执行进度。')
    pollJob(currentJob.value.id)
  } catch {
    ElMessage.error('任务创建失败，请稍后重试。')
  } finally {
    actionBusy.value = false
  }
}
function pollJob(jobId: string) {
  if (jobTimer) clearTimeout(jobTimer)
  jobTimer = setTimeout(async () => {
    try {
      currentJob.value = await orderApi.job(session.token!, jobId)
      if (['queued', 'running'].includes(currentJob.value.status)) {
        pollJob(jobId)
        return
      }
      await Promise.all([ordersQuery.refetch(), auditQuery.refetch(), detailQuery.refetch()])
      if (currentJob.value.status === 'partial') {
        ElMessage.warning('任务部分成功，请查看失败原因并重试失败项。')
      } else {
        ElMessage.success('任务执行完成，审计记录已更新。')
      }
    } catch {
      ElMessage.error('任务状态刷新失败，请稍后重试。')
    }
  }, 700)
}
function retryFailedItems() {
  if (!currentJob.value) return
  const failedIds = currentJob.value.results
    .filter((item) => !item.success)
    .map((item) => item.order_id)
  if (failedIds.length) void runAction(currentJob.value.action, failedIds)
}
watch(
  () => ordersQuery.data.value?.items,
  (items) => {
    if (!deepLinkedOrder.value || deepLinkHandled.value || !items?.length) return
    const target = items.find((item) => item.order_no === deepLinkedOrder.value)
    if (target) {
      deepLinkHandled.value = true
      openDetail(target)
    }
  },
  { immediate: true },
)
watch(
  () => workspace.currentShopId,
  () => {
    clearSelection()
    detailOpen.value = false
    filters.page = 1
  },
)
onBeforeUnmount(() => {
  if (jobTimer) clearTimeout(jobTimer)
})
</script>

<template>
  <div class="orders-view">
    <header class="page-heading">
      <div>
        <div class="page-heading__eyebrow"><span>订单与售后</span><b>演示数据</b></div>
        <h1>SLA 风险处置台</h1>
        <p>按服务端时限口径锁定即将超时的订单，在单店上下文中完成确认、执行与审计。</p>
      </div>
      <div class="page-heading__meta">
        <el-icon><Clock /></el-icon>
        <span
          >更新于
          <strong>{{
            ordersQuery.data.value
              ? dayjs(ordersQuery.data.value.data_updated_at).format('YYYY-MM-DD HH:mm')
              : '同步中'
          }}</strong></span
        >
        <el-button
          :icon="Refresh"
          :loading="ordersQuery.isFetching.value"
          @click="ordersQuery.refetch()"
          >刷新</el-button
        >
      </div>
    </header>

    <el-alert
      class="environment-note"
      type="warning"
      :closable="false"
      show-icon
      title="当前为演示闭环：敏感信息已脱敏，任务与审计保存在进程内存中，服务重启后会清空；不会写入真实电商平台。"
    />
    <el-alert
      v-if="ordersQuery.isError.value"
      class="load-error"
      type="error"
      :closable="false"
      show-icon
      title="订单列表加载失败，请检查后端服务后重试。"
    />

    <template v-if="ordersQuery.data.value">
      <section class="sla-runway" aria-label="SLA 风险态势">
        <div class="sla-runway__lead">
          <span>SLA 风险跑道</span
          ><strong>{{ ordersQuery.data.value.summary.critical }} 单需优先处置</strong>
          <small>倒计时由服务端计算，刷新与休眠不会改变口径。</small>
        </div>
        <button
          type="button"
          class="sla-card sla-card--danger"
          :class="{ 'is-active': filters.sla === 'overdue' }"
          @click="setSlaFilter('overdue')"
        >
          <span>已经超时</span><strong>{{ ordersQuery.data.value.summary.overdue }}</strong
          ><small>立即处理</small>
        </button>
        <button
          type="button"
          class="sla-card sla-card--warning"
          :class="{ 'is-active': filters.sla === 'two_hours' }"
          @click="setSlaFilter('two_hours')"
        >
          <span>2 小时内</span><strong>{{ ordersQuery.data.value.summary.due_within_2h }}</strong
          ><small>锁定责任人</small>
        </button>
        <div class="sla-card">
          <span>待处理售后</span
          ><strong>{{ ordersQuery.data.value.summary.pending_after_sale }}</strong
          ><small>申请与退款流程</small>
        </div>
        <button
          type="button"
          class="sla-card"
          :class="{ 'is-active': filters.status === 'pending_shipment' }"
          @click="setOrderStatus('pending_shipment')"
        >
          <span>待发货</span><strong>{{ ordersQuery.data.value.summary.pending_shipment }}</strong
          ><small>关注承诺时效</small>
        </button>
        <div class="sla-card sla-card--loss">
          <span>预估风险损失</span
          ><strong>{{ currency.format(ordersQuery.data.value.summary.estimated_loss) }}</strong
          ><small>估算值，非财务结算</small>
        </div>
      </section>

      <ActionJobPanel
        v-if="currentJob"
        :job="currentJob"
        @close="currentJob = null"
        @retry="retryFailedItems"
      />

      <section class="orders-workbench">
        <FilterBar>
          <el-input
            v-model="searchInput"
            class="search-input"
            clearable
            placeholder="订单号 / 买家 / 商品 / SKU"
            :prefix-icon="Search"
            @keyup.enter="applySearch"
            @clear="applySearch"
          />
          <el-select v-model="filters.platform" aria-label="平台筛选" @change="filters.page = 1">
            <el-option label="全部平台" value="all" /><el-option
              label="淘宝"
              value="taobao"
            /><el-option label="抖店" value="douyin" /><el-option
              label="拼多多"
              value="pinduoduo"
            />
          </el-select>
          <el-select
            v-model="filters.status"
            clearable
            placeholder="订单状态"
            @change="filters.page = 1"
          >
            <el-option
              v-for="(label, value) in orderStatusLabels"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
          <el-select
            v-model="filters.after_sale_status"
            clearable
            placeholder="售后状态"
            @change="filters.page = 1"
          >
            <el-option
              v-for="(label, value) in afterSaleLabels"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
          <el-select
            v-model="filters.risk"
            clearable
            placeholder="风险等级"
            @change="filters.page = 1"
          >
            <el-option label="紧急风险" value="critical" /><el-option
              label="待处理"
              value="warning"
            /><el-option label="正常" value="normal" />
          </el-select>
          <el-select
            v-model="filters.sla"
            clearable
            placeholder="SLA 时限"
            @change="filters.page = 1"
          >
            <el-option label="已经超时" value="overdue" /><el-option
              label="2 小时内"
              value="two_hours"
            /><el-option label="今日到期" value="today" />
          </el-select>
          <template #actions
            ><el-button @click="resetFilters">重置</el-button
            ><el-button type="primary" :icon="Search" @click="applySearch"
              >查询</el-button
            ></template
          >
        </FilterBar>

        <div class="capability-strip" :class="{ 'is-limited': !canOperate }">
          <div>
            <el-icon><DocumentChecked /></el-icon><span>{{ capabilityMessage }}</span>
          </div>
          <small>当前店铺：{{ workspace.currentShop?.name ?? '载入中' }}</small>
        </div>
        <div v-if="selectedRows.length" class="batch-strip">
          <div>
            <strong>已选 {{ selectedRows.length }} 单</strong
            ><span>批量动作将逐项返回结果，3 单以上演示任务会包含 1 个失败项。</span>
          </div>
          <div>
            <el-tooltip
              :content="actionDisabledReason('remind_ship')"
              :disabled="isActionAllowed('remind_ship')"
              ><span
                ><el-button
                  :disabled="!isActionAllowed('remind_ship')"
                  :loading="actionBusy"
                  @click="
                    runAction(
                      'remind_ship',
                      selectedRows.map((item) => item.id),
                    )
                  "
                  >批量催发货</el-button
                ></span
              ></el-tooltip
            >
            <el-button
              type="primary"
              :disabled="!isActionAllowed('mark_follow_up')"
              :loading="actionBusy"
              @click="
                runAction(
                  'mark_follow_up',
                  selectedRows.map((item) => item.id),
                )
              "
              >标记跟进</el-button
            >
            <el-button text @click="clearSelection">取消选择</el-button>
          </div>
        </div>

        <div class="table-shell">
          <el-table
            ref="tableRef"
            v-loading="ordersQuery.isFetching.value"
            :data="ordersQuery.data.value.items"
            row-key="id"
            table-layout="fixed"
            :default-sort="{ prop: 'risk', order: 'descending' }"
            @selection-change="handleSelectionChange"
            @sort-change="handleSortChange"
            @row-dblclick="openDetail"
          >
            <el-table-column type="selection" width="46" fixed="left" />
            <el-table-column label="订单 / 店铺" width="190" fixed="left"
              ><template #default="{ row }"
                ><button class="order-link" type="button" @click="openDetail(row)">
                  <strong>{{ row.order_no }}</strong
                  ><span>{{ row.platform_label }} · {{ row.shop_name }}</span>
                </button></template
              ></el-table-column
            >
            <el-table-column label="买家 / 商品" width="210"
              ><template #default="{ row }"
                ><div class="buyer-product">
                  <strong>{{ row.buyer_masked }} · {{ row.item_title }}</strong
                  ><span>{{ row.sku }} × {{ row.quantity }}</span>
                </div></template
              ></el-table-column
            >
            <el-table-column prop="amount" label="实付金额" width="112" sortable="custom"
              ><template #default="{ row }"
                ><strong class="amount">{{ currency.format(row.amount) }}</strong></template
              ></el-table-column
            >
            <el-table-column label="订单状态" width="104"
              ><template #default="{ row }"
                ><span class="status-chip">{{
                  orderStatusLabels[row.order_status as OrderStatus]
                }}</span></template
              ></el-table-column
            >
            <el-table-column label="售后状态" width="120"
              ><template #default="{ row }"
                ><span
                  :class="['after-sale-chip', { 'is-active': row.after_sale_status !== 'none' }]"
                  >{{ afterSaleLabels[row.after_sale_status as AfterSaleStatus] }}</span
                ></template
              ></el-table-column
            >
            <el-table-column prop="risk" label="风险" width="108" sortable="custom"
              ><template #default="{ row }"><RiskBadge :risk="row.risk" compact /></template
            ></el-table-column>
            <el-table-column label="SLA 时限" width="178"
              ><template #default="{ row }"
                ><div
                  :class="['sla-cell', `sla-cell--${getSlaDisplay(row.remaining_minutes).tone}`]"
                >
                  <strong>{{ getSlaDisplay(row.remaining_minutes).label }}</strong
                  ><span v-if="row.sla_deadline">{{
                    dayjs(row.sla_deadline).format('MM-DD HH:mm')
                  }}</span>
                </div></template
              ></el-table-column
            >
            <el-table-column prop="estimated_loss" label="预估损失" width="118" sortable="custom"
              ><template #default="{ row }"
                ><strong :class="{ 'loss-value': row.estimated_loss > 0 }">{{
                  currency.format(row.estimated_loss)
                }}</strong></template
              ></el-table-column
            >
            <el-table-column label="风险原因" min-width="210"
              ><template #default="{ row }"
                ><div class="reason-list">
                  <span v-for="reason in row.risk_reasons.slice(0, 2)" :key="reason">{{
                    reason
                  }}</span>
                </div></template
              ></el-table-column
            >
            <el-table-column label="操作" width="96" fixed="right"
              ><template #default="{ row }"
                ><el-button type="primary" text @click="openDetail(row)">处置</el-button></template
              ></el-table-column
            >
            <template #empty
              ><EmptyState
                title="没有匹配的订单"
                description="请调整店铺、风险或 SLA 条件；演示数据共 12 条。"
                action-label="重置筛选"
                @action="resetFilters"
            /></template>
          </el-table>
        </div>
        <footer class="table-footer">
          <span
            >共 {{ ordersQuery.data.value.pagination.total }} 条 · 默认按风险与预估损失优先</span
          >
          <el-pagination
            v-model:current-page="filters.page"
            v-model:page-size="filters.page_size"
            :total="ordersQuery.data.value.pagination.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
          />
        </footer>
      </section>
    </template>

    <el-drawer
      v-model="detailOpen"
      class="order-drawer"
      direction="rtl"
      size="min(680px, 100%)"
      :with-header="false"
      @closed="closeDetail"
    >
      <div v-if="detailQuery.isLoading.value" class="drawer-loading">正在加载订单处置上下文…</div>
      <div v-else-if="detailQuery.data.value" class="drawer-content">
        <header class="drawer-hero">
          <div>
            <span
              >{{ detailQuery.data.value.platform_label }} ·
              {{ detailQuery.data.value.shop_name }}</span
            >
            <h2>{{ detailQuery.data.value.order_no }}</h2>
            <p>{{ detailQuery.data.value.item_title }} · {{ detailQuery.data.value.sku }}</p>
          </div>
          <div class="drawer-hero__risk">
            <RiskBadge :risk="detailQuery.data.value.risk" /><strong>{{
              getSlaDisplay(detailQuery.data.value.remaining_minutes).label
            }}</strong>
          </div>
        </header>
        <el-alert
          class="masking-note"
          type="info"
          :closable="false"
          show-icon
          title="买家姓名、手机号、地址和物流单号已脱敏。真实环境需按角色权限申请查看。"
        />
        <section class="drawer-kpis">
          <span
            ><small>实付金额</small
            ><strong>{{ currency.format(detailQuery.data.value.amount) }}</strong></span
          >
          <span
            ><small>预估损失</small
            ><strong class="loss-value">{{
              currency.format(detailQuery.data.value.estimated_loss)
            }}</strong></span
          >
          <span
            ><small>订单状态</small
            ><strong>{{ orderStatusLabels[detailQuery.data.value.order_status] }}</strong></span
          >
          <span
            ><small>售后状态</small
            ><strong>{{ afterSaleLabels[detailQuery.data.value.after_sale_status] }}</strong></span
          >
        </section>
        <section class="drawer-section identity-grid">
          <div>
            <span>买家</span><strong>{{ detailQuery.data.value.buyer_masked }}</strong>
          </div>
          <div>
            <span>手机号</span><strong>{{ detailQuery.data.value.buyer_phone_masked }}</strong>
          </div>
          <div class="is-wide">
            <span>收货地址</span
            ><strong>{{ detailQuery.data.value.shipping_address_masked }}</strong>
          </div>
          <div>
            <span>物流公司</span
            ><strong>{{ detailQuery.data.value.logistics_company ?? '暂未发货' }}</strong>
          </div>
          <div>
            <span>物流单号</span
            ><strong>{{ detailQuery.data.value.tracking_no_masked ?? '暂未生成' }}</strong>
          </div>
        </section>
        <section class="drawer-section">
          <div class="section-title">
            <div>
              <span>订单商品</span>
              <h3>金额与 SKU 核对</h3>
            </div>
            <small>共 {{ detailQuery.data.value.lines.length }} 项</small>
          </div>
          <div v-for="line in detailQuery.data.value.lines" :key="line.sku" class="line-item">
            <div>
              <strong>{{ line.title }}</strong
              ><span>{{ line.sku }}</span>
            </div>
            <span>× {{ line.quantity }}</span
            ><strong>{{ currency.format(line.unit_price * line.quantity) }}</strong>
          </div>
        </section>
        <section class="drawer-section">
          <div class="section-title">
            <div>
              <span>处理轨迹</span>
              <h3>平台时限与关键节点</h3>
            </div>
            <small>服务端口径</small>
          </div>
          <el-timeline class="order-timeline"
            ><el-timeline-item
              v-for="item in detailQuery.data.value.timeline"
              :key="`${item.time}-${item.title}`"
              :timestamp="dayjs(item.time).format('MM-DD HH:mm')"
              :type="
                item.state === 'critical'
                  ? 'danger'
                  : item.state === 'warning'
                    ? 'warning'
                    : 'primary'
              "
              placement="top"
              ><strong>{{ item.title }}</strong>
              <p>{{ item.detail }}</p></el-timeline-item
            ></el-timeline
          >
        </section>
        <section class="drawer-section conversation-section">
          <div class="section-title">
            <div>
              <span>买家会话</span>
              <h3>最近沟通上下文</h3>
            </div>
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <div
            v-for="message in detailQuery.data.value.conversation"
            :key="message.id"
            :class="['message-bubble', `message-bubble--${message.sender_type}`]"
          >
            <div>
              <strong>{{ message.sender }}</strong
              ><span>{{ dayjs(message.sent_at).format('HH:mm') }}</span>
            </div>
            <p>{{ message.content }}</p>
          </div>
        </section>
        <section class="drawer-section ai-reply-section">
          <div class="section-title">
            <div>
              <span>AI 回复建议</span>
              <h3>引用当前订单事实，不自动发送</h3>
            </div>
            <el-icon><Select /></el-icon>
          </div>
          <article v-for="reply in detailQuery.data.value.ai_replies" :key="reply.id">
            <div>
              <strong>{{ reply.tone }}</strong
              ><button type="button" @click="fillReply(reply.content)">填入待确认区</button>
            </div>
            <p>{{ reply.content }}</p>
            <small>依据：{{ reply.evidence.join(' · ') }}</small>
          </article>
          <el-input
            v-model="replyDraft"
            class="reply-editor"
            type="textarea"
            :rows="4"
            maxlength="300"
            show-word-limit
            placeholder="选择 AI 建议或手动输入；发送前必须人工确认。"
          />
          <div class="reply-actions">
            <span>AI 仅生成草稿，当前内容不会自动触达买家。</span
            ><el-tooltip
              :content="actionDisabledReason('send_reply')"
              :disabled="isActionAllowed('send_reply')"
              ><span
                ><el-button
                  type="primary"
                  :disabled="!isActionAllowed('send_reply') || !replyDraft.trim()"
                  :loading="actionBusy"
                  @click="
                    runAction('send_reply', [detailQuery.data.value.id], { content: replyDraft })
                  "
                  >核对并发送</el-button
                ></span
              ></el-tooltip
            >
          </div>
        </section>
        <section class="drawer-section action-section">
          <div class="section-title">
            <div>
              <span>处置动作</span>
              <h3>单订单操作</h3>
            </div>
            <small>先确认，再入队</small>
          </div>
          <el-alert
            v-if="!canOperate"
            type="warning"
            :closable="false"
            :title="capabilityMessage"
          />
          <div class="action-grid">
            <el-tooltip
              v-for="action in detailQuery.data.value.available_actions.filter(
                (item) => item !== 'send_reply',
              )"
              :key="action"
              :content="actionDisabledReason(action)"
              :disabled="isActionAllowed(action)"
              ><span
                ><el-button
                  :type="
                    action === 'approve_refund'
                      ? 'danger'
                      : action === 'mark_follow_up'
                        ? 'primary'
                        : 'default'
                  "
                  :plain="action === 'approve_refund'"
                  :disabled="!isActionAllowed(action)"
                  :loading="actionBusy"
                  @click="runAction(action, [detailQuery.data.value.id])"
                  >{{ actionLabels[action] }}</el-button
                ></span
              ></el-tooltip
            >
          </div>
          <p class="capability-note">
            <el-icon><WarningFilled /></el-icon>{{ detailQuery.data.value.capability_note }}
          </p>
        </section>
        <section class="drawer-section audit-section">
          <div class="section-title">
            <div>
              <span>操作审计</span>
              <h3>最近任务记录</h3>
            </div>
            <el-icon><DocumentChecked /></el-icon>
          </div>
          <div v-if="auditQuery.data.value?.length" class="audit-list">
            <article v-for="entry in auditQuery.data.value" :key="entry.id">
              <span :class="entry.result === 'succeeded' ? 'is-success' : 'is-failure'"></span>
              <div>
                <strong>{{ entry.action_label }} · {{ entry.actor }}</strong>
                <p>{{ entry.note }}</p>
              </div>
              <time>{{ dayjs(entry.created_at).format('MM-DD HH:mm:ss') }}</time>
            </article>
          </div>
          <div v-else class="audit-empty">
            <Bell /><span>暂无操作记录。完成任务后会在这里留下审计轨迹。</span>
          </div>
        </section>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.orders-view {
  min-width: 0;
}
.page-heading {
  display: flex;
  align-items: flex-end;
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
  font-weight: 800;
  letter-spacing: 0.08em;
}
.page-heading__eyebrow b {
  padding: 3px 6px;
  color: var(--warning-dark);
  background: var(--warning-soft);
  border-radius: 4px;
  font-size: var(--font-size-caption);
  letter-spacing: 0;
}
.page-heading h1 {
  margin: 6px 0 5px;
  font-size: clamp(24px, 3vw, 34px);
  letter-spacing: -0.035em;
}
.page-heading p {
  max-width: 760px;
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}
.page-heading__meta {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
}
.page-heading__meta strong {
  color: var(--text-secondary);
}
.environment-note,
.load-error {
  margin-bottom: 14px;
}
.sla-runway {
  position: relative;
  display: grid;
  grid-template-columns: minmax(210px, 1.35fr) repeat(4, minmax(112px, 0.72fr)) minmax(
      155px,
      0.95fr
    );
  overflow: hidden;
  margin-bottom: 14px;
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.sla-runway::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: linear-gradient(180deg, var(--danger), var(--warning), var(--primary));
  content: '';
}
.sla-runway__lead,
.sla-card {
  min-width: 0;
  padding: 16px;
  text-align: left;
}
.sla-runway__lead {
  display: grid;
  align-content: center;
  gap: 4px;
  padding-left: 20px;
  background: linear-gradient(120deg, #f8fbff, #fff);
}
.sla-runway__lead span,
.sla-card span {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
  font-weight: 700;
}
.sla-runway__lead strong {
  font-size: var(--font-size-section-title);
}
.sla-runway__lead small,
.sla-card small {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  line-height: 1.35;
}
.sla-card {
  display: grid;
  align-content: center;
  gap: 3px;
  color: inherit;
  background: transparent;
  border: 0;
  border-left: 1px solid var(--border-soft);
  cursor: default;
}
button.sla-card {
  cursor: pointer;
}
button.sla-card:hover,
.sla-card.is-active {
  background: var(--primary-softer);
}
.sla-card strong {
  font-size: 22px;
  letter-spacing: -0.03em;
}
.sla-card--danger strong {
  color: var(--danger-dark);
}
.sla-card--warning strong {
  color: var(--warning-dark);
}
.sla-card--loss strong {
  color: var(--primary-active);
  font-size: var(--font-size-section-title);
}
.orders-workbench {
  overflow: hidden;
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.orders-workbench :deep(.filter-bar) {
  border: 0;
  border-bottom: 1px solid var(--border-soft);
  border-radius: 0;
}
.search-input {
  width: 240px;
}
:deep(.filter-bar .el-select) {
  width: 132px;
}
.capability-strip,
.batch-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-soft);
}
.capability-strip {
  color: var(--success-dark);
  background: var(--success-soft);
  font-size: var(--font-size-label);
}
.capability-strip.is-limited {
  color: var(--warning-dark);
  background: var(--warning-soft);
}
.capability-strip > div {
  display: flex;
  align-items: center;
  gap: 7px;
}
.capability-strip small {
  color: inherit;
  opacity: 0.8;
}
.batch-strip {
  background: var(--primary-softer);
}
.batch-strip > div:last-child {
  display: flex;
  align-items: center;
  gap: 8px;
}
.batch-strip strong,
.batch-strip span {
  display: block;
}
.batch-strip span {
  margin-top: 2px;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.table-shell {
  max-width: 100%;
  overflow: hidden;
}
.table-shell :deep(.el-table) {
  min-width: 1220px;
}
.table-shell :deep(.el-table__header th) {
  height: 46px;
  color: var(--text-secondary);
  background: var(--surface-subtle);
  font-size: var(--font-size-meta);
  letter-spacing: 0.02em;
}
.table-shell :deep(.el-table__row td) {
  padding: 11px 0;
}
.table-shell :deep(.el-table__body tr:hover > td) {
  background: #f7faff !important;
}
.order-link {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 0;
  color: inherit;
  background: transparent;
  border: 0;
  text-align: left;
  cursor: pointer;
}
.order-link strong {
  color: var(--primary-active);
  font-size: var(--font-size-label);
}
.order-link span,
.buyer-product span {
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.buyer-product {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.buyer-product strong {
  overflow: hidden;
  font-size: var(--font-size-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.amount,
.loss-value {
  color: var(--danger-dark);
}
.status-chip,
.after-sale-chip {
  display: inline-flex;
  padding: 4px 7px;
  color: var(--text-secondary);
  background: var(--surface-muted);
  border-radius: 5px;
  font-size: var(--font-size-meta);
  font-weight: 700;
  white-space: nowrap;
}
.after-sale-chip.is-active {
  color: var(--warning-dark);
  background: var(--warning-soft);
}
.sla-cell {
  display: grid;
  gap: 3px;
}
.sla-cell strong {
  font-size: var(--font-size-label);
}
.sla-cell span {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.sla-cell--overdue strong {
  color: var(--danger-dark);
}
.sla-cell--urgent strong,
.sla-cell--today strong {
  color: var(--warning-dark);
}
.sla-cell--safe strong {
  color: var(--success-dark);
}
.sla-cell--none strong {
  color: var(--text-tertiary);
}
.reason-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.reason-list span {
  padding: 3px 5px;
  color: var(--text-secondary);
  background: var(--surface-muted);
  border-radius: 4px;
  font-size: var(--font-size-caption);
}
.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 14px;
  color: var(--text-tertiary);
  border-top: 1px solid var(--border-soft);
  font-size: var(--font-size-meta);
}
.drawer-loading {
  display: grid;
  min-height: 50vh;
  place-items: center;
  color: var(--text-tertiary);
}
.drawer-content {
  padding-bottom: 32px;
}
.drawer-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 18px;
}
.drawer-hero > div:first-child > span,
.section-title > div > span {
  color: var(--primary);
  font-size: var(--font-size-caption);
  font-weight: 800;
  letter-spacing: 0.08em;
}
.drawer-hero h2 {
  margin: 5px 0;
  font-size: 26px;
  letter-spacing: -0.03em;
}
.drawer-hero p {
  margin: 0;
  color: var(--text-secondary);
}
.drawer-hero__risk {
  display: grid;
  justify-items: end;
  gap: 8px;
  text-align: right;
}
.drawer-hero__risk > strong {
  color: var(--danger-dark);
  font-size: var(--font-size-label);
}
.masking-note {
  margin-bottom: 16px;
}
.drawer-kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin: 0 0 16px;
  background: var(--surface-subtle);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
}
.drawer-kpis > span {
  padding: 12px;
  border-right: 1px solid var(--border-soft);
}
.drawer-kpis > span:last-child {
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
  font-size: var(--font-size-body);
}
.drawer-section {
  padding: 18px 0;
  border-top: 1px solid var(--border-soft);
}
.identity-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
}
.identity-grid div {
  display: grid;
  gap: 4px;
  padding: 11px;
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
}
.identity-grid .is-wide {
  grid-column: 1 / -1;
}
.identity-grid span {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.identity-grid strong {
  font-size: var(--font-size-label);
  line-height: 1.5;
}
.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.section-title h3 {
  margin: 3px 0 0;
  font-size: var(--font-size-body);
}
.section-title > small,
.section-title > .el-icon {
  color: var(--text-tertiary);
}
.line-item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 16px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-soft);
  font-size: var(--font-size-label);
}
.line-item:last-child {
  border-bottom: 0;
}
.line-item div {
  display: grid;
  gap: 3px;
}
.line-item div span {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.order-timeline {
  padding: 4px 0 0 3px;
}
.order-timeline strong {
  font-size: var(--font-size-label);
}
.order-timeline p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  line-height: 1.5;
}
.message-bubble {
  width: min(82%, 480px);
  margin-bottom: 9px;
  padding: 10px 12px;
  background: var(--surface-muted);
  border-radius: 4px 12px 12px;
}
.message-bubble--merchant {
  margin-left: auto;
  background: var(--primary-soft);
  border-radius: 12px 4px 12px 12px;
}
.message-bubble > div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: var(--font-size-caption);
}
.message-bubble > div span {
  color: var(--text-tertiary);
}
.message-bubble p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-label);
  line-height: 1.55;
}
.ai-reply-section article {
  padding: 12px;
  background: var(--primary-softer);
  border: 1px solid #dce8fb;
  border-radius: var(--radius-md);
}
.ai-reply-section article + article {
  margin-top: 8px;
}
.ai-reply-section article > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.ai-reply-section article button {
  padding: 0;
  color: var(--primary);
  background: transparent;
  border: 0;
  font-size: var(--font-size-meta);
  font-weight: 700;
  cursor: pointer;
}
.ai-reply-section article p {
  margin: 7px 0;
  color: var(--text-secondary);
  font-size: var(--font-size-label);
  line-height: 1.55;
}
.ai-reply-section article small {
  color: var(--success-dark);
  font-size: var(--font-size-caption);
}
.reply-editor {
  margin-top: 12px;
}
.reply-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 9px;
}
.reply-actions > span {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.action-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.capability-note {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin: 12px 0 0;
  padding: 11px;
  color: var(--warning-dark);
  background: var(--warning-soft);
  border-radius: var(--radius-md);
  font-size: var(--font-size-meta);
  line-height: 1.5;
}
.audit-list {
  display: grid;
  gap: 8px;
}
.audit-list article {
  display: grid;
  grid-template-columns: 8px 1fr auto;
  gap: 9px;
  padding: 10px;
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
}
.audit-list article > span {
  width: 7px;
  height: 7px;
  margin-top: 4px;
  background: var(--success);
  border-radius: 50%;
}
.audit-list article > span.is-failure {
  background: var(--danger);
}
.audit-list strong {
  font-size: var(--font-size-meta);
}
.audit-list p {
  margin: 3px 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
}
.audit-list time {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.audit-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px;
  color: var(--text-tertiary);
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-meta);
}
.audit-empty svg {
  width: 16px;
}
@media (max-width: 1180px) {
  .sla-runway {
    grid-template-columns: repeat(3, 1fr);
  }
  .sla-runway__lead {
    grid-column: 1 / -1;
    border-bottom: 1px solid var(--border-soft);
  }
  .sla-card:nth-child(5) {
    border-left: 0;
  }
}
@media (max-width: 820px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .page-heading__meta {
    width: 100%;
    justify-content: space-between;
  }
  .sla-runway {
    grid-template-columns: repeat(2, 1fr);
  }
  .sla-runway__lead {
    grid-column: 1 / -1;
  }
  .sla-card:nth-child(even) {
    border-left: 0;
  }
  .search-input,
  :deep(.filter-bar .el-select) {
    width: 100%;
  }
  .capability-strip,
  .batch-strip {
    align-items: flex-start;
    flex-direction: column;
  }
  .batch-strip > div:last-child {
    width: 100%;
    flex-wrap: wrap;
  }
  .table-shell {
    overflow-x: auto;
  }
  .table-footer {
    align-items: flex-start;
    flex-direction: column;
    overflow-x: auto;
  }
  .drawer-hero,
  .reply-actions {
    align-items: flex-start;
    flex-direction: column;
  }
  .drawer-hero__risk {
    justify-items: start;
    text-align: left;
  }
}
@media (max-width: 520px) {
  .sla-runway {
    grid-template-columns: 1fr 1fr;
  }
  .sla-card {
    padding: 13px;
  }
  .drawer-kpis,
  .identity-grid {
    grid-template-columns: 1fr 1fr;
  }
  .drawer-kpis > span:nth-child(2) {
    border-right: 0;
  }
  .drawer-kpis > span:nth-child(-n + 2) {
    border-bottom: 1px solid var(--border-soft);
  }
  .identity-grid div:not(.is-wide) {
    grid-column: 1 / -1;
  }
  .message-bubble {
    width: 94%;
  }
  .audit-list article {
    grid-template-columns: 8px 1fr;
  }
  .audit-list time {
    grid-column: 2;
  }
}
</style>
