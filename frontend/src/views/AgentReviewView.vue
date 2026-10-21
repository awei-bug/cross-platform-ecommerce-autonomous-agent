<script setup lang="ts">
import {
  CircleCheck,
  CircleClose,
  Cpu,
  Document,
  MagicStick,
  Refresh,
  Search,
  VideoPlay,
  WarningFilled,
} from '@element-plus/icons-vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'

import { agentApi } from '../api'
import { useSessionStore } from '../stores/session'
import type {
  AgentRun,
  AgentStepKind,
  CompetitorImportResult,
  Diagnosis,
  DiagnosisConfidence,
  DiagnosisRiskLevel,
} from '../types/api'

const session = useSessionStore()
const queryClient = useQueryClient()

const GOAL_PRESETS = [
  '汇总 3 家店铺 7 天经营数据，对比竞品定价，诊断流量与转化问题，输出优化方案并自检复盘',
  '诊断各店铺库存风险并输出补货建议',
  '对比竞品卖点与定价，输出商品优化方案',
]

const SHOP_OPTIONS = [
  { value: 'shop-taobao-001', label: '柔肤旗舰店（淘宝）' },
  { value: 'shop-douyin-001', label: '柔肤抖音专营店（抖店）' },
  { value: 'shop-pdd-001', label: '柔肤品牌馆（拼多多）' },
]

const STEP_KIND_LABELS: Record<AgentStepKind, string> = {
  data_collect: '数据汇总',
  competitor_scan: '竞品扫描',
  diagnosis: '规则诊断',
  recommendation: '方案汇总',
  self_check: '反思自检',
  supplement_data: '补采数据',
  supplement_competitor: '补采竞品',
  rediagnosis: '重跑诊断',
}

const DIAGNOSIS_KIND_LABELS: Record<string, string> = {
  inventory: '库存风险',
  margin: '毛利结构',
  conversion: '转化效率',
  review: '差评风险',
  price_gap: '价格对标',
  after_sale: '售后时效',
}

const goalText = ref(GOAL_PRESETS[0])
const selectedShopIds = ref<string[]>([])
const selectedRunId = ref<string | null>(null)
const competitorKeyword = ref('')
const competitorDialogOpen = ref(false)
const competitorForm = ref({ title: '', price: 0, selling_points: '', review_pain_points: '' })

const taobaokeDialogOpen = ref(false)
const taobaokeKeyword = ref('')
const taobaokeLimit = ref(10)
const taobaokeNote = ref<string | null>(null)

const runsQuery = useQuery({
  queryKey: ['agent-runs'],
  queryFn: () => agentApi.runs(session.token!),
  enabled: computed(() => Boolean(session.token)),
})
const runs = computed(() => runsQuery.data.value ?? [])

const runDetailQuery = useQuery({
  queryKey: ['agent-run', selectedRunId],
  queryFn: () => agentApi.run(session.token!, selectedRunId.value!),
  enabled: computed(() => Boolean(session.token && selectedRunId.value)),
})
const runDetail = computed(() => runDetailQuery.data.value)

const competitorsQuery = useQuery({
  queryKey: ['agent-competitors', competitorKeyword],
  queryFn: () => agentApi.competitors(session.token!, { q: competitorKeyword.value || undefined }),
  enabled: computed(() => Boolean(session.token)),
})
const competitors = computed(() => competitorsQuery.data.value ?? [])

const createMutation = useMutation({
  mutationFn: () =>
    agentApi.createRun(session.token!, {
      goal: goalText.value.trim(),
      shop_ids: selectedShopIds.value,
    }),
  onSuccess: (run: AgentRun) => {
    selectedRunId.value = run.id
    ElMessage.success(
      run.status === 'succeeded'
        ? `复盘完成：${run.summary.diagnoses_total} 条带证据结论`
        : '运行结束，请查看步骤状态',
    )
    void queryClient.invalidateQueries({ queryKey: ['agent-runs'] })
    void queryClient.invalidateQueries({ queryKey: ['agent-run', run.id] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '启动复盘失败，请重试。')
  },
})

const decideMutation = useMutation({
  mutationFn: (input: { diagnosisId: string; decision: 'approve' | 'reject' }) =>
    agentApi.decide(session.token!, selectedRunId.value!, input.diagnosisId, {
      decision: input.decision,
      note: input.decision === 'approve' ? '已人工核对证据链' : '与当前运营策略冲突',
    }),
  onSuccess: (_data, variables) => {
    ElMessage.success(variables.decision === 'approve' ? '已确认该结论' : '已驳回该结论')
    void queryClient.invalidateQueries({ queryKey: ['agent-run', selectedRunId.value] })
    void queryClient.invalidateQueries({ queryKey: ['agent-runs'] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '决策提交失败，请重试。')
  },
})

const competitorSubmitMutation = useMutation({
  mutationFn: () => {
    const points = (value: string) =>
      value
        .split(/[,，、\n]/)
        .map((item) => item.trim())
        .filter(Boolean)
    return agentApi.createCompetitor(session.token!, {
      category: '美容护肤 / 面部护理',
      title: competitorForm.value.title.trim(),
      price: Number(competitorForm.value.price) || 0,
      selling_points: points(competitorForm.value.selling_points),
      review_pain_points: points(competitorForm.value.review_pain_points),
      platform_label: '人工录入',
    })
  },
  onSuccess: () => {
    ElMessage.success('竞品已录入知识库')
    competitorDialogOpen.value = false
    competitorForm.value = { title: '', price: 0, selling_points: '', review_pain_points: '' }
    void queryClient.invalidateQueries({ queryKey: ['agent-competitors'] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '录入失败，请重试。')
  },
})

const taobaokeImportMutation = useMutation({
  mutationFn: () =>
    agentApi.importTaobaoke(session.token!, {
      keyword: taobaokeKeyword.value.trim(),
      limit: taobaokeLimit.value,
    }),
  onSuccess: (result: CompetitorImportResult) => {
    taobaokeNote.value = result.note
    ElMessage.success(
      `已导入 ${result.created} 条、更新 ${result.updated} 条（来源：${result.source}）`,
    )
    taobaokeDialogOpen.value = false
    taobaokeKeyword.value = ''
    void queryClient.invalidateQueries({ queryKey: ['agent-competitors'] })
  },
  onError: (error: unknown) => {
    const detail = (error as { detail?: unknown })?.detail
    const message =
      (detail && typeof detail === 'object' && 'message' in detail
        ? String((detail as { message: unknown }).message)
        : '') || (error instanceof Error ? error.message : '淘宝客导入失败')
    ElMessage.error(message)
  },
})

function stepStatusType(status: AgentRun['steps'][number]['status']) {
  if (status === 'succeeded') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'primary'
  return 'info'
}

function runStatusLabel(status: AgentRun['status']) {
  return { planning: '规划中', running: '执行中', succeeded: '已完成', failed: '执行失败' }[status]
}

function severityType(severity: string) {
  return severity === 'critical' ? 'danger' : severity === 'warning' ? 'warning' : 'info'
}

function confidenceType(confidence: DiagnosisConfidence) {
  return confidence === 'high' ? 'success' : confidence === 'medium' ? 'warning' : 'info'
}

function diagnosisStatusLabel(status: Diagnosis['status']) {
  return { pending: '待人工决策', approved: '已确认', rejected: '已驳回' }[status]
}

function diagnosisStatusType(status: Diagnosis['status']) {
  return status === 'approved' ? 'success' : status === 'rejected' ? 'info' : 'warning'
}

function riskLabel(riskLevel: DiagnosisRiskLevel) {
  return riskLevel === 'high' ? '写操作建议 · 需人工确认' : '只读建议'
}

function shopScopeLabel(shopIds: string[]) {
  if (!shopIds.length || shopIds.includes('shop-all')) return '全部店铺'
  return shopIds
    .map((id) => SHOP_OPTIONS.find((item) => item.value === id)?.label ?? id)
    .join('、')
}

function waveGroups(run: AgentRun) {
  const groups = new Map<number, AgentRun['steps']>()
  for (const step of run.steps) {
    const list = groups.get(step.wave) ?? []
    list.push(step)
    groups.set(step.wave, list)
  }
  return [...groups.entries()]
    .sort((left, right) => left[0] - right[0])
    .map(([wave, steps]) => ({ wave, steps }))
}
</script>

<template>
  <div class="agent-view">
    <header class="page-heading">
      <div>
        <div class="page-heading__eyebrow"><span>目标驱动的智能体复盘</span><b>只读安全模式</b></div>
        <h1>智能体复盘</h1>
        <p>用一句业务目标驱动完整闭环：数据汇总、竞品对标、规则诊断、方案汇总、反思自检。</p>
      </div>
      <div class="page-heading__meta">
        <el-icon><Cpu /></el-icon>
        <span>已完成 <strong>{{ runs.length }}</strong> 次运行</span>
        <el-button :icon="Refresh" :loading="runsQuery.isFetching.value" @click="runsQuery.refetch">
          刷新
        </el-button>
      </div>
    </header>

    <el-alert
      class="agent-alert"
      title="安全边界：智能体全程只读。诊断结论必须携带指标证据，涉及改价、上下架、批量修改的建议一律拦截为人工确认，确认动作本身也不会写入任何平台。"
      type="info"
      :closable="false"
      show-icon
    />

    <section class="goal-panel panel-surface">
      <div class="section-heading">
        <div>
          <span>第一步</span>
          <h2>描述你的复盘目标</h2>
        </div>
        <small>系统自动拆解串行与并行子任务</small>
      </div>
      <el-input
        v-model="goalText"
        class="goal-input"
        type="textarea"
        :rows="2"
        maxlength="500"
        show-word-limit
        placeholder="例如：汇总 3 家店铺 7 天经营数据，对比竞品定价，诊断流量与转化问题，输出优化方案"
      />
      <div class="goal-presets">
        <span>快速模板：</span>
        <el-tag
          v-for="preset in GOAL_PRESETS"
          :key="preset"
          class="goal-preset"
          effect="plain"
          @click="goalText = preset"
        >
          {{ preset.slice(0, 18) }}…
        </el-tag>
      </div>
      <div class="goal-actions">
        <el-select
          v-model="selectedShopIds"
          class="goal-shops"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="默认全部店铺"
          aria-label="选择复盘店铺范围"
        >
          <el-option
            v-for="shop in SHOP_OPTIONS"
            :key="shop.value"
            :label="shop.label"
            :value="shop.value"
          />
        </el-select>
        <el-button
          type="primary"
          :icon="VideoPlay"
          :loading="createMutation.isPending.value"
          :disabled="goalText.trim().length < 4"
          @click="createMutation.mutate()"
        >
          启动复盘
        </el-button>
      </div>
    </section>

    <section v-if="runDetail" class="run-detail">
      <div class="run-detail__head panel-surface">
        <div class="run-detail__title">
          <strong>{{ runDetail.goal }}</strong>
          <div class="run-detail__tags">
            <el-tag size="small" :type="runDetail.status === 'succeeded' ? 'success' : runDetail.status === 'failed' ? 'danger' : 'info'">
              {{ runStatusLabel(runDetail.status) }}
            </el-tag>
            <el-tag size="small" effect="plain">{{ shopScopeLabel(runDetail.shop_ids) }}</el-tag>
            <el-tag v-if="runDetail.is_demo" size="small" type="warning" effect="plain">演示数据</el-tag>
          </div>
        </div>
        <div class="run-detail__stats">
          <div class="stat-item">
            <span>执行步骤</span
            ><strong
              >{{ runDetail.summary.steps_succeeded }}<small> / {{ runDetail.summary.steps_total }}</small></strong
            >
          </div>
          <div class="stat-item">
            <span>有效结论</span><strong>{{ runDetail.summary.diagnoses_total }}</strong>
          </div>
          <div class="stat-item">
            <span>反思丢弃</span><strong>{{ runDetail.summary.discarded_conclusions }}</strong>
          </div>
          <div class="stat-item">
            <span>补采轮次</span><strong>{{ runDetail.summary.supplement_rounds }}</strong>
          </div>
          <div class="stat-item stat-item--alert">
            <span>待人工确认</span><strong>{{ runDetail.summary.high_risk_pending }}</strong>
          </div>
        </div>
      </div>

      <div class="run-detail__body">
        <div class="run-detail__main">
          <section class="panel-surface">
            <div class="section-heading">
              <div>
                <span>执行档案</span>
                <h2>步骤时间线</h2>
              </div>
              <small>同波次步骤并行执行</small>
            </div>
            <div v-for="group in waveGroups(runDetail)" :key="group.wave" class="wave-group">
              <div class="wave-label">波次 {{ group.wave }}{{ group.steps.length > 1 ? ' · 并行' : '' }}</div>
              <article v-for="step in group.steps" :key="step.id" class="step-row">
                <div class="step-status" :class="`step-status--${step.status}`">
                  <el-icon
                    ><CircleCheck v-if="step.status === 'succeeded'" /><WarningFilled v-else-if="step.status === 'failed'" /><Cpu v-else
                  /></el-icon>
                </div>
                <div class="step-copy">
                  <div class="step-title">
                    <strong>{{ step.title }}</strong>
                    <el-tag size="small" effect="plain">{{ STEP_KIND_LABELS[step.kind] }}</el-tag>
                    <el-tag size="small" :type="stepStatusType(step.status)" effect="light">{{
                      step.status === 'succeeded' ? '完成' : step.status === 'failed' ? '失败' : step.status === 'running' ? '执行中' : '等待'
                    }}</el-tag>
                  </div>
                  <p v-if="step.error_message" class="step-error">{{ step.error_message }}</p>
                  <span class="step-meta">耗时 {{ step.duration_ms }} ms</span>
                </div>
              </article>
            </div>
          </section>

          <section class="panel-surface">
            <div class="section-heading">
              <div>
                <span>反思记录</span>
                <h2>自检结论</h2>
              </div>
              <small>无证据不结论，信息不足先补采</small>
            </div>
            <ol v-if="runDetail.summary.reflection_notes.length" class="reflection-list">
              <li v-for="(note, index) in runDetail.summary.reflection_notes" :key="index">{{ note }}</li>
            </ol>
            <el-empty v-else description="本次运行没有触发反思拦截" :image-size="60" />
          </section>

          <section class="panel-surface">
            <div class="section-heading">
              <div>
                <span>可执行输出</span>
                <h2>诊断结论（{{ runDetail.diagnoses.length }}）</h2>
              </div>
              <small>每条结论均可追溯至具体指标</small>
            </div>
            <div v-if="runDetail.diagnoses.length" class="diagnosis-list">
              <article v-for="item in runDetail.diagnoses" :key="item.id" class="diagnosis-row">
                <div class="diagnosis-head">
                  <div class="diagnosis-title">
                    <strong>{{ item.title }}</strong>
                    <el-tag size="small" :type="severityType(item.severity)" effect="plain">
                      {{ item.severity === 'critical' ? '高风险' : item.severity === 'warning' ? '需关注' : '提示' }}
                    </el-tag>
                    <el-tag size="small" effect="plain">{{ DIAGNOSIS_KIND_LABELS[item.kind] ?? item.kind }}</el-tag>
                    <el-tag size="small" :type="confidenceType(item.confidence)" effect="light">
                      置信度 {{ item.confidence === 'high' ? '高' : item.confidence === 'medium' ? '中' : '低' }}
                    </el-tag>
                    <el-tag size="small" :type="item.risk_level === 'high' ? 'danger' : 'success'" effect="light">
                      {{ riskLabel(item.risk_level) }}
                    </el-tag>
                  </div>
                  <el-tag size="small" :type="diagnosisStatusType(item.status)" effect="plain">
                    {{ diagnosisStatusLabel(item.status) }}
                  </el-tag>
                </div>
                <p class="diagnosis-detail">{{ item.detail }}</p>
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
                    <tr v-for="(evidence, index) in item.evidence" :key="index">
                      <td>{{ evidence.metric }}</td>
                      <td><strong>{{ evidence.value }}</strong></td>
                      <td>{{ evidence.threshold }}</td>
                      <td>{{ evidence.source }}</td>
                    </tr>
                  </tbody>
                </table>
                <div class="diagnosis-foot">
                  <span class="diagnosis-action">
                    <el-icon><MagicStick /></el-icon>{{ item.recommendation }}
                  </span>
                  <span v-if="item.decided_by" class="diagnosis-decision">
                    {{ item.decision_note || '已决策' }} · {{ item.decided_by }}
                  </span>
                  <div v-if="item.status === 'pending'" class="diagnosis-controls">
                    <el-button
                      size="small"
                      type="primary"
                      :loading="decideMutation.isPending.value"
                      @click="decideMutation.mutate({ diagnosisId: item.id, decision: 'approve' })"
                    >
                      确认采纳
                    </el-button>
                    <el-button
                      size="small"
                      :icon="CircleClose"
                      :loading="decideMutation.isPending.value"
                      @click="decideMutation.mutate({ diagnosisId: item.id, decision: 'reject' })"
                    >
                      驳回
                    </el-button>
                  </div>
                </div>
              </article>
            </div>
            <el-empty v-else description="本次运行没有产生有效结论" :image-size="60" />
          </section>
        </div>

        <aside class="run-detail__side">
          <section class="panel-surface">
            <div class="section-heading">
              <div>
                <span>历史</span>
                <h2>运行记录</h2>
              </div>
            </div>
            <div v-if="runs.length" class="run-history">
              <button
                v-for="item in runs"
                :key="item.id"
                type="button"
                class="history-row"
                :class="{ 'history-row--active': item.id === selectedRunId }"
                @click="selectedRunId = item.id"
              >
                <strong>{{ item.goal.slice(0, 24) }}{{ item.goal.length > 24 ? '…' : '' }}</strong>
                <span>
                  {{ dayjs(item.created_at).format('MM-DD HH:mm') }} ·
                  {{ item.diagnoses_total }} 条结论
                  <em v-if="item.high_risk_pending"> · {{ item.high_risk_pending }} 待确认</em>
                </span>
              </button>
            </div>
            <el-empty v-else description="还没有运行记录" :image-size="60" />
          </section>

          <section class="panel-surface">
            <div class="section-heading">
              <div>
                <span>知识库</span>
                <h2>竞品库</h2>
              </div>
              <div class="competitor-actions">
                <el-button size="small" :icon="Document" @click="competitorDialogOpen = true">录入</el-button>
                <el-button
                  size="small"
                  type="primary"
                  plain
                  :icon="Search"
                  @click="taobaokeDialogOpen = true"
                  >从淘宝客导入</el-button
                >
              </div>
            </div>
            <el-input
              v-model="competitorKeyword"
              class="competitor-search"
              size="small"
              placeholder="搜索竞品标题或卖点"
              :prefix-icon="Search"
              clearable
            />
            <div class="competitor-list">
              <article v-for="item in competitors" :key="item.id" class="competitor-row">
                <div class="competitor-head">
                  <strong>{{ item.title }}</strong>
                  <span class="competitor-price">¥{{ item.price.toFixed(2) }}</span>
                </div>
                <div class="competitor-meta">
                  <el-tag size="small" effect="plain">{{ item.platform_label }}</el-tag>
                  <el-tag size="small" type="info" effect="plain">7 日销 {{ item.sales_7d }}</el-tag>
                  <el-tag v-if="item.similarity" size="small" type="success" effect="plain">
                    相似度 {{ item.similarity.toFixed(2) }}
                  </el-tag>
                </div>
                <p v-if="item.selling_points.length" class="competitor-points">
                  卖点：{{ item.selling_points.join(' / ') }}
                </p>
                <p v-if="item.review_pain_points.length" class="competitor-points competitor-points--pain">
                  痛点：{{ item.review_pain_points.join(' / ') }}
                </p>
              </article>
            </div>
          </section>
        </aside>
      </div>
    </section>

    <el-empty v-else description="先描述一个复盘目标，系统会自动规划并执行完整闭环" :image-size="90">
      <template #description>
        <p>先描述一个复盘目标，系统会自动规划并执行完整闭环。</p>
        <p class="empty-hint">规划拆解 → 并行执行 → 反思校验 → 人工确认</p>
      </template>
    </el-empty>

    <el-dialog v-model="competitorDialogOpen" title="录入竞品" width="min(520px, 100%)">
      <el-form label-position="top">
        <el-form-item label="竞品标题">
          <el-input v-model="competitorForm.title" maxlength="200" placeholder="例如：竞品 玻尿酸保湿安瓶精华" />
        </el-form-item>
        <el-form-item label="售价（元）">
          <el-input-number v-model="competitorForm.price" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="核心卖点（逗号分隔）">
          <el-input v-model="competitorForm.selling_points" placeholder="小分子玻尿酸, 7 天补水" />
        </el-form-item>
        <el-form-item label="评价痛点（逗号分隔）">
          <el-input v-model="competitorForm.review_pain_points" placeholder="包装易漏液, 客服响应慢" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="competitorDialogOpen = false">取消</el-button>
        <el-button
          type="primary"
          :loading="competitorSubmitMutation.isPending.value"
          :disabled="competitorForm.title.trim().length < 2"
          @click="competitorSubmitMutation.mutate()"
        >
          保存到知识库
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="taobaokeDialogOpen" title="从淘宝客导入竞品" width="min(520px, 100%)">
      <el-alert
        class="taobaoke-alert"
        title="淘宝客是阿里妈妈的公开商品接口，个人实名即可申请，无需店铺授权；导入的是真实公开商品数据（券后价、平台销量口径）。"
        type="info"
        :closable="false"
        show-icon
      />
      <el-form label-position="top" style="margin-top: 12px">
        <el-form-item label="关键词">
          <el-input
            v-model="taobaokeKeyword"
            maxlength="50"
            placeholder="例如：玻尿酸 精华 补水"
            @keyup.enter="taobaokeImportMutation.mutate()"
          />
        </el-form-item>
        <el-form-item label="导入条数">
          <el-input-number v-model="taobaokeLimit" :min="1" :max="40" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taobaokeDialogOpen = false">取消</el-button>
        <el-button
          type="primary"
          :loading="taobaokeImportMutation.isPending.value"
          :disabled="taobaokeKeyword.trim().length < 1"
          @click="taobaokeImportMutation.mutate()"
        >
          导入真实竞品
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.agent-view {
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
.agent-alert {
  margin-bottom: 14px;
}
.panel-surface {
  padding: 18px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
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
.goal-panel {
  margin-bottom: 14px;
}
.goal-presets {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 10px 0 14px;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.goal-preset {
  cursor: pointer;
}
.goal-actions {
  display: flex;
  gap: 12px;
}
.goal-shops {
  max-width: 420px;
}
.run-detail__head {
  margin-bottom: 14px;
}
.run-detail__title strong {
  display: block;
  color: var(--text-primary);
  font-size: var(--font-size-subtitle);
  line-height: 1.5;
}
.run-detail__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 8px;
}
.run-detail__stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 18px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-soft);
}
.stat-item {
  display: grid;
  gap: 4px;
}
.stat-item span {
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
}
.stat-item strong {
  color: var(--text-primary);
  font-size: 22px;
}
.stat-item strong small {
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
  font-weight: 500;
}
.stat-item--alert strong {
  color: var(--danger);
}
.run-detail__body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 14px;
  align-items: start;
}
.run-detail__main {
  display: grid;
  gap: 14px;
  min-width: 0;
}
.run-detail__side {
  display: grid;
  gap: 14px;
}
.wave-group {
  margin-bottom: 12px;
}
.wave-label {
  margin-bottom: 6px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  font-weight: 700;
}
.step-row {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 11px;
  align-items: flex-start;
  padding: 10px 12px;
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
}
.step-row + .step-row {
  margin-top: 6px;
}
.step-status {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  color: var(--success);
  background: var(--success-soft);
  border-radius: 50%;
}
.step-status--failed {
  color: var(--danger);
  background: var(--danger-soft);
}
.step-status--running {
  color: var(--primary);
  background: var(--primary-soft);
}
.step-status--pending,
.step-status--skipped {
  color: var(--text-tertiary);
  background: #eef2f7;
}
.step-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
}
.step-title strong {
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.step-meta {
  display: block;
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.step-error {
  margin: 5px 0 0;
  color: var(--danger);
  font-size: var(--font-size-meta);
}
.reflection-list {
  margin: 0;
  padding-left: 20px;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  line-height: 1.8;
}
.diagnosis-list {
  display: grid;
  gap: 10px;
}
.diagnosis-row {
  padding: 13px 14px;
  background: var(--surface-subtle);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
}
.diagnosis-row:hover {
  border-color: #c9dbf5;
  background: #f8fbff;
}
.diagnosis-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.diagnosis-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
}
.diagnosis-title strong {
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.diagnosis-detail {
  margin: 8px 0 10px;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  line-height: 1.6;
}
.evidence-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-caption);
}
.evidence-table th,
.evidence-table td {
  padding: 6px 8px;
  text-align: left;
  border-bottom: 1px solid var(--border-soft);
}
.evidence-table th {
  color: var(--text-tertiary);
  font-weight: 600;
  background: #f6f9fd;
}
.evidence-table td {
  color: var(--text-secondary);
}
.diagnosis-foot {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
}
.diagnosis-action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 220px;
  color: var(--primary);
  font-size: var(--font-size-meta);
}
.diagnosis-decision {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.diagnosis-controls {
  display: flex;
  gap: 8px;
}
.run-history {
  display: grid;
  gap: 6px;
}
.history-row {
  display: grid;
  gap: 4px;
  padding: 9px 11px;
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
  font-size: var(--font-size-label);
}
.history-row span {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.history-row em {
  color: var(--danger);
  font-style: normal;
}
.competitor-search {
  margin-bottom: 10px;
}
.competitor-actions {
  display: flex;
  gap: 8px;
}
.taobaoke-alert {
  margin-bottom: 4px;
}
.competitor-list {
  display: grid;
  gap: 8px;
  max-height: 420px;
  overflow-y: auto;
}
.competitor-row {
  padding: 10px 11px;
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
}
.competitor-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.competitor-head strong {
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.competitor-price {
  color: var(--danger);
  font-size: var(--font-size-label);
  font-weight: 700;
}
.competitor-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 6px 0;
}
.competitor-points {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: 1.6;
}
.competitor-points--pain {
  color: var(--text-tertiary);
}
.empty-hint {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
@media (max-width: 1080px) {
  .run-detail__body {
    grid-template-columns: minmax(0, 1fr);
  }
  .run-detail__stats {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .goal-actions {
    flex-direction: column;
  }
  .goal-shops {
    max-width: none;
  }
  .run-detail__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
