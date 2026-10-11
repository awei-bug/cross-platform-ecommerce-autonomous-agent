<script setup lang="ts">
import { ArrowRight, Clock, DataAnalysis, Refresh, WarningFilled } from '@element-plus/icons-vue'
import { useQuery } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import type { EChartsType } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { dashboardApi } from '../api'
import EmptyState from '../components/business/EmptyState.vue'
import MetricCard from '../components/business/MetricCard.vue'
import RiskBadge from '../components/business/RiskBadge.vue'
import { useSessionStore } from '../stores/session'
import { useWorkspaceStore } from '../stores/workspace'

echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const router = useRouter()
const session = useSessionStore()
const workspace = useWorkspaceStore()
const chartEl = ref<HTMLDivElement | null>(null)
let chart: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null

const overviewQuery = useQuery({
  queryKey: computed(() => ['dashboard-overview', workspace.currentShopId]),
  queryFn: () => dashboardApi.overview(session.token!, workspace.currentShopId),
  enabled: computed(() => Boolean(session.token)),
})

const currency = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  maximumFractionDigits: 0,
})

function renderChart() {
  const trend = overviewQuery.data.value?.trend
  if (!chartEl.value || !trend) return
  chart ??= echarts.init(chartEl.value)
  chart.setOption({
    animationDuration: 450,
    textStyle: { fontFamily: 'Inter, Microsoft YaHei, sans-serif', fontSize: 14 },
    color: ['#2474f5', '#18a873'],
    tooltip: { trigger: 'axis' },
    legend: {
      top: 0,
      right: 0,
      itemWidth: 10,
      itemHeight: 6,
      textStyle: { color: '#52627a', fontSize: 14 },
    },
    grid: { top: 44, right: 42, bottom: 28, left: 62 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: trend.map((item) => item.date),
      axisLine: { lineStyle: { color: '#d8e1ed' } },
      axisLabel: { color: '#65758d', fontSize: 13 },
    },
    yAxis: [
      {
        type: 'value',
        name: '销售额',
        nameTextStyle: { color: '#65758d', fontSize: 13 },
        splitLine: { lineStyle: { color: '#e7edf5' } },
        axisLabel: {
          color: '#65758d',
          fontSize: 13,
          formatter: (value: number) => `${Math.round(value / 1000)}k`,
        },
      },
      {
        type: 'value',
        name: '订单',
        nameTextStyle: { color: '#65758d', fontSize: 13 },
        splitLine: { show: false },
        axisLabel: { color: '#65758d', fontSize: 13 },
      },
    ],
    series: [
      {
        name: '销售额',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        data: trend.map((item) => item.sales),
        lineStyle: { width: 3 },
        areaStyle: { color: 'rgba(36, 116, 245, 0.08)' },
      },
      {
        name: '订单',
        type: 'bar',
        yAxisIndex: 1,
        barMaxWidth: 16,
        data: trend.map((item) => item.orders),
        itemStyle: { borderRadius: [4, 4, 0, 0], opacity: 0.72 },
      },
    ],
  })
}

watch(
  () => overviewQuery.data.value,
  async () => {
    await nextTick()
    renderChart()
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
  <div class="dashboard-view">
    <header class="page-heading">
      <div>
        <div class="page-heading__eyebrow"><span>运营总览</span><b>演示数据</b></div>
        <h1>今日经营作战面板</h1>
        <p>围绕当前店铺上下文，按预估损失与时效优先处理风险。</p>
      </div>
      <div class="page-heading__meta">
        <el-icon><Clock /></el-icon>
        <span
          >更新于
          <strong>{{
            overviewQuery.data.value
              ? dayjs(overviewQuery.data.value.data_updated_at).format('YYYY-MM-DD HH:mm')
              : '同步中'
          }}</strong></span
        >
        <el-button
          :icon="Refresh"
          :loading="overviewQuery.isFetching.value"
          @click="overviewQuery.refetch()"
          >刷新</el-button
        >
      </div>
    </header>

    <el-alert
      v-if="overviewQuery.isError.value"
      class="load-error"
      type="error"
      :closable="false"
      show-icon
      title="运营总览加载失败，请重试。"
    />

    <template v-if="overviewQuery.data.value">
      <section class="metric-grid" aria-label="核心经营指标">
        <MetricCard
          v-for="metric in overviewQuery.data.value.metrics"
          :key="metric.key"
          :metric="metric"
        />
      </section>

      <section class="primary-grid">
        <article class="surface-panel trend-panel">
          <div class="section-heading">
            <div>
              <span>近 7 日趋势</span>
              <h2>销售额与支付订单</h2>
            </div>
            <small>数据口径：支付成功，退款中订单未扣除</small>
          </div>
          <div
            ref="chartEl"
            class="trend-chart"
            role="img"
            aria-label="近 7 日销售额和订单趋势图"
          ></div>
        </article>

        <article class="surface-panel risk-panel">
          <div class="section-heading">
            <div>
              <span>优先处理</span>
              <h2>风险队列</h2>
            </div>
            <el-icon class="risk-panel__icon"><WarningFilled /></el-icon>
          </div>
          <div v-if="overviewQuery.data.value.risks.length" class="risk-list">
            <button
              v-for="risk in overviewQuery.data.value.risks"
              :key="risk.id"
              type="button"
              @click="router.push(risk.route)"
            >
              <RiskBadge :risk="risk.level" compact />
              <span class="risk-list__copy"
                ><strong>{{ risk.title }}</strong
                ><small>{{ risk.detail }}</small
                ><em>{{ risk.shop_name }} · 截止 {{ risk.deadline }}</em></span
              >
              <span class="risk-list__loss"
                ><small>预估损失</small><strong>{{ currency.format(risk.estimated_loss) }}</strong
                ><el-icon><ArrowRight /></el-icon
              ></span>
            </button>
          </div>
          <EmptyState
            v-else
            title="当前没有高优先级风险"
            description="系统会在下一次数据同步后继续检测。"
          />
        </article>
      </section>

      <section class="secondary-grid">
        <article class="surface-panel task-panel">
          <div class="section-heading">
            <div>
              <span>执行进度</span>
              <h2>今日运营任务</h2>
            </div>
            <small>{{ overviewQuery.data.value.tasks.length }} 项</small>
          </div>
          <div class="task-list">
            <div v-for="task in overviewQuery.data.value.tasks" :key="task.id" class="task-row">
              <div>
                <strong>{{ task.title }}</strong
                ><small>{{ task.owner }} · {{ task.due_at }}</small>
              </div>
              <span>{{ task.status }}</span>
              <div class="task-row__progress">
                <el-progress :percentage="task.progress" :stroke-width="7" /><small
                  >{{ task.progress }}%</small
                >
              </div>
            </div>
          </div>
        </article>

        <article class="surface-panel top-panel">
          <div class="section-heading">
            <div>
              <span>成交贡献</span>
              <h2>热销商品</h2>
            </div>
            <button type="button" @click="router.push('/products')">
              查看全部 <el-icon><ArrowRight /></el-icon>
            </button>
          </div>
          <div class="top-list">
            <button
              v-for="(item, index) in overviewQuery.data.value.top_products"
              :key="item.id"
              type="button"
              @click="router.push(`/products?sku=${item.sku}`)"
            >
              <b>{{ index + 1 }}</b
              ><span
                ><strong>{{ item.title }}</strong
                ><small>{{ item.sku }} · {{ item.platform_label }}</small></span
              ><em
                >{{ currency.format(item.revenue)
                }}<small
                  >{{ item.sales }} 件 · {{ item.trend > 0 ? '+' : '' }}{{ item.trend }}%</small
                ></em
              >
            </button>
          </div>
        </article>

        <article class="surface-panel ai-panel">
          <div class="ai-panel__heading">
            <span
              ><el-icon><DataAnalysis /></el-icon> AI 运营简报</span
            ><small>{{ overviewQuery.data.value.ai_brief.context_label }}</small>
          </div>
          <h2>{{ overviewQuery.data.value.ai_brief.headline }}</h2>
          <p>{{ overviewQuery.data.value.ai_brief.summary }}</p>
          <ul>
            <li v-for="item in overviewQuery.data.value.ai_brief.evidence" :key="item">
              {{ item }}
            </li>
          </ul>
          <div class="ai-panel__actions">
            <button
              v-for="(action, index) in overviewQuery.data.value.ai_brief.actions"
              :key="action"
              type="button"
              @click="index === 0 && router.push('/products?risk=critical')"
            >
              {{ action }} <el-icon><ArrowRight /></el-icon>
            </button>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped lang="scss">
.dashboard-view {
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
.load-error {
  margin-bottom: 14px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 14px;
}
.surface-panel {
  min-width: 0;
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.primary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(360px, 0.8fr);
  gap: 14px;
  margin-bottom: 14px;
}
.trend-panel,
.risk-panel,
.task-panel,
.top-panel,
.ai-panel {
  padding: 18px;
}
.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.section-heading span {
  color: var(--primary);
  font-size: var(--font-size-caption);
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.section-heading h2 {
  margin: 4px 0 0;
  font-size: var(--font-size-subtitle);
}
.section-heading > small {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.section-heading button {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  color: var(--primary);
  background: transparent;
  border: 0;
  font-size: var(--font-size-meta);
  font-weight: 700;
  cursor: pointer;
}
.trend-chart {
  width: 100%;
  height: 330px;
  margin-top: 8px;
}
.risk-panel__icon {
  color: var(--danger);
  font-size: 20px;
}
.risk-list {
  margin-top: 12px;
}
.risk-list > button {
  display: grid;
  width: 100%;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 13px 0;
  color: inherit;
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--border-soft);
  text-align: left;
  cursor: pointer;
}
.risk-list > button:last-child {
  border-bottom: 0;
}
.risk-list > button:hover .risk-list__copy strong {
  color: var(--primary);
}
.risk-list__copy strong,
.risk-list__copy small,
.risk-list__copy em,
.risk-list__loss small,
.risk-list__loss strong {
  display: block;
}
.risk-list__copy {
  min-width: 0;
}
.risk-list__copy strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-body);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.risk-list__copy small {
  overflow: hidden;
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.risk-list__copy em {
  margin-top: 5px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  font-style: normal;
}
.risk-list__loss {
  position: relative;
  min-width: 76px;
  padding-right: 18px;
  text-align: right;
}
.risk-list__loss small {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.risk-list__loss strong {
  margin-top: 4px;
  color: var(--danger-dark);
  font-size: var(--font-size-body);
}
.risk-list__loss .el-icon {
  position: absolute;
  top: 50%;
  right: 0;
  color: var(--text-tertiary);
  transform: translateY(-50%);
}
.secondary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(330px, 0.8fr) minmax(330px, 0.9fr);
  gap: 14px;
}
.task-list,
.top-list {
  margin-top: 12px;
}
.task-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) 64px minmax(150px, 0.65fr);
  align-items: center;
  gap: 14px;
  padding: 13px 0;
  border-bottom: 1px solid var(--border-soft);
}
.task-row:last-child {
  border-bottom: 0;
}
.task-row strong,
.task-row small {
  display: block;
}
.task-row strong {
  font-size: var(--font-size-label);
}
.task-row small {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.task-row > span {
  color: var(--warning-dark);
  font-size: var(--font-size-meta);
  font-weight: 700;
}
.task-row__progress {
  display: grid;
  grid-template-columns: 1fr 32px;
  align-items: center;
  gap: 7px;
}
.task-row__progress small {
  margin: 0;
  text-align: right;
}
.top-list button {
  display: grid;
  width: 100%;
  grid-template-columns: 24px minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  padding: 10px 0;
  color: inherit;
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--border-soft);
  text-align: left;
  cursor: pointer;
}
.top-list button:last-child {
  border-bottom: 0;
}
.top-list button > b {
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 5px;
  font-size: var(--font-size-meta);
}
.top-list button span {
  min-width: 0;
}
.top-list button span strong,
.top-list button span small,
.top-list button em,
.top-list button em small {
  display: block;
}
.top-list button span strong {
  overflow: hidden;
  font-size: var(--font-size-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top-list button span small {
  margin-top: 3px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.top-list button em {
  color: var(--text-primary);
  font-size: var(--font-size-label);
  font-style: normal;
  font-weight: 700;
  text-align: right;
}
.top-list button em small {
  margin-top: 3px;
  color: var(--success-dark);
  font-size: var(--font-size-caption);
}
.ai-panel {
  color: #eef5ff;
  background: var(--nav-bg);
  border-color: var(--nav-bg);
}
.ai-panel__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: #a9c5ef;
  font-size: var(--font-size-meta);
}
.ai-panel__heading span {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #fff;
  font-weight: 700;
}
.ai-panel h2 {
  margin: 22px 0 8px;
  color: #fff;
  font-size: 19px;
  line-height: 1.35;
}
.ai-panel > p {
  margin: 0;
  color: #bed0e8;
  font-size: var(--font-size-label);
  line-height: 1.65;
}
.ai-panel ul {
  display: grid;
  gap: 7px;
  margin: 16px 0;
  padding: 12px 0;
  border-block: 1px solid rgb(255 255 255 / 12%);
  list-style: none;
}
.ai-panel li {
  color: #e4efff;
  font-size: var(--font-size-meta);
}
.ai-panel li::before {
  margin-right: 7px;
  color: #5de0ae;
  content: '•';
}
.ai-panel__actions {
  display: grid;
  gap: 7px;
}
.ai-panel__actions button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 10px;
  color: #eef5ff;
  background: rgb(255 255 255 / 7%);
  border: 1px solid rgb(255 255 255 / 10%);
  border-radius: 6px;
  font-size: var(--font-size-meta);
  cursor: pointer;
}
.ai-panel__actions button:hover {
  background: rgb(255 255 255 / 12%);
}
@media (max-width: 1250px) {
  .secondary-grid {
    grid-template-columns: 1fr 1fr;
  }
  .ai-panel {
    grid-column: 1 / -1;
  }
  .ai-panel__actions {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (max-width: 1050px) {
  .metric-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .primary-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 760px) {
  .page-heading {
    flex-direction: column;
  }
  .page-heading__meta {
    width: 100%;
    justify-content: space-between;
  }
  .metric-grid,
  .secondary-grid {
    grid-template-columns: 1fr;
  }
  .ai-panel {
    grid-column: auto;
  }
  .ai-panel__actions {
    grid-template-columns: 1fr;
  }
  .task-row {
    grid-template-columns: 1fr auto;
  }
  .task-row__progress {
    grid-column: 1 / -1;
  }
  .trend-chart {
    height: 280px;
  }
}
</style>
