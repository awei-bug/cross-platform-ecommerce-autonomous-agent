<script setup lang="ts">
import { Clock, Refresh, WarningFilled, TrendCharts } from '@element-plus/icons-vue'
import { useQuery } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import type { EChartsType } from 'echarts/core'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

import { campaignApi } from '../api'
import type { CampaignStatus } from '../types/api'
import { useSessionStore } from '../stores/session'
import { useWorkspaceStore } from '../stores/workspace'

echarts.use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const session = useSessionStore()
const workspace = useWorkspaceStore()
const chartEl = ref<HTMLDivElement | null>(null)
let chart: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null

const filters = reactive<{ account_id: string; status: CampaignStatus | ''; q: string }>({
  account_id: '',
  status: '',
  q: '',
})

const overviewQuery = useQuery({
  queryKey: computed(() => [
    'campaign-overview',
    workspace.currentShopId,
    filters.account_id,
    filters.status,
    filters.q,
  ]),
  queryFn: () =>
    campaignApi.overview(session.token!, {
      shop_id: workspace.currentShopId,
      account_id: filters.account_id,
      status: filters.status || undefined,
      q: filters.q,
    }),
  enabled: computed(() => Boolean(session.token)),
})

const overview = computed(() => overviewQuery.data.value)
const accounts = computed(() => overview.value?.accounts ?? [])
const campaigns = computed(() => overview.value?.campaigns ?? [])
const summary = computed(() => overview.value?.summary)

const formatCurrency = (value: number) => `¥${Math.round(value).toLocaleString('zh-CN')}`
const formatNumber = (value: number) => value.toLocaleString('zh-CN')
const formatPercent = (value: number) => `${value.toFixed(2)}%`

function statusLabel(status: CampaignStatus) {
  return { running: '投放中', paused: '已暂停', review: '待审核' }[status]
}

function statusType(status: CampaignStatus) {
  return { running: 'success', paused: 'info', review: 'warning' }[status] as
    'success' | 'info' | 'warning'
}

function renderChart() {
  const trend = overview.value?.trend
  if (!chartEl.value || !trend) return
  chart ??= echarts.init(chartEl.value)
  chart.setOption({
    animationDuration: 420,
    textStyle: { fontFamily: 'Inter, Microsoft YaHei, sans-serif', fontSize: 14 },
    color: ['#2474f5', '#18a873'],
    tooltip: { trigger: 'axis', valueFormatter: (value: number) => formatCurrency(value) },
    legend: {
      top: 0,
      right: 0,
      itemWidth: 10,
      itemHeight: 6,
      textStyle: { color: '#52627a', fontSize: 14 },
    },
    grid: { top: 44, right: 28, bottom: 28, left: 60 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: trend.map((item) => item.date),
      axisLine: { lineStyle: { color: '#d8e1ed' } },
      axisLabel: { color: '#65758d', fontSize: 13 },
    },
    yAxis: {
      type: 'value',
      name: '金额',
      nameTextStyle: { color: '#65758d', fontSize: 13 },
      splitLine: { lineStyle: { color: '#e7edf5' } },
      axisLabel: {
        color: '#65758d',
        fontSize: 13,
        formatter: (value: number) => `${Math.round(value / 1000)}k`,
      },
    },
    series: [
      {
        name: '广告花费',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        data: trend.map((item) => item.spend),
        lineStyle: { width: 3 },
        areaStyle: { color: 'rgba(36, 116, 245, 0.08)' },
      },
      {
        name: '成交金额',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        data: trend.map((item) => item.revenue),
        lineStyle: { width: 3 },
        areaStyle: { color: 'rgba(24, 168, 115, 0.06)' },
      },
    ],
  })
}

watch(
  () => overview.value,
  async () => {
    await nextTick()
    renderChart()
  },
)

watch(
  () => workspace.currentShopId,
  () => {
    filters.account_id = ''
  },
)

onMounted(() => {
  resizeObserver = new ResizeObserver(() => chart?.resize())
  if (chartEl.value) resizeObserver.observe(chartEl.value)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
})
</script>

<template>
  <div class="campaign-view">
    <header class="page-heading">
      <div>
        <div class="page-heading__eyebrow"><span>投放与广告</span><b>演示数据</b></div>
        <h1>广告计划作战台</h1>
        <p>统一观察各平台投放效率，把预算风险和低效计划先拉到桌面上。</p>
      </div>
      <div class="page-heading__meta">
        <el-icon><Clock /></el-icon>
        <span>
          更新于
          <strong>{{
            overview ? dayjs(overview.data_updated_at).format('YYYY-MM-DD HH:mm') : '同步中'
          }}</strong>
        </span>
        <el-button
          :icon="Refresh"
          :loading="overviewQuery.isFetching.value"
          @click="overviewQuery.refetch()"
        >
          刷新
        </el-button>
      </div>
    </header>

    <el-alert
      v-if="overviewQuery.isError.value"
      class="load-error"
      type="error"
      :closable="false"
      show-icon
      title="广告数据加载失败，请重试。"
    />

    <section class="campaign-toolbar surface-panel">
      <div class="toolbar-title">
        <span>广告账户</span>
        <strong>{{ accounts.length }} 个账户</strong>
      </div>
      <el-select
        v-model="filters.account_id"
        clearable
        placeholder="全部广告账户"
        class="account-select"
      >
        <el-option
          v-for="account in accounts"
          :key="account.id"
          :label="account.name"
          :value="account.id"
        />
      </el-select>
      <el-select v-model="filters.status" clearable placeholder="全部状态" class="status-select">
        <el-option label="投放中" value="running" />
        <el-option label="已暂停" value="paused" />
        <el-option label="待审核" value="review" />
      </el-select>
      <el-input v-model="filters.q" clearable placeholder="搜索计划名称" class="keyword-input" />
      <div class="toolbar-scope">
        <span>{{ workspace.scopePlatformLabel }}</span>
        <strong>{{ workspace.scopeLabel }}</strong>
      </div>
    </section>

    <template v-if="overview">
      <section class="metric-grid campaign-metrics" aria-label="广告核心指标">
        <article class="metric-card metric-card--blue">
          <span>近 7 日广告消耗</span>
          <strong>{{ formatCurrency(summary?.spend ?? 0) }}</strong>
          <small>覆盖 {{ formatNumber(summary?.active_campaigns ?? 0) }} 个投放中计划</small>
        </article>
        <article class="metric-card metric-card--green">
          <span>广告 ROI</span>
          <strong>{{ (summary?.roi ?? 0).toFixed(2) }}</strong>
          <small>成交金额 {{ formatCurrency(summary?.revenue ?? 0) }}</small>
        </article>
        <article class="metric-card metric-card--orange">
          <span>转化单量</span>
          <strong>{{ formatNumber(summary?.conversions ?? 0) }}</strong>
          <small>点击 {{ formatNumber(summary?.clicks ?? 0) }} 次</small>
        </article>
        <article class="metric-card metric-card--red">
          <span>异常计划</span>
          <strong>{{ summary?.anomaly_campaigns ?? 0 }}</strong>
          <small>高花费低转化，建议优先复核</small>
        </article>
      </section>

      <section class="campaign-main-grid">
        <article class="surface-panel trend-panel">
          <div class="section-heading">
            <div>
              <span>投放趋势</span>
              <h2>花费与成交金额</h2>
            </div>
            <small>近 7 日 · 金额口径</small>
          </div>
          <div
            ref="chartEl"
            class="trend-chart"
            role="img"
            aria-label="近七日广告花费和成交金额趋势图"
          ></div>
        </article>

        <article class="surface-panel budget-panel">
          <div class="section-heading">
            <div>
              <span>预算告警</span>
              <h2>接近阈值的账户</h2>
            </div>
            <el-icon class="warning-icon"><WarningFilled /></el-icon>
          </div>
          <div v-if="overview.budget_alerts.length" class="budget-list">
            <div v-for="alert in overview.budget_alerts" :key="alert.id" class="budget-item">
              <div class="budget-item__head">
                <strong>{{ alert.account_name }}</strong>
                <b>{{ alert.usage_percent.toFixed(1) }}%</b>
              </div>
              <el-progress
                :percentage="Math.min(alert.usage_percent, 100)"
                :show-text="false"
                status="warning"
              />
              <small>{{ alert.message }}</small>
              <span>{{ formatCurrency(alert.spend) }} / {{ formatCurrency(alert.budget) }}</span>
            </div>
          </div>
          <div v-else class="empty-copy">当前范围暂无预算告警</div>
        </article>
      </section>

      <section class="surface-panel campaign-table-panel">
        <div class="section-heading">
          <div>
            <span>计划监控</span>
            <h2>广告计划列表</h2>
          </div>
          <small>{{ campaigns.length }} 个计划 · 异常计划优先处理</small>
        </div>
        <el-table
          :data="campaigns"
          row-key="id"
          class="campaign-table"
          :default-sort="{ prop: 'roi', order: 'descending' }"
        >
          <el-table-column label="计划名称" min-width="250">
            <template #default="{ row }">
              <div class="campaign-name">
                <span :class="['platform-dot', `platform-dot--${row.platform}`]"></span>
                <div>
                  <strong>{{ row.name }}</strong>
                  <small>{{ row.shop_name }} · {{ row.account_name }}</small>
                </div>
                <el-tag v-if="row.anomaly" type="danger" effect="plain" size="small">异常</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" effect="light">{{
                statusLabel(row.status)
              }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="曝光" width="115" align="right">
            <template #default="{ row }">{{ formatNumber(row.impressions) }}</template>
          </el-table-column>
          <el-table-column label="点击率" width="105" align="right">
            <template #default="{ row }">{{ formatPercent(row.ctr) }}</template>
          </el-table-column>
          <el-table-column label="花费" width="120" align="right">
            <template #default="{ row }">{{ formatCurrency(row.spend) }}</template>
          </el-table-column>
          <el-table-column label="转化率" width="105" align="right">
            <template #default="{ row }">{{ formatPercent(row.conversion_rate) }}</template>
          </el-table-column>
          <el-table-column label="ROI" width="95" align="right" sortable>
            <template #default="{ row }"
              ><strong :class="{ 'roi-danger': row.roi < 2 }">{{
                row.roi.toFixed(2)
              }}</strong></template
            >
          </el-table-column>
        </el-table>
        <div v-if="!campaigns.length" class="table-empty">当前筛选条件下暂无广告计划</div>
      </section>

      <section class="surface-panel recommendation-panel">
        <div class="section-heading">
          <div>
            <span>AI 投放建议</span>
            <h2>把数据转成下一步动作</h2>
          </div>
          <small>仅供参考，不会自动修改平台广告</small>
        </div>
        <div v-if="overview.recommendations.length" class="recommendation-grid">
          <article
            v-for="recommendation in overview.recommendations"
            :key="recommendation.id"
            class="recommendation-card"
          >
            <div class="recommendation-card__icon">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="recommendation-card__body">
              <div class="recommendation-card__title">
                <strong>{{ recommendation.title }}</strong>
                <el-tag
                  :type="recommendation.level === 'critical' ? 'danger' : 'success'"
                  effect="plain"
                  size="small"
                >
                  {{ recommendation.level === 'critical' ? '需关注' : '可扩量' }}
                </el-tag>
              </div>
              <p>{{ recommendation.detail }}</p>
              <div class="evidence-list">
                <span v-for="evidence in recommendation.evidence" :key="evidence">{{
                  evidence
                }}</span>
              </div>
            </div>
            <el-button text type="primary">{{ recommendation.action }}</el-button>
          </article>
        </div>
        <div v-else class="empty-copy">当前范围暂无 AI 投放建议</div>
      </section>
    </template>
  </div>
</template>

<style scoped lang="scss">
.campaign-view {
  min-width: 0;
}
.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
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
  color: #9a6700;
  background: #fff4d7;
  border-radius: 4px;
  font-size: var(--font-size-caption);
}
.page-heading h1 {
  margin: 7px 0 5px;
  color: var(--text-primary);
  font-size: clamp(24px, 3vw, 32px);
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
  gap: 10px;
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
  white-space: nowrap;
}
.page-heading__meta strong {
  color: var(--text-secondary);
}
.load-error {
  margin-bottom: 14px;
}
.surface-panel {
  min-width: 0;
  padding: 20px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.campaign-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.toolbar-title {
  display: flex;
  min-width: 170px;
  flex-direction: column;
  gap: 3px;
  margin-right: 4px;
}
.toolbar-title span {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.toolbar-title strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.account-select {
  width: 260px;
}
.status-select {
  width: 130px;
}
.keyword-input {
  width: 190px;
}
.toolbar-scope {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-left: auto;
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.toolbar-scope span {
  padding: 4px 7px;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 5px;
  font-size: var(--font-size-meta);
}
.campaign-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 14px;
}
.metric-card {
  position: relative;
  min-height: 118px;
  padding: 18px 20px;
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.metric-card::after {
  position: absolute;
  right: -20px;
  bottom: -42px;
  width: 110px;
  height: 110px;
  content: '';
  border-radius: 50%;
  opacity: 0.1;
}
.metric-card span,
.metric-card small {
  display: block;
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
}
.metric-card strong {
  display: block;
  margin: 9px 0 5px;
  color: var(--text-primary);
  font-size: 26px;
  letter-spacing: -0.04em;
}
.metric-card--blue {
  border-top: 3px solid #2474f5;
}
.metric-card--blue::after {
  background: #2474f5;
}
.metric-card--green {
  border-top: 3px solid #18a873;
}
.metric-card--green::after {
  background: #18a873;
}
.metric-card--orange {
  border-top: 3px solid #f39b26;
}
.metric-card--orange::after {
  background: #f39b26;
}
.metric-card--red {
  border-top: 3px solid #e85d5d;
}
.metric-card--red::after {
  background: #e85d5d;
}
.campaign-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.8fr);
  gap: 14px;
  margin-bottom: 14px;
}
.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 15px;
}
.section-heading > div span {
  color: var(--primary);
  font-size: var(--font-size-meta);
  font-weight: 700;
}
.section-heading h2 {
  margin: 4px 0 0;
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
  letter-spacing: -0.02em;
}
.section-heading > small {
  padding-top: 3px;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
  text-align: right;
}
.trend-chart {
  width: 100%;
  height: 275px;
}
.warning-icon {
  color: #e5a11b;
  font-size: 20px;
}
.budget-list {
  display: grid;
  gap: 19px;
}
.budget-item__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.budget-item__head strong {
  max-width: 210px;
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.budget-item__head b {
  color: #bd7a00;
  font-size: var(--font-size-label);
}
.budget-item small {
  display: block;
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  line-height: 1.5;
}
.budget-item > span {
  display: block;
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.empty-copy,
.table-empty {
  padding: 35px 10px;
  color: var(--text-tertiary);
  font-size: var(--font-size-body);
  text-align: center;
}
.campaign-table-panel {
  margin-bottom: 14px;
}
.campaign-table :deep(.el-table__header th) {
  color: var(--text-tertiary);
  background: #fbfcfe;
  font-size: var(--font-size-meta);
  font-weight: 600;
}
.campaign-table :deep(.el-table__row td) {
  padding-top: 13px;
  padding-bottom: 13px;
}
.campaign-name {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}
.campaign-name > div {
  min-width: 0;
  flex: 1;
}
.campaign-name strong,
.campaign-name small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.campaign-name strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.campaign-name small {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.platform-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
}
.platform-dot--taobao {
  background: #ff6a00;
}
.platform-dot--douyin {
  background: #111827;
}
.platform-dot--pinduoduo {
  background: #e33a2f;
}
.roi-danger {
  color: var(--danger);
}
.recommendation-panel {
  margin-bottom: 12px;
}
.recommendation-grid {
  display: grid;
  gap: 10px;
}
.recommendation-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 13px 14px;
  background: #f8fbff;
  border: 1px solid #e3edf9;
  border-radius: 10px;
}
.recommendation-card__icon {
  display: grid;
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 8px;
}
.recommendation-card__body {
  min-width: 0;
  flex: 1;
}
.recommendation-card__title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.recommendation-card__title strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.recommendation-card p {
  margin: 6px 0 8px;
  color: var(--text-secondary);
  font-size: var(--font-size-label);
  line-height: 1.55;
}
.evidence-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.evidence-list span {
  padding: 3px 6px;
  color: var(--text-tertiary);
  background: #fff;
  border-radius: 4px;
  font-size: var(--font-size-caption);
}
@media (max-width: 1080px) {
  .campaign-toolbar {
    flex-wrap: wrap;
  }
  .toolbar-title {
    min-width: 130px;
  }
  .toolbar-scope {
    width: 100%;
    margin-left: 0;
  }
  .campaign-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 760px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .page-heading__meta {
    width: 100%;
    justify-content: space-between;
  }
  .campaign-main-grid {
    grid-template-columns: 1fr;
  }
  .account-select,
  .keyword-input {
    width: 100%;
  }
  .status-select {
    flex: 1;
    width: auto;
  }
  .campaign-metrics {
    grid-template-columns: 1fr;
  }
  .surface-panel {
    padding: 16px;
  }
  .campaign-table-panel {
    overflow-x: auto;
  }
  .campaign-table {
    min-width: 800px;
  }
  .recommendation-card {
    align-items: flex-start;
    flex-wrap: wrap;
  }
}
</style>
