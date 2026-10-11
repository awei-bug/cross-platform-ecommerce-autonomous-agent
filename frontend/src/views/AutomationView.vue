<script setup lang="ts">
import { CircleCheck, Clock, Cpu, Refresh, VideoPlay, WarningFilled } from '@element-plus/icons-vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'

import { automationApi } from '../api'
import { useSessionStore } from '../stores/session'
import type {
  AutomationMode,
  AutomationRule,
  AutomationRuleType,
  AutomationTask,
  AutomationTaskStatus,
} from '../types/api'

const session = useSessionStore()
const queryClient = useQueryClient()

const automationQuery = useQuery({
  queryKey: ['automation'],
  queryFn: () => automationApi.overview(session.token!),
  enabled: computed(() => Boolean(session.token)),
})
const overview = computed(() => automationQuery.data.value)
const rules = computed(() => overview.value?.rules ?? [])
const runs = computed(() => overview.value?.runs ?? [])
const tasks = computed(() => overview.value?.tasks ?? [])
const selectedRunId = ref<string | null>(null)
const resultDrawerOpen = ref(false)
const selectedRun = computed(() => runs.value.find((run) => run.id === selectedRunId.value) ?? null)
const activeRules = computed(() => rules.value.filter((rule) => rule.is_enabled).length)
const matchedCount = computed(() => runs.value.reduce((total, run) => total + run.matched_count, 0))
const pendingTaskCount = computed(
  () =>
    tasks.value.filter((task) => task.status === 'pending' || task.status === 'in_progress').length,
)

const toggleMutation = useMutation({
  mutationFn: (input: { ruleId: string; isEnabled: boolean }) =>
    automationApi.updateRule(session.token!, input.ruleId, { is_enabled: input.isEnabled }),
  onSuccess: () => {
    ElMessage.success('规则状态已更新')
    void queryClient.invalidateQueries({ queryKey: ['automation'] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '规则状态更新失败，请重试。')
    void queryClient.invalidateQueries({ queryKey: ['automation'] })
  },
})

const runMutation = useMutation({
  mutationFn: (ruleId: string) => automationApi.runRule(session.token!, ruleId),
  onSuccess: (run) => {
    ElMessage.success(`扫描完成，发现 ${run.matched_count} 个待处理对象`)
    void queryClient.invalidateQueries({ queryKey: ['automation'] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '规则扫描失败，请重试。')
  },
})

const taskMutation = useMutation({
  mutationFn: (input: {
    taskId: string
    request: { status?: AutomationTaskStatus; assignee?: string | null }
  }) => automationApi.updateTask(session.token!, input.taskId, input.request),
  onSuccess: () => {
    ElMessage.success('自动化任务状态已更新')
    void queryClient.invalidateQueries({ queryKey: ['automation'] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '任务状态更新失败，请重试。')
    void queryClient.invalidateQueries({ queryKey: ['automation'] })
  },
})

function ruleTypeLabel(type: AutomationRuleType) {
  return {
    after_sale_sla: '售后时效',
    inventory_low: '库存安全线',
    product_quality: '商品质量',
  }[type]
}

function ruleTypeIcon(type: AutomationRuleType) {
  return type === 'after_sale_sla' ? WarningFilled : type === 'inventory_low' ? Clock : Cpu
}

function modeLabel(mode: AutomationMode) {
  return mode === 'approval_required' ? '人工确认' : mode === 'suggest' ? '建议模式' : '自动执行'
}

function modeTagType(mode: AutomationMode) {
  return mode === 'approval_required' ? 'warning' : mode === 'suggest' ? 'info' : 'success'
}

function ruleConfig(rule: AutomationRule) {
  if (rule.rule_type === 'after_sale_sla')
    return `剩余 ${rule.config.threshold_minutes ?? 120} 分钟内`
  if (rule.rule_type === 'inventory_low') return `库存 ≤ ${rule.config.stock_threshold ?? 25} 件`
  return rule.config.include_warning === false ? '仅扫描高风险' : '扫描下架、草稿和风险标签'
}

function lastRunLabel(rule: AutomationRule) {
  return rule.last_run_at ? dayjs(rule.last_run_at).format('MM-DD HH:mm') : '尚未运行'
}

function runLabel(status: string) {
  return status === 'succeeded' ? '扫描完成' : '执行失败'
}

function toggleRule(ruleId: string, value: boolean | string | number) {
  toggleMutation.mutate({ ruleId, isEnabled: Boolean(value) })
}

function openRun(runId: string) {
  selectedRunId.value = runId
  resultDrawerOpen.value = true
}

function taskStatusLabel(status: AutomationTaskStatus) {
  return {
    pending: '待处理',
    in_progress: '处理中',
    completed: '已完成',
    dismissed: '已忽略',
  }[status]
}

function taskStatusType(status: AutomationTaskStatus) {
  return status === 'completed' ? 'success' : status === 'dismissed' ? 'info' : 'warning'
}

function taskSeverityLabel(severity: string) {
  return severity === 'critical' ? '高风险' : severity === 'warning' ? '需关注' : '提示'
}

function updateTaskStatus(task: AutomationTask, value: string | number | boolean) {
  const status = String(value) as AutomationTaskStatus
  if (status === task.status) return
  taskMutation.mutate({ taskId: task.id, request: { status } })
}

function updateTaskAssignee(task: AutomationTask, value: string | number | boolean) {
  const assignee = String(value).trim() || null
  if (assignee === task.assignee) return
  taskMutation.mutate({ taskId: task.id, request: { assignee } })
}

function taskDueLabel(task: AutomationTask) {
  return task.due_at ? `截止 ${dayjs(task.due_at).format('MM-DD HH:mm')}` : '暂无明确截止时间'
}
</script>

<template>
  <div class="automation-view">
    <header class="page-heading">
      <div>
        <div class="page-heading__eyebrow"><span>规则驱动的运营动作</span><b>演示数据</b></div>
        <h1>自动化中心</h1>
        <p>先用确定性规则发现风险，再由运营确认任务；当前不会直接写入任何电商平台。</p>
      </div>
      <div class="page-heading__meta">
        <el-icon><Clock /></el-icon>
        <span
          >数据更新至
          <strong>{{
            overview ? dayjs(overview.data_updated_at).format('MM-DD HH:mm') : '同步中'
          }}</strong></span
        >
        <el-button
          :icon="Refresh"
          :loading="automationQuery.isFetching.value"
          @click="automationQuery.refetch"
        >
          刷新
        </el-button>
      </div>
    </header>

    <el-alert
      class="automation-alert"
      title="安全边界：当前规则只扫描演示数据并创建待确认结果，不会自动改价、退款、上下架或发送消息。"
      type="info"
      :closable="false"
      show-icon
    />

    <div v-if="automationQuery.isError.value" class="load-error-actions">
      <el-alert type="error" :closable="false" show-icon title="自动化规则加载失败，请重试。" />
      <el-button type="primary" plain @click="automationQuery.refetch">重试加载</el-button>
    </div>

    <section v-if="overview" class="automation-summary" aria-label="自动化摘要">
      <div class="summary-item">
        <span>已启用规则</span
        ><strong
          >{{ activeRules }}<small> / {{ rules.length }}</small></strong
        >
      </div>
      <div class="summary-item">
        <span>累计扫描发现</span><strong>{{ matchedCount }}<small> 个对象</small></strong>
      </div>
      <div class="summary-item">
        <span>待处理任务</span><strong>{{ pendingTaskCount }}<small> 个</small></strong>
      </div>
      <div class="summary-item summary-item--hint">
        <el-icon><CircleCheck /></el-icon><span>所有规则当前都需要建议或人工确认</span>
      </div>
    </section>

    <section class="rules-panel panel-surface">
      <div class="section-heading">
        <div>
          <span>策略配置</span>
          <h2>运营规则</h2>
        </div>
        <small>规则只生成任务，不代替平台确认</small>
      </div>

      <el-skeleton v-if="automationQuery.isPending.value" :rows="5" animated />
      <div v-else-if="rules.length" class="rule-list">
        <article v-for="rule in rules" :key="rule.id" class="rule-row">
          <div class="rule-icon" :class="`rule-icon--${rule.rule_type}`">
            <el-icon><component :is="ruleTypeIcon(rule.rule_type)" /></el-icon>
          </div>
          <div class="rule-copy">
            <div class="rule-title">
              <strong>{{ rule.name }}</strong>
              <el-tag size="small" effect="plain">{{ ruleTypeLabel(rule.rule_type) }}</el-tag>
              <el-tag size="small" :type="modeTagType(rule.mode)" effect="light">{{
                modeLabel(rule.mode)
              }}</el-tag>
            </div>
            <p>{{ rule.description }}</p>
            <div class="rule-meta">
              <span>{{ ruleConfig(rule) }}</span
              ><span>上次运行：{{ lastRunLabel(rule) }}</span>
            </div>
          </div>
          <div class="rule-controls">
            <el-switch
              :model-value="rule.is_enabled"
              :loading="toggleMutation.isPending.value"
              active-text="启用"
              inactive-text="暂停"
              @change="toggleRule(rule.id, $event)"
            />
            <el-button
              type="primary"
              plain
              :icon="VideoPlay"
              :loading="runMutation.isPending.value && runMutation.variables.value === rule.id"
              :disabled="!rule.is_enabled"
              @click="runMutation.mutate(rule.id)"
              >扫描现在</el-button
            >
          </div>
        </article>
      </div>
      <div v-else class="empty-copy">还没有可用规则。</div>
    </section>

    <section class="tasks-panel panel-surface">
      <div class="section-heading">
        <div>
          <span>运营收件箱</span>
          <h2>自动化任务</h2>
        </div>
        <small>同一规则同一对象每天自动去重</small>
      </div>
      <div v-if="tasks.length" class="task-list">
        <article v-for="task in tasks" :key="task.id" class="task-row">
          <div class="task-status-icon" :class="`task-status-icon--${task.severity}`">
            <el-icon><WarningFilled /></el-icon>
          </div>
          <div class="task-copy">
            <div class="task-title">
              <strong>{{ task.title }}</strong>
              <el-tag
                size="small"
                :type="task.severity === 'critical' ? 'danger' : 'warning'"
                effect="plain"
              >
                {{ taskSeverityLabel(task.severity) }}
              </el-tag>
              <el-tag size="small" :type="taskStatusType(task.status)" effect="light">
                {{ taskStatusLabel(task.status) }}
              </el-tag>
            </div>
            <p>{{ task.reason }}</p>
            <div class="task-meta">
              <span>{{ task.reference }}</span
              ><span>{{ task.suggested_action }}</span
              ><span>{{ taskDueLabel(task) }}</span>
            </div>
          </div>
          <div class="task-controls">
            <el-select
              :model-value="task.assignee ?? ''"
              class="task-assignee-select"
              size="small"
              placeholder="指派负责人"
              :loading="taskMutation.isPending.value"
              aria-label="指派任务负责人"
              @change="updateTaskAssignee(task, $event)"
            >
              <el-option label="暂不指派" value="" />
              <el-option label="徐店长" value="徐店长" />
              <el-option label="客服组" value="客服组" />
              <el-option label="商品运营组" value="商品运营组" />
            </el-select>
            <el-select
              :model-value="task.status"
              class="task-status-select"
              size="small"
              :loading="taskMutation.isPending.value"
              aria-label="更新任务状态"
              @change="updateTaskStatus(task, $event)"
            >
              <el-option label="待处理" value="pending" />
              <el-option label="处理中" value="in_progress" />
              <el-option label="已完成" value="completed" />
              <el-option label="已忽略" value="dismissed" />
            </el-select>
          </div>
        </article>
      </div>
      <el-empty v-else description="扫描规则后，命中的对象会出现在这里" />
    </section>

    <section class="runs-panel panel-surface">
      <div class="section-heading">
        <div>
          <span>执行记录</span>
          <h2>最近扫描</h2>
        </div>
        <small>保留最近 20 次规则运行</small>
      </div>
      <div v-if="runs.length" class="run-list">
        <article v-for="run in runs" :key="run.id" class="run-row">
          <div class="run-status" :class="{ 'run-status--failed': run.status === 'failed' }">
            <el-icon
              ><CircleCheck v-if="run.status === 'succeeded'" /><WarningFilled v-else
            /></el-icon>
          </div>
          <div class="run-copy">
            <strong>{{ run.rule_name }}</strong>
            <span
              >{{ dayjs(run.created_at).format('YYYY-MM-DD HH:mm') }} ·
              {{ runLabel(run.status) }}</span
            >
          </div>
          <div class="run-count">
            <strong>{{ run.matched_count }}</strong
            ><span>发现对象</span>
          </div>
          <div class="run-count">
            <strong>{{ run.task_count }}</strong
            ><span>待处理任务</span>
          </div>
          <el-button text type="primary" @click="openRun(run.id)">查看结果</el-button>
        </article>
      </div>
      <div v-else class="empty-copy">还没有扫描记录，先运行一条规则。</div>
    </section>

    <el-drawer v-model="resultDrawerOpen" title="规则扫描结果" size="min(680px, 100%)">
      <template v-if="selectedRun">
        <div class="drawer-summary">
          <strong>{{ selectedRun.rule_name }}</strong>
          <span
            >{{ dayjs(selectedRun.created_at).format('YYYY-MM-DD HH:mm') }} · 发现
            {{ selectedRun.matched_count }} 个对象</span
          >
        </div>
        <div v-if="selectedRun.results.length" class="match-list">
          <article
            v-for="item in selectedRun.results"
            :key="`${selectedRun.id}-${item.entity_id}`"
            class="match-row"
          >
            <div class="match-head">
              <strong>{{ item.title }}</strong>
              <el-tag size="small" :type="item.severity === 'critical' ? 'danger' : 'warning'">{{
                item.reference
              }}</el-tag>
            </div>
            <p>{{ item.reason }}</p>
            <span>{{ item.suggested_action }}</span>
          </article>
        </div>
        <el-empty v-else description="本次扫描没有发现待处理对象" />
      </template>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.automation-view {
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
.page-heading__meta strong {
  color: var(--text-secondary);
}
.automation-alert,
.load-error-actions {
  margin-bottom: 14px;
}
.load-error-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.load-error-actions .el-alert {
  flex: 1;
}
.automation-summary {
  display: grid;
  grid-template-columns: 160px 180px 160px 1fr;
  gap: 22px;
  align-items: center;
  margin-bottom: 14px;
  padding: 15px 18px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}
.summary-item {
  display: grid;
  gap: 5px;
  padding-right: 24px;
  border-right: 1px solid var(--border-soft);
}
.summary-item span {
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
}
.summary-item strong {
  color: var(--text-primary);
  font-size: 24px;
}
.summary-item strong small {
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
  font-weight: 500;
}
.summary-item--hint {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--success);
  border-right: 0;
}
.summary-item--hint span {
  color: var(--text-secondary);
}
.panel-surface {
  padding: 18px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}
.tasks-panel {
  margin-top: 14px;
}
.task-list {
  display: grid;
  gap: 8px;
}
.task-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) 138px;
  gap: 12px;
  align-items: center;
  padding: 13px 14px;
  background: var(--surface-subtle);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
}
.task-row:hover {
  border-color: #c9dbf5;
  background: #f8fbff;
}
.task-status-icon {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  color: var(--warning-dark);
  background: var(--warning-soft);
  border-radius: 8px;
}
.task-status-icon--critical {
  color: var(--danger);
  background: var(--danger-soft);
}
.task-copy {
  min-width: 0;
}
.task-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
}
.task-title strong {
  min-width: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-copy p {
  margin: 5px 0 6px;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
}
.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.task-controls {
  display: grid;
  gap: 6px;
}
.task-status-select,
.task-assignee-select {
  width: 138px;
}
.runs-panel {
  margin-top: 14px;
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
.rule-list,
.run-list {
  display: grid;
  gap: 8px;
}
.rule-row {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) auto;
  gap: 13px;
  align-items: center;
  padding: 14px;
  background: var(--surface-subtle);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
}
.rule-row:hover {
  border-color: #c9dbf5;
  background: #f8fbff;
}
.rule-icon {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 8px;
}
.rule-icon--after_sale_sla {
  color: var(--warning-dark);
  background: var(--warning-soft);
}
.rule-icon--product_quality {
  color: var(--danger);
  background: var(--danger-soft);
}
.rule-copy {
  min-width: 0;
}
.rule-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
}
.rule-title strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.rule-copy p {
  margin: 5px 0 7px;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
}
.rule-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.rule-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}
.run-row {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) 90px 100px auto;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-soft);
}
.run-row:last-child {
  border-bottom: 0;
}
.run-status {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  color: var(--success);
  background: var(--success-soft);
  border-radius: 50%;
}
.run-status--failed {
  color: var(--danger);
  background: var(--danger-soft);
}
.run-copy {
  min-width: 0;
}
.run-copy strong,
.run-copy span {
  display: block;
}
.run-copy strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.run-copy span {
  margin-top: 3px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.run-count {
  text-align: right;
}
.run-count strong,
.run-count span {
  display: block;
}
.run-count strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.run-count span {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.empty-copy {
  padding: 24px;
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
  text-align: center;
}
.drawer-summary {
  display: grid;
  gap: 5px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border-soft);
}
.drawer-summary strong {
  color: var(--text-primary);
  font-size: var(--font-size-subtitle);
}
.drawer-summary span {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.match-list {
  display: grid;
  gap: 8px;
  padding-top: 14px;
}
.match-row {
  padding: 12px;
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
}
.match-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.match-head strong {
  min-width: 0;
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.match-row p {
  margin: 7px 0 5px;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  line-height: 1.5;
}
.match-row > span {
  color: var(--primary);
  font-size: var(--font-size-caption);
  line-height: 1.5;
}
@media (max-width: 820px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .page-heading h1 {
    font-size: 28px;
    white-space: nowrap;
  }
  .page-heading__meta {
    width: 100%;
    justify-content: space-between;
  }
  .automation-summary {
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }
  .summary-item {
    padding-right: 14px;
  }
  .summary-item--hint {
    grid-column: 1 / -1;
    padding-top: 10px;
    border-top: 1px solid var(--border-soft);
  }
  .rule-row {
    grid-template-columns: 40px minmax(0, 1fr);
  }
  .rule-controls {
    grid-column: 2;
    justify-content: space-between;
  }
  .task-row {
    grid-template-columns: 34px minmax(0, 1fr);
  }
  .task-controls {
    grid-column: 2;
    grid-template-columns: 1fr 1fr;
  }
  .task-status-select,
  .task-assignee-select {
    width: 100%;
  }
  .run-row {
    grid-template-columns: 30px minmax(0, 1fr) auto;
  }
  .run-count {
    display: none;
  }
  .run-row .el-button {
    grid-column: 2 / -1;
    justify-self: start;
    padding-left: 0;
  }
}
@media (max-width: 520px) {
  .panel-surface {
    padding: 13px;
  }
  .automation-summary {
    padding: 13px;
  }
  .rule-title {
    align-items: flex-start;
    flex-direction: column;
    gap: 5px;
  }
  .task-controls {
    grid-template-columns: 1fr;
  }
}
</style>
