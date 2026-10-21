<script setup lang="ts">
import { Document, Download, Refresh, TrendCharts } from '@element-plus/icons-vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'

import { diagnosticsApi } from '../api'
import { useSessionStore } from '../stores/session'
import type { DiagnosticReport } from '../types/api'

const session = useSessionStore()
const queryClient = useQueryClient()

const SHOP_OPTIONS = [
  { value: 'shop-all', label: '全部店铺' },
  { value: 'shop-taobao-001', label: '柔肤旗舰店（淘宝）' },
  { value: 'shop-douyin-001', label: '柔肤抖音专营店（抖店）' },
  { value: 'shop-pdd-001', label: '柔肤品牌馆（拼多多）' },
]

const selectedShopId = ref('shop-all')

const overviewQuery = useQuery({
  queryKey: ['diagnostics-overview', selectedShopId],
  queryFn: () => diagnosticsApi.overview(session.token!, selectedShopId.value),
  enabled: computed(() => Boolean(session.token)),
})
const overview = computed(() => overviewQuery.data.value)

const reportsQuery = useQuery({
  queryKey: ['diagnostics-reports'],
  queryFn: () => diagnosticsApi.reports(session.token!),
  enabled: computed(() => Boolean(session.token)),
})
const reports = computed(() => reportsQuery.data.value ?? [])

const currentReport = ref<DiagnosticReport | null>(null)

const reportMutation = useMutation({
  mutationFn: () => diagnosticsApi.createReport(session.token!, selectedShopId.value),
  onSuccess: (report) => {
    currentReport.value = report
    ElMessage.success(report.source === 'ai' ? '模型报告已生成' : '已生成规则模板报告')
    void queryClient.invalidateQueries({ queryKey: ['diagnostics-reports'] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '报告生成失败，请重试。')
  },
})

const exportMutation = useMutation({
  mutationFn: (input: { reportId: string; format: 'pdf' | 'xlsx' }) =>
    diagnosticsApi.createExport(session.token!, input.reportId, input.format),
  onSuccess: async (job, variables) => {
    try {
      const blob = await diagnosticsApi.downloadExport(session.token!, job.id)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = job.file_name
      anchor.click()
      URL.revokeObjectURL(url)
      ElMessage.success(`已下载 ${job.file_name}`)
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '文件下载失败，请重试。')
    }
    void variables
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '导出失败，请重试。')
  },
})

function healthScoreClass(score: number) {
  if (score >= 80) return 'health--good'
  if (score >= 60) return 'health--warning'
  return 'health--danger'
}

function componentScoreClass(score: number) {
  if (score >= 80) return 'good'
  if (score >= 60) return 'warning'
  return 'danger'
}

function severityType(severity: string) {
  return severity === 'critical' ? 'danger' : severity === 'warning' ? 'warning' : 'info'
}

function severityLabel(severity: string) {
  return severity === 'critical' ? '严重' : severity === 'warning' ? '关注' : '提示'
}

function confidenceLabel(confidence: string) {
  return confidence === 'high' ? '高' : confidence === 'medium' ? '中' : '低'
}

function riskLabel(riskLevel: string) {
  return riskLevel === 'high' ? '写操作建议 · 需人工确认' : '只读建议'
}

function money(value: number) {
  return `¥${value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

async function openReport(reportId: string) {
  try {
    currentReport.value = await diagnosticsApi.report(session.token!, reportId)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '报告加载失败，请重试。')
  }
}
</script>

<template>
  <div class="diagnostics-view">
    <header class="page-heading">
      <div>
        <div class="page-heading__eyebrow">
          <span>健康分与问题优先级</span><b v-if="overview?.is_demo">演示数据</b>
        </div>
        <h1>数据诊断</h1>
        <p>可解释健康分、按预计损失与紧迫度排序的问题清单，以及可导出的诊断报告。</p>
      </div>
      <div class="page-heading__meta">
        <el-select v-model="selectedShopId" class="scope-select" size="default" aria-label="选择诊断范围">
          <el-option
            v-for="shop in SHOP_OPTIONS"
            :key="shop.value"
            :label="shop.label"
            :value="shop.value"
          />
        </el-select>
        <el-button
          :icon="Refresh"
          :loading="overviewQuery.isFetching.value"
          @click="overviewQuery.refetch"
        >
          刷新
        </el-button>
      </div>
    </header>

    <el-alert
      class="scope-alert"
      title="口径说明：预计损失为排序用估算值（口径随问题标注），不是财务实际损失；健康分为五分项加权（算法版本 health-score-v1）；诊断结论全部只读，不构成平台写操作指令。"
      type="info"
      :closable="false"
      show-icon
    />

    <div v-if="overviewQuery.isError.value" class="load-error-actions">
      <el-alert type="error" :closable="false" show-icon title="诊断数据加载失败，请重试。" />
      <el-button type="primary" plain @click="overviewQuery.refetch">重试加载</el-button>
    </div>

    <template v-if="overview">
      <section class="health-panel panel-surface">
        <div class="health-hero">
          <div class="health-score" :class="healthScoreClass(overview.health.score)">
            <strong>{{ overview.health.score }}</strong>
            <span>综合健康分</span>
          </div>
          <div class="health-meta">
            <span>算法版本 {{ overview.health.algorithm_version }}</span>
            <span>数据源 {{ overview.is_demo ? '演示种子数据' : '实时授权店铺' }}</span>
            <span>生成时间 {{ dayjs(overview.generated_at).format('MM-DD HH:mm') }}</span>
          </div>
        </div>
        <div class="health-components">
          <article v-for="item in overview.health.components" :key="item.key" class="component-row">
            <div class="component-head">
              <strong>{{ item.label }}</strong>
              <span class="component-weight">权重 {{ (item.weight * 100).toFixed(0) }}%</span>
              <span class="component-score" :class="componentScoreClass(item.score)">
                {{ item.score }}
              </span>
            </div>
            <el-progress
              :percentage="item.score"
              :stroke-width="8"
              :show-text="false"
              :color="
                item.score >= 80 ? 'var(--success)' : item.score >= 60 ? 'var(--warning)' : 'var(--danger)'
              "
            />
            <p>{{ item.detail }}</p>
          </article>
        </div>
      </section>

      <section class="issues-panel panel-surface">
        <div class="section-heading">
          <div>
            <span>按 预计损失 x 紧迫度 x 置信度 排序</span>
            <h2>问题清单（{{ overview.issues.length }}）</h2>
          </div>
          <el-tooltip content="点击任意一行展开指标证据链" placement="top">
            <small><el-icon><TrendCharts /></el-icon> 证据可追溯</small>
          </el-tooltip>
        </div>
        <el-table
          v-if="overview.issues.length"
          :data="overview.issues"
          row-key="title"
          class="issue-table"
        >
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="evidence-block">
                <table class="evidence-table">
                  <thead>
                    <tr>
                      <th>指标</th>
                      <th>实测值</th>
                      <th>阈值 / 参考</th>
                      <th>来源</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(evidence, index) in row.evidence" :key="index">
                      <td>{{ evidence.metric }}</td>
                      <td><strong>{{ evidence.value }}</strong></td>
                      <td>{{ evidence.threshold }}</td>
                      <td>{{ evidence.source }}</td>
                    </tr>
                  </tbody>
                </table>
                <p class="loss-note">预计损失口径：{{ row.loss_note }}</p>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="96" align="right">
            <template #default="{ row }">
              <strong class="priority-cell">{{ row.priority.toFixed(1) }}</strong>
            </template>
          </el-table-column>
          <el-table-column label="问题" min-width="240">
            <template #default="{ row }">
              <div class="issue-title">
                <strong>{{ row.title }}</strong>
                <div class="issue-tags">
                  <el-tag size="small" :type="severityType(row.severity)" effect="plain">
                    {{ severityLabel(row.severity) }}
                  </el-tag>
                  <el-tag size="small" effect="plain">置信度 {{ confidenceLabel(row.confidence) }}</el-tag>
                  <el-tag
                    size="small"
                    :type="row.risk_level === 'high' ? 'danger' : 'success'"
                    effect="light"
                  >
                    {{ riskLabel(row.risk_level) }}
                  </el-tag>
                </div>
                <p class="issue-detail">{{ row.detail }}</p>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="范围" width="150">
            <template #default="{ row }">
              <span class="scope-cell">{{ row.shop_name }}</span>
              <span v-if="row.product_title" class="scope-cell scope-cell--product">{{
                row.product_title
              }}</span>
            </template>
          </el-table-column>
          <el-table-column label="预计损失" width="130" align="right">
            <template #default="{ row }">
              <span class="loss-cell">{{ money(row.estimated_loss) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="紧迫度" width="90" align="center">
            <template #default="{ row }">
              <span>{{ row.urgency }}</span>
            </template>
          </el-table-column>
          <el-table-column label="建议" min-width="220">
            <template #default="{ row }">
              <span class="recommendation-cell">{{ row.recommendation }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="当前范围内未发现达到判定阈值的问题" :image-size="70" />
      </section>

      <section class="comparison-panel panel-surface">
        <div class="section-heading">
          <div>
            <span>横向对标</span>
            <h2>店铺对比</h2>
          </div>
          <small>健康分相同时对比问题分布与销售额</small>
        </div>
        <el-table :data="overview.comparison" class="comparison-table">
          <el-table-column label="店铺" min-width="160">
            <template #default="{ row }">
              <strong>{{ row.shop_name }}</strong>
              <span class="platform-cell">{{ row.platform_label }}</span>
            </template>
          </el-table-column>
          <el-table-column label="健康分" width="110" align="right">
            <template #default="{ row }">
              <span class="health-cell" :class="componentScoreClass(row.health_score)">{{
                row.health_score
              }}</span>
            </template>
          </el-table-column>
          <el-table-column label="SKU 数" width="90" align="right" prop="product_count" />
          <el-table-column label="严重问题" width="100" align="right" prop="critical_issues" />
          <el-table-column label="关注问题" width="100" align="right" prop="warning_issues" />
          <el-table-column label="近 7 日销售额" width="150" align="right">
            <template #default="{ row }">
              <span>{{ money(row.revenue_7d) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="数据源" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="row.data_source === 'live' ? 'success' : 'info'" effect="plain">
                {{ row.data_source === 'live' ? '实时' : '演示' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="report-panel panel-surface">
        <div class="section-heading">
          <div>
            <span>可导出</span>
            <h2>诊断报告</h2>
          </div>
          <div class="report-actions">
            <el-button
              type="primary"
              :icon="Document"
              :loading="reportMutation.isPending.value"
              @click="reportMutation.mutate()"
            >
              生成报告
            </el-button>
            <el-button
              :icon="Download"
              :disabled="!currentReport"
              :loading="exportMutation.isPending.value"
              @click="
                currentReport &&
                exportMutation.mutate({ reportId: currentReport.id, format: 'pdf' })
              "
            >
              导出 PDF
            </el-button>
            <el-button
              :icon="Download"
              :disabled="!currentReport"
              :loading="exportMutation.isPending.value"
              @click="
                currentReport &&
                exportMutation.mutate({ reportId: currentReport.id, format: 'xlsx' })
              "
            >
              导出 Excel
            </el-button>
          </div>
        </div>
        <p class="report-hint">
          配置了可用 AI 模型且开关打开时报告由真实模型生成，否则使用规则模板；模型失败会自动降级并在报告首部说明。
        </p>
        <div v-if="currentReport" class="report-preview">
          <div class="report-preview__head">
            <strong>{{ currentReport.title }}</strong>
            <div class="report-preview__tags">
              <el-tag size="small" :type="currentReport.source === 'ai' ? 'success' : 'info'" effect="plain">
                {{ currentReport.source === 'ai' ? '模型生成' : '规则模板' }}
              </el-tag>
              <el-tag v-if="currentReport.model_id" size="small" effect="plain">
                {{ currentReport.model_id }}
              </el-tag>
              <span>{{ dayjs(currentReport.created_at).format('YYYY-MM-DD HH:mm') }}</span>
            </div>
          </div>
          <pre class="report-content">{{ currentReport.content }}</pre>
        </div>
        <div v-if="reports.length" class="report-history">
          <span class="report-history__label">历史报告</span>
          <button
            v-for="item in reports"
            :key="item.id"
            type="button"
            class="history-row"
            :class="{ 'history-row--active': currentReport?.id === item.id }"
            @click="openReport(item.id)"
          >
            <strong>{{ item.title }}</strong>
            <span>
              {{ dayjs(item.created_at).format('MM-DD HH:mm') }} ·
              {{ item.source === 'ai' ? '模型生成' : '规则模板' }}
            </span>
          </button>
        </div>
      </section>

      <section class="definitions-panel panel-surface">
        <div class="section-heading">
          <div>
            <span>服务端下发</span>
            <h2>指标口径</h2>
          </div>
        </div>
        <ul class="definition-list">
          <li v-for="item in overview.metric_definitions" :key="item.key">
            <strong>{{ item.label }}（{{ item.unit }}）</strong>
            <span>{{ item.definition }}</span>
          </li>
        </ul>
      </section>
    </template>

    <el-skeleton v-else-if="overviewQuery.isPending.value" :rows="8" animated />
  </div>
</template>

<style scoped lang="scss">
.diagnostics-view {
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
  font-size: 32px;
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
}
.scope-select {
  width: 200px;
}
.scope-alert {
  margin-bottom: 14px;
}
.load-error-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.load-error-actions .el-alert {
  flex: 1;
}
.panel-surface {
  padding: 18px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  margin-bottom: 14px;
}
.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.section-heading span {
  display: block;
  color: var(--primary);
  font-size: var(--font-size-meta);
  font-weight: 700;
}
.section-heading h2 {
  margin: 4px 0 0;
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
}
.section-heading small {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-top: 3px;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.health-panel {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 22px;
}
.health-hero {
  display: grid;
  gap: 12px;
  align-content: start;
  padding-right: 20px;
  border-right: 1px solid var(--border-soft);
}
.health-score {
  display: grid;
  place-items: center;
  gap: 4px;
  padding: 20px;
  border-radius: var(--radius-md);
}
.health-score strong {
  font-size: 44px;
  line-height: 1;
}
.health-score span {
  font-size: var(--font-size-label);
}
.health-score.health--good {
  color: var(--success-dark, #0d7a55);
  background: var(--success-soft);
}
.health-score.health--warning {
  color: var(--warning-dark);
  background: var(--warning-soft);
}
.health-score.health--danger {
  color: var(--danger);
  background: var(--danger-soft);
}
.health-meta {
  display: grid;
  gap: 5px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.health-components {
  display: grid;
  gap: 12px;
}
.component-row {
  display: grid;
  gap: 6px;
}
.component-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.component-head strong {
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.component-weight {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.component-score {
  margin-left: auto;
  font-size: var(--font-size-subtitle);
  font-weight: 700;
}
.component-score.good {
  color: var(--success);
}
.component-score.warning {
  color: var(--warning-dark);
}
.component-score.danger {
  color: var(--danger);
}
.component-row p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
}
.priority-cell {
  color: var(--text-primary);
  font-size: var(--font-size-subtitle);
}
.issue-title strong {
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.issue-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 6px 0;
}
.issue-detail {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: 1.6;
}
.scope-cell {
  display: block;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
}
.scope-cell--product {
  color: var(--text-tertiary);
}
.loss-cell {
  color: var(--danger);
  font-weight: 700;
}
.recommendation-cell {
  color: var(--primary);
  font-size: var(--font-size-caption);
  line-height: 1.6;
}
.evidence-block {
  padding: 10px 14px 12px;
  background: var(--surface-subtle);
}
.evidence-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-caption);
}
.evidence-table th,
.evidence-table td {
  padding: 5px 8px;
  text-align: left;
  border-bottom: 1px solid var(--border-soft);
}
.evidence-table th {
  color: var(--text-tertiary);
  font-weight: 600;
}
.loss-note {
  margin: 8px 0 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.platform-cell {
  display: block;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.health-cell {
  font-weight: 700;
}
.health-cell.good {
  color: var(--success);
}
.health-cell.warning {
  color: var(--warning-dark);
}
.health-cell.danger {
  color: var(--danger);
}
.report-actions {
  display: flex;
  gap: 10px;
}
.report-hint {
  margin: 0 0 12px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.report-preview {
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.report-preview__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: #f6f9fd;
  border-bottom: 1px solid var(--border-soft);
}
.report-preview__head strong {
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.report-preview__tags {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.report-content {
  max-height: 420px;
  margin: 0;
  padding: 14px;
  overflow: auto;
  color: var(--text-secondary);
  font-family: var(--font-mono, monospace);
  font-size: var(--font-size-caption);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
}
.report-history {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.report-history__label {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.history-row {
  display: grid;
  gap: 3px;
  padding: 7px 11px;
  text-align: left;
  background: var(--surface-subtle);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.history-row:hover {
  border-color: #c9dbf5;
}
.history-row--active {
  border-color: var(--primary);
  background: var(--primary-soft);
}
.history-row strong {
  color: var(--text-primary);
  font-size: var(--font-size-caption);
}
.history-row span {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.definition-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.definition-list li {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
}
.definition-list strong {
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.definition-list span {
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: 1.6;
}
@media (max-width: 1080px) {
  .health-panel {
    grid-template-columns: minmax(0, 1fr);
  }
  .health-hero {
    padding-right: 0;
    border-right: 0;
  }
}
@media (max-width: 640px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .report-actions {
    flex-wrap: wrap;
  }
}
</style>
