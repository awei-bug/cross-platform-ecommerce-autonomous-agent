<script setup lang="ts">
import { Delete, Refresh, RefreshRight, WarningFilled } from '@element-plus/icons-vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, ref } from 'vue'

import { opsApi } from '../api'
import { useSessionStore } from '../stores/session'
import type { OpsTask } from '../types/api'

const session = useSessionStore()
const queryClient = useQueryClient()

const KIND_OPTIONS = [
  { value: '', label: '全部类型' },
  { value: 'operation_job', label: '操作任务' },
  { value: 'generation_job', label: '素材生成' },
  { value: 'agent_run', label: '智能体运行' },
]

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'succeeded', label: '已完成' },
  { value: 'running', label: '执行中' },
  { value: 'failed', label: '失败' },
  { value: 'dead_letter', label: '死信' },
  { value: 'dismissed', label: '已丢弃' },
]

const kindFilter = ref('')
const statusFilter = ref('')

const metricsQuery = useQuery({
  queryKey: ['ops-metrics'],
  queryFn: () => opsApi.metrics(session.token!),
  enabled: computed(() => Boolean(session.token)),
})
const metrics = computed(() => metricsQuery.data.value)

const tasksQuery = useQuery({
  queryKey: ['ops-tasks', kindFilter, statusFilter],
  queryFn: () =>
    opsApi.tasks(session.token!, {
      kind: kindFilter.value || undefined,
      status: statusFilter.value || undefined,
    }),
  enabled: computed(() => Boolean(session.token)),
})
const tasks = computed(() => tasksQuery.data.value ?? [])

const sweepMutation = useMutation({
  mutationFn: () => opsApi.sweep(session.token!),
  onSuccess: (result) => {
    ElMessage.success(
      `巡检完成：超时标记 ${result.timed_out.length} 个，进入死信 ${result.dead_lettered.length} 个`,
    )
    void queryClient.invalidateQueries({ queryKey: ['ops-metrics'] })
    void queryClient.invalidateQueries({ queryKey: ['ops-tasks'] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '巡检执行失败，请重试。')
  },
})

const retryMutation = useMutation({
  mutationFn: (task: OpsTask) => opsApi.retry(session.token!, task.kind, task.id),
  onSuccess: (task) => {
    ElMessage.success(`任务已重试：${task.status === 'succeeded' ? '重试成功' : task.status}`)
    void queryClient.invalidateQueries({ queryKey: ['ops-metrics'] })
    void queryClient.invalidateQueries({ queryKey: ['ops-tasks'] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '重试失败。')
  },
})

const discardMutation = useMutation({
  mutationFn: (task: OpsTask) => opsApi.discard(session.token!, task.kind, task.id),
  onSuccess: () => {
    ElMessage.success('任务已丢弃')
    void queryClient.invalidateQueries({ queryKey: ['ops-metrics'] })
    void queryClient.invalidateQueries({ queryKey: ['ops-tasks'] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '丢弃失败。')
  },
})

const KIND_LABELS: Record<string, string> = {
  operation_job: '操作任务',
  generation_job: '素材生成',
  agent_run: '智能体运行',
}

const STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  planning: '规划中',
  pending: '待处理',
  running: '执行中',
  succeeded: '已完成',
  partial: '部分成功',
  failed: '失败',
  dead_letter: '死信',
  dismissed: '已丢弃',
}

function statusTagType(status: string) {
  if (status === 'succeeded') return 'success'
  if (status === 'partial') return 'warning'
  if (status === 'failed') return 'danger'
  if (status === 'dead_letter') return 'danger'
  if (status === 'dismissed') return 'info'
  if (status === 'running' || status === 'planning') return 'primary'
  return 'info'
}

function canRetry(task: OpsTask) {
  return ['failed', 'dead_letter'].includes(task.status) && task.attempts < task.max_attempts
}

function canDiscard(task: OpsTask) {
  return ['failed', 'dead_letter'].includes(task.status)
}

function durationLabel(task: OpsTask) {
  const end = task.completed_at ?? task.updated_at
  const seconds = dayjs(end).diff(dayjs(task.created_at), 'second')
  if (seconds < 60) return `${seconds} 秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`
  return `${(seconds / 3600).toFixed(1)} 小时`
}

async function confirmDiscard(task: OpsTask) {
  try {
    await ElMessageBox.confirm(
      `丢弃后该任务不再重试，仅保留记录。确认丢弃「${task.title}」？`,
      '丢弃任务',
      { type: 'warning', confirmButtonText: '丢弃', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  discardMutation.mutate(task)
}
</script>

<template>
  <div class="ops-view">
    <header class="page-heading">
      <div>
        <div class="page-heading__eyebrow"><span>超时 / 重试 / 死信</span><b>运维视角</b></div>
        <h1>任务运维</h1>
        <p>统一查看操作任务、素材生成与智能体运行的状态、耗时与失败原因。</p>
      </div>
      <div class="page-heading__meta">
        <span v-if="metrics">统计至 {{ dayjs(metrics.generated_at).format('MM-DD HH:mm') }}</span>
        <el-button :icon="Refresh" :loading="metricsQuery.isFetching.value" @click="metricsQuery.refetch">
          刷新
        </el-button>
        <el-button
          type="primary"
          plain
          :icon="RefreshRight"
          :loading="sweepMutation.isPending.value"
          @click="sweepMutation.mutate()"
        >
          执行巡检
        </el-button>
      </div>
    </header>

    <el-alert
      class="ops-alert"
      title="巡检规则：执行中超过阈值（操作任务 15 分钟 / 生成与智能体 10 分钟）的任务标记为失败；失败且重试次数耗尽的进入死信，只能丢弃。生产模式下巡检由调度器周期调用。"
      type="info"
      :closable="false"
      show-icon
    />

    <section v-if="metrics" class="metrics-grid" aria-label="任务指标">
      <article class="metric-card">
        <span>任务总数</span><strong>{{ metrics.totals.total }}</strong>
      </article>
      <article class="metric-card metric-card--success">
        <span>已完成</span><strong>{{ metrics.totals.succeeded }}</strong>
      </article>
      <article class="metric-card">
        <span>执行中</span><strong>{{ metrics.totals.running }}</strong>
      </article>
      <article class="metric-card metric-card--danger">
        <span>失败</span><strong>{{ metrics.totals.failed }}</strong>
      </article>
      <article class="metric-card metric-card--danger">
        <span>死信</span><strong>{{ metrics.totals.dead_letter }}</strong>
      </article>
      <article class="metric-card">
        <span>失败率</span><strong>{{ (metrics.failure_rate * 100).toFixed(1) }}%</strong>
      </article>
      <article class="metric-card">
        <span>平均耗时</span><strong>{{ metrics.avg_duration_seconds.toFixed(1) }}s</strong>
      </article>
    </section>

    <section class="panel-surface">
      <div class="section-heading">
        <div>
          <span>统一视图</span>
          <h2>任务列表（{{ tasks.length }}）</h2>
        </div>
        <div class="filters">
          <el-select v-model="kindFilter" class="filter-select" size="small" aria-label="按类型筛选">
            <el-option v-for="item in KIND_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-model="statusFilter" class="filter-select" size="small" aria-label="按状态筛选">
            <el-option v-for="item in STATUS_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
      </div>
      <el-table v-if="tasks.length" :data="tasks" class="ops-table">
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ KIND_LABELS[row.kind] ?? row.kind }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="任务" min-width="220">
          <template #default="{ row }">
            <strong class="task-title">{{ row.title }}</strong>
            <span class="task-id">{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType(row.status)" effect="light">
              {{ STATUS_LABELS[row.status] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="尝试" width="80" align="center">
          <template #default="{ row }">{{ row.attempts }} / {{ row.max_attempts }}</template>
        </el-table-column>
        <el-table-column label="耗时" width="90" align="right">
          <template #default="{ row }">{{ durationLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="失败原因" min-width="200">
          <template #default="{ row }">
            <span v-if="row.error" class="error-cell">{{ row.error }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" align="right">
          <template #default="{ row }">
            <el-button
              v-if="canRetry(row)"
              text
              type="primary"
              size="small"
              :loading="retryMutation.isPending.value"
              @click="retryMutation.mutate(row)"
              >重试</el-button
            >
            <el-button
              v-if="canDiscard(row)"
              text
              type="danger"
              size="small"
              :icon="Delete"
              :loading="discardMutation.isPending.value"
              @click="confirmDiscard(row)"
              >丢弃</el-button
            >
            <span v-if="!canRetry(row) && !canDiscard(row)" class="muted">—</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="没有匹配的任务" :image-size="70" />
    </section>

    <section v-if="metrics?.recent_failures.length" class="panel-surface">
      <div class="section-heading">
        <div>
          <span>最近失败</span>
          <h2>失败与死信（{{ metrics.recent_failures.length }}）</h2>
        </div>
        <small>最新在前</small>
      </div>
      <div class="failure-list">
        <article v-for="item in metrics.recent_failures" :key="`${item.kind}-${item.id}`" class="failure-row">
          <div class="failure-icon"><el-icon><WarningFilled /></el-icon></div>
          <div class="failure-copy">
            <strong>{{ item.title }}</strong>
            <span>{{ item.error ?? '未记录原因' }}</span>
          </div>
          <div class="failure-meta">
            <el-tag size="small" effect="plain">{{ KIND_LABELS[item.kind] ?? item.kind }}</el-tag>
            <span>第 {{ item.attempts }} 次尝试</span>
            <span>{{ dayjs(item.updated_at).format('MM-DD HH:mm') }}</span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.ops-view {
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
  white-space: nowrap;
}
.ops-alert {
  margin-bottom: 14px;
}
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}
.metric-card {
  display: grid;
  gap: 6px;
  padding: 14px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}
.metric-card span {
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
}
.metric-card strong {
  color: var(--text-primary);
  font-size: 24px;
}
.metric-card--success strong {
  color: var(--success);
}
.metric-card--danger strong {
  color: var(--danger);
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
  padding-top: 3px;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.filters {
  display: flex;
  gap: 8px;
}
.filter-select {
  width: 130px;
}
.task-title {
  display: block;
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.task-id {
  display: block;
  margin-top: 2px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.error-cell {
  color: var(--danger);
  font-size: var(--font-size-caption);
  line-height: 1.5;
}
.muted {
  color: var(--text-tertiary);
}
.failure-list {
  display: grid;
  gap: 8px;
}
.failure-row {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 11px 13px;
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
}
.failure-icon {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  color: var(--danger);
  background: var(--danger-soft);
  border-radius: 50%;
}
.failure-copy {
  min-width: 0;
}
.failure-copy strong {
  display: block;
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.failure-copy span {
  display: block;
  margin-top: 3px;
  overflow: hidden;
  color: var(--danger);
  font-size: var(--font-size-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.failure-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  white-space: nowrap;
}
@media (max-width: 1080px) {
  .metrics-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .failure-meta {
    flex-wrap: wrap;
  }
}
</style>
