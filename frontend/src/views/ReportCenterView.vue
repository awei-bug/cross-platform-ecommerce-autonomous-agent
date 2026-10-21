<script setup lang="ts">
import { Clock, Download, EditPen, Files, Refresh, TrendCharts } from '@element-plus/icons-vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { BarChart, LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import type { EChartsType } from 'echarts/core'

import { reportApi } from '../api'
import { useSessionStore } from '../stores/session'
import { useWorkspaceStore } from '../stores/workspace'
import type { ReportFormat, ReportTemplateType } from '../types/api'

echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const session = useSessionStore()
const workspace = useWorkspaceStore()
const queryClient = useQueryClient()
const chartEl = ref<HTMLDivElement | null>(null)
let chart: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null

const selectedTemplate = ref<ReportTemplateType>('weekly')
const dateRange = ref<[string, string]>(['2026-09-07', '2026-09-13'])
const selectedMetrics = ref<string[]>(['revenue', 'orders', 'roi', 'refund_rate'])
const noteDialogOpen = ref(false)
const noteForm = reactive({ title: '', conclusion: '', next_actions: '' })
const previewMetric = ref('revenue')

const reportQuery = useQuery({
  queryKey: computed(() => [
    'reports',
    workspace.currentShopId,
    selectedTemplate.value,
    selectedMetrics.value.join(','),
  ]),
  queryFn: () =>
    reportApi.overview(session.token!, {
      shop_id: workspace.currentShopId,
      template_id: selectedTemplate.value,
      metrics: selectedMetrics.value,
    }),
  enabled: computed(() => Boolean(session.token)),
})
const overview = computed(() => reportQuery.data.value)
const templates = computed(() => overview.value?.templates ?? [])
const metrics = computed(() => overview.value?.metrics ?? [])
const notes = computed(() => overview.value?.notes ?? [])
const exports = computed(() => overview.value?.exports ?? [])

const exportMutation = useMutation({
  mutationFn: (format: ReportFormat) =>
    reportApi.createExport(session.token!, {
      template_id: selectedTemplate.value,
      format,
      shop_id: workspace.currentShopId,
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
      metrics: selectedMetrics.value,
    }),
  onSuccess: async (job) => {
    try {
      await downloadReportFile(job.id, job.file_name)
      ElMessage.success(`${job.format === 'excel' ? 'Excel' : 'PDF'} 报表已生成并下载`)
    } catch (error) {
      ElMessage.warning(
        error instanceof Error ? `报表已生成，但下载失败：${error.message}` : '报表已生成，但下载失败',
      )
    }
    void queryClient.invalidateQueries({ queryKey: ['reports'] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '导出任务创建失败，请稍后重试。')
  },
})

const downloadMutation = useMutation({
  mutationFn: (job: { id: string; file_name: string }) =>
    downloadReportFile(job.id, job.file_name),
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '文件下载失败，请稍后重试。')
  },
})

async function downloadReportFile(exportId: string, fileName: string) {
  const blob = await reportApi.downloadExport(session.token!, exportId)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  anchor.click()
  URL.revokeObjectURL(url)
}
const noteMutation = useMutation({
  mutationFn: () =>
    reportApi.createNote(session.token!, {
      template_id: selectedTemplate.value,
      title: noteForm.title,
      conclusion: noteForm.conclusion,
      next_actions: noteForm.next_actions,
    }),
  onSuccess: () => {
    ElMessage.success('复盘笔记已保存（演示数据）')
    noteDialogOpen.value = false
    noteForm.title = ''
    noteForm.conclusion = ''
    noteForm.next_actions = ''
    void queryClient.invalidateQueries({ queryKey: ['reports'] })
  },
})

function chooseTemplate(templateId: ReportTemplateType) {
  selectedTemplate.value = templateId
  const template = templates.value.find((item) => item.id === templateId)
  if (template) selectedMetrics.value = [...template.default_metrics]
}

function metricLabel(key: string) {
  return (
    {
      revenue: '成交金额',
      orders: '支付订单',
      spend: '广告消耗',
      roi: '广告 ROI',
      refund_rate: '退款率',
    }[key] ?? key
  )
}

function changeType(change: number) {
  return change >= 0 ? 'success' : 'danger'
}

function renderChart() {
  const trend = overview.value?.trend ?? []
  if (!chartEl.value || !trend.length) return
  chart ??= echarts.init(chartEl.value)
  chart.setOption({
    animationDuration: 420,
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
    grid: { top: 42, right: 26, bottom: 26, left: 58 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: trend.map((item) => item.date),
      axisLine: { lineStyle: { color: '#d8e1ed' } },
      axisLabel: { color: '#65758d', fontSize: 13 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#e7edf5' } },
      axisLabel: {
        color: '#65758d',
        fontSize: 13,
        formatter: (value: number) =>
          previewMetric.value === 'orders'
            ? `${Math.round(value)}`
            : `${Math.round(value / 1000)}k`,
      },
    },
    series: [
      {
        name:
          previewMetric.value === 'orders'
            ? '支付订单'
            : previewMetric.value === 'spend'
              ? '广告消耗'
              : previewMetric.value === 'refund_rate'
                ? '退款金额'
                : '成交金额',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        data: trend.map((item) =>
          previewMetric.value === 'orders'
            ? item.orders
            : previewMetric.value === 'spend'
              ? item.spend
              : previewMetric.value === 'refund_rate'
                ? item.refunds
                : item.revenue,
        ),
        areaStyle: { color: 'rgba(36, 116, 245, 0.08)' },
        lineStyle: { width: 3 },
      },
      {
        name: '广告消耗',
        type: 'bar',
        barMaxWidth: 10,
        data: trend.map((item) => item.spend),
        itemStyle: { color: 'rgba(24, 168, 115, 0.28)' },
      },
    ],
  })
}

function openNoteDialog() {
  noteForm.title = `${templates.value.find((item) => item.id === selectedTemplate.value)?.name ?? '报表'}复盘`
  noteDialogOpen.value = true
}

watch([overview, previewMetric], async () => {
  await nextTick()
  renderChart()
})
watch(selectedTemplate, () => {
  previewMetric.value = selectedMetrics.value.includes('revenue')
    ? 'revenue'
    : (selectedMetrics.value[0] ?? 'revenue')
})
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
  <div class="report-view">
    <header class="page-heading">
      <div>
        <div class="page-heading__eyebrow"><span>报表与复盘中心</span><b>演示数据</b></div>
        <h1>经营复盘工作台</h1>
        <p>把指标、趋势、明细和行动计划放在同一份报表里，让每次复盘都有结论可追踪。</p>
      </div>
      <div class="page-heading__meta">
        <el-icon><Clock /></el-icon
        ><span
          >更新于
          <strong>{{
            overview ? dayjs(overview.data_updated_at).format('MM-DD HH:mm') : '同步中'
          }}</strong></span
        ><el-button
          :icon="Refresh"
          :loading="reportQuery.isFetching.value"
          @click="reportQuery.refetch"
          >刷新</el-button
        >
      </div>
    </header>

    <el-alert
      class="demo-alert"
      title="当前为演示数据，导出任务会记录流程但不会生成真实 Excel/PDF 文件。"
      type="info"
      :closable="false"
      show-icon
    />
    <div v-if="reportQuery.isError.value" class="load-error-actions">
      <el-alert type="error" :closable="false" show-icon title="报表数据加载失败，请重试。" />
      <el-button type="primary" plain @click="reportQuery.refetch">重试加载</el-button>
    </div>

    <section class="report-config panel-surface">
      <div class="config-heading">
        <div><span>报表配置</span><strong>选择模板与统计口径</strong></div>
        <el-button type="primary" :icon="EditPen" @click="openNoteDialog">添加复盘笔记</el-button>
      </div>
      <div class="template-tabs">
        <button
          v-for="template in templates"
          :key="template.id"
          type="button"
          :class="{ 'is-active': selectedTemplate === template.id }"
          @click="chooseTemplate(template.id)"
        >
          <span>{{ template.category }}</span
          ><strong>{{ template.name }}</strong
          ><small>{{ template.description }}</small>
        </button>
      </div>
      <div class="config-fields">
        <div>
          <label>统计时间</label
          ><el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
          />
        </div>
        <div class="metric-picker">
          <label>展示指标</label
          ><el-checkbox-group v-model="selectedMetrics"
            ><el-checkbox
              v-for="metric in ['revenue', 'orders', 'spend', 'roi', 'refund_rate']"
              :key="metric"
              :value="metric"
              >{{ metricLabel(metric) }}</el-checkbox
            ></el-checkbox-group
          >
        </div>
        <div class="config-scope">
          <label>店铺范围</label><strong>{{ workspace.scopeLabel }}</strong
          ><small>{{ workspace.scopePlatformLabel }} · 跟随顶部工作区切换</small>
        </div>
      </div>
    </section>

    <section v-if="overview" class="metric-grid">
      <article v-for="metric in metrics" :key="metric.key" class="metric-card">
        <span>{{ metric.label }}</span
        ><strong>{{ metric.display_value }}</strong
        ><el-tag size="small" :type="changeType(metric.change)"
          >{{ metric.change >= 0 ? '↑' : '↓' }} {{ Math.abs(metric.change).toFixed(1) }}%
          同比</el-tag
        >
      </article>
    </section>

    <main v-if="overview" class="report-grid">
      <section class="preview-panel panel-surface">
        <div class="section-heading">
          <div>
            <span>在线预览</span>
            <h2>{{ templates.find((item) => item.id === selectedTemplate)?.name }} · 趋势概览</h2>
          </div>
          <div class="preview-actions">
            <el-radio-group v-model="previewMetric" size="small"
              ><el-radio-button v-for="metric in selectedMetrics" :key="metric" :value="metric">{{
                metricLabel(metric)
              }}</el-radio-button></el-radio-group
            ><el-button
              :icon="Download"
              :loading="exportMutation.isPending.value"
              @click="exportMutation.mutate('excel')"
              >导出 Excel</el-button
            ><el-button
              plain
              :loading="exportMutation.isPending.value"
              @click="exportMutation.mutate('pdf')"
              >导出 PDF</el-button
            >
          </div>
        </div>
        <div ref="chartEl" class="report-chart"></div>
      </section>
      <section class="drill-panel panel-surface">
        <div class="section-heading">
          <div>
            <span>指标下钻</span>
            <h2>主体明细</h2>
          </div>
          <small>{{ overview.rows.length }} 条</small>
        </div>
        <el-table :data="overview.rows" size="small"
          ><el-table-column
            prop="name"
            label="商品 / 主体"
            min-width="160"
            show-overflow-tooltip
          /><el-table-column prop="platform_label" label="平台" width="70" /><el-table-column
            label="成交金额"
            width="100"
            align="right"
            ><template #default="scope"
              >¥{{ Math.round(scope.row.revenue).toLocaleString('zh-CN') }}</template
            ></el-table-column
          ><el-table-column label="订单" width="70" align="right" prop="orders" /><el-table-column
            label="ROI"
            width="70"
            align="right"
            ><template #default="scope">{{ scope.row.roi.toFixed(2) }}</template></el-table-column
          ><el-table-column label="退款率" width="80" align="right"
            ><template #default="scope"
              >{{ scope.row.refund_rate.toFixed(1) }}%</template
            ></el-table-column
          ></el-table
        >
      </section>
    </main>

    <section class="lower-grid">
      <section class="panel-surface export-panel">
        <div class="section-heading">
          <div>
            <span>异步任务</span>
            <h2>导出记录</h2>
          </div>
          <small>后台生成状态</small>
        </div>
        <div class="export-list">
          <article v-for="job in exports" :key="job.id">
            <div class="file-icon">
              <el-icon><Files /></el-icon>
            </div>
            <div class="export-copy">
              <strong>{{ job.file_name }}</strong
              ><small
                >{{ job.format === 'excel' ? 'Excel' : 'PDF' }} ·
                {{ dayjs(job.created_at).format('MM-DD HH:mm') }}
                <template v-if="job.file_size"> · {{ (job.file_size / 1024).toFixed(0) }} KB</template></small
              >
            </div>
            <el-tag size="small" :type="job.status === 'succeeded' ? 'success' : 'danger'">{{
              job.status === 'succeeded' ? '已完成' : '失败'
            }}</el-tag>
            <el-button
              v-if="job.status === 'succeeded'"
              text
              type="primary"
              :icon="Download"
              :loading="downloadMutation.isPending.value"
              @click="downloadMutation.mutate(job)"
              >下载</el-button
            >
          </article>
          <el-empty v-if="!exports.length" description="还没有导出记录" :image-size="60" />
        </div>
      </section>
      <section class="panel-surface notes-panel">
        <div class="section-heading">
          <div>
            <span>团队沉淀</span>
            <h2>复盘笔记</h2>
          </div>
          <el-button text type="primary" @click="openNoteDialog">新增笔记</el-button>
        </div>
        <div v-if="notes.length" class="note-list">
          <article v-for="note in notes" :key="note.id">
            <div class="note-head">
              <strong>{{ note.title }}</strong
              ><small>{{ note.author }} · {{ dayjs(note.created_at).format('MM-DD HH:mm') }}</small>
            </div>
            <p>{{ note.conclusion }}</p>
            <div class="note-action">
              <el-icon><TrendCharts /></el-icon><span>后续行动：{{ note.next_actions }}</span>
            </div>
          </article>
        </div>
        <div v-else class="empty-copy">当前报表还没有复盘笔记，先记录第一条结论。</div>
      </section>
    </section>

    <el-dialog v-model="noteDialogOpen" title="添加复盘笔记" width="520px"
      ><el-form label-position="top"
        ><el-form-item label="笔记标题"
          ><el-input v-model="noteForm.title" placeholder="例如：本周投放效率提升" /></el-form-item
        ><el-form-item label="复盘结论"
          ><el-input
            v-model="noteForm.conclusion"
            type="textarea"
            :rows="4"
            placeholder="记录这期报表最重要的判断" /></el-form-item
        ><el-form-item label="后续行动计划"
          ><el-input
            v-model="noteForm.next_actions"
            type="textarea"
            :rows="3"
            placeholder="记录下一步要做什么、由谁负责" /></el-form-item></el-form
      ><template #footer
        ><el-button @click="noteDialogOpen = false">取消</el-button
        ><el-button
          type="primary"
          :loading="noteMutation.isPending.value"
          :disabled="!noteForm.title || !noteForm.conclusion"
          @click="noteMutation.mutate"
          >保存笔记</el-button
        ></template
      ></el-dialog
    >
  </div>
</template>

<style scoped lang="scss">
.load-error-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.load-error-actions .el-alert {
  flex: 1;
}
.report-view {
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
  color: var(--warning-dark);
  background: var(--warning-soft);
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
.demo-alert {
  margin-bottom: 14px;
}
.panel-surface {
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}
.report-config {
  padding: 18px;
  margin-bottom: 14px;
}
.config-heading,
.section-heading,
.preview-actions,
.note-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.config-heading {
  align-items: center;
  margin-bottom: 15px;
}
.config-heading span,
.section-heading span {
  display: block;
  color: var(--primary);
  font-size: var(--font-size-meta);
  font-weight: 700;
}
.config-heading strong {
  display: block;
  margin-top: 4px;
  color: var(--text-primary);
  font-size: var(--font-size-subtitle);
}
.section-heading {
  margin-bottom: 14px;
}
.section-heading h2 {
  margin: 4px 0 0;
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
  letter-spacing: -0.02em;
}
.section-heading small {
  padding-top: 3px;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.template-tabs {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
}
.template-tabs button {
  min-height: 92px;
  padding: 11px;
  text-align: left;
  background: var(--surface-subtle);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: 0.16s ease;
}
.template-tabs button:hover,
.template-tabs button.is-active {
  background: var(--primary-softer);
  border-color: #a9c7f7;
  box-shadow: inset 0 -3px 0 var(--primary);
}
.template-tabs span,
.template-tabs strong,
.template-tabs small {
  display: block;
}
.template-tabs span {
  color: var(--primary);
  font-size: var(--font-size-caption);
}
.template-tabs strong {
  margin-top: 8px;
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.template-tabs small {
  margin-top: 5px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  line-height: 1.4;
}
.config-fields {
  display: grid;
  grid-template-columns: 250px 1fr 220px;
  gap: 20px;
  align-items: end;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--border-soft);
}
.config-fields label {
  display: block;
  margin-bottom: 7px;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  font-weight: 700;
}
.metric-picker :deep(.el-checkbox-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 3px 13px;
}
.metric-picker :deep(.el-checkbox) {
  margin-right: 0;
}
.config-scope {
  min-height: 66px;
  padding: 10px 12px;
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
}
.config-scope strong,
.config-scope small {
  display: block;
}
.config-scope strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.config-scope small {
  margin-top: 5px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}
.metric-card {
  display: grid;
  gap: 7px;
  min-height: 108px;
  padding: 15px 17px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}
.metric-card span {
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
}
.metric-card strong {
  color: var(--text-primary);
  font-size: 24px;
  letter-spacing: -0.03em;
}
.report-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(420px, 0.9fr);
  gap: 14px;
}
.preview-panel,
.drill-panel,
.export-panel,
.notes-panel {
  padding: 18px;
}
.preview-actions {
  align-items: center;
}
.report-chart {
  width: 100%;
  height: 310px;
}
.drill-panel :deep(.el-table__header th) {
  color: var(--text-tertiary);
  background: #fbfcfe;
  font-size: var(--font-size-meta);
}
.drill-panel :deep(.el-table__row td) {
  padding-top: 12px;
  padding-bottom: 12px;
}
.lower-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-top: 14px;
}
.export-list,
.note-list {
  display: grid;
  gap: 8px;
}
.export-list article {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px;
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
}
.file-icon {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 6px;
}
.export-copy {
  min-width: 0;
  flex: 1;
}
.export-copy strong,
.export-copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.export-copy strong {
  color: var(--text-primary);
  font-size: var(--font-size-meta);
}
.export-copy small {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.note-list article {
  padding: 12px;
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
}
.note-head {
  align-items: center;
}
.note-head strong {
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.note-head small {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.note-list p {
  margin: 8px 0;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  line-height: 1.6;
}
.note-action {
  display: flex;
  gap: 6px;
  color: var(--primary);
  font-size: var(--font-size-caption);
  line-height: 1.5;
}
.empty-copy {
  padding: 24px;
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
  text-align: center;
}
@media (max-width: 1240px) {
  .template-tabs {
    grid-template-columns: repeat(3, 1fr);
  }
  .config-fields {
    grid-template-columns: 1fr 1.5fr;
  }
  .config-scope {
    grid-column: 1 / -1;
  }
  .metric-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .report-grid {
    grid-template-columns: 1fr;
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
  .template-tabs {
    grid-template-columns: repeat(2, 1fr);
  }
  .config-fields {
    grid-template-columns: 1fr;
  }
  .config-scope {
    grid-column: auto;
  }
  .metric-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .preview-actions {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .report-chart {
    height: 260px;
  }
  .lower-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 520px) {
  .template-tabs {
    grid-template-columns: 1fr;
  }
  .metric-grid {
    grid-template-columns: 1fr 1fr;
  }
  .metric-card {
    padding: 12px;
  }
  .preview-panel,
  .drill-panel,
  .export-panel,
  .notes-panel,
  .report-config {
    padding: 13px;
  }
  .preview-actions :deep(.el-radio-group) {
    width: 100%;
    overflow-x: auto;
  }
}
</style>
