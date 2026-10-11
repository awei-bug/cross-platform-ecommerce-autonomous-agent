<script setup lang="ts">
import {
  ChatDotRound,
  Clock,
  CollectionTag,
  EditPen,
  Refresh,
  Search,
  Star,
  WarningFilled,
} from '@element-plus/icons-vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, reactive, ref } from 'vue'

import { reviewApi } from '../api'
import EmptyState from '../components/business/EmptyState.vue'
import { useSessionStore } from '../stores/session'
import { useWorkspaceStore } from '../stores/workspace'
import type { ReviewItem, ReviewRating, ReviewTemplate, ReviewTicketStatus } from '../types/api'

const session = useSessionStore()
const workspace = useWorkspaceStore()
const queryClient = useQueryClient()
const filters = reactive({
  product_id: '',
  rating: '' as ReviewRating | '',
  ticket_status: '' as ReviewTicketStatus | '',
  q: '',
})
const detailOpen = ref(false)
const activeReview = ref<ReviewItem | null>(null)
const ticketForm = reactive({
  assignee: '运营待分配',
  status: 'open' as ReviewTicketStatus,
  reply_draft: '',
  follow_up_note: '',
})

const reviewQuery = useQuery({
  queryKey: computed(() => [
    'reviews',
    workspace.currentShopId,
    workspace.platformFilter,
    filters.product_id,
    filters.rating,
    filters.ticket_status,
    filters.q,
  ]),
  queryFn: () =>
    reviewApi.overview(session.token!, {
      shop_id: workspace.currentShopId,
      platform: workspace.platformFilter,
      product_id: filters.product_id,
      rating: filters.rating || undefined,
      ticket_status: filters.ticket_status || undefined,
      q: filters.q,
    }),
  enabled: computed(() => Boolean(session.token)),
})
const overview = computed(() => reviewQuery.data.value)
const summary = computed(() => overview.value?.summary)
const reviews = computed(() => overview.value?.reviews ?? [])
const products = computed(() => overview.value?.products ?? [])
const tickets = computed(() => overview.value?.tickets ?? [])
const negativeReviews = computed(() =>
  reviews.value.filter((review) => review.rating_label === 'negative'),
)
const wordMax = computed(() =>
  Math.max(...(overview.value?.words.map((word) => word.count) ?? [1])),
)

const ticketMutation = useMutation({
  mutationFn: () =>
    reviewApi.updateTicket(session.token!, {
      review_id: activeReview.value!.id,
      assignee: ticketForm.assignee,
      status: ticketForm.status,
      reply_draft: ticketForm.reply_draft,
      follow_up_note: ticketForm.follow_up_note,
    }),
  onSuccess: () => {
    ElMessage.success('差评工单已更新（演示数据）')
    detailOpen.value = false
    void queryClient.invalidateQueries({ queryKey: ['reviews'] })
  },
})

function openTicket(review: ReviewItem) {
  activeReview.value = review
  const ticket = tickets.value.find((item) => item.review_id === review.id)
  ticketForm.assignee = ticket?.assignee ?? '运营待分配'
  ticketForm.status = ticket?.status ?? 'open'
  ticketForm.reply_draft = ticket?.reply_draft ?? ''
  ticketForm.follow_up_note = ticket?.follow_up_note ?? ''
  detailOpen.value = true
}

function applyTemplate(template: ReviewTemplate) {
  ticketForm.reply_draft = template.content
  ElMessage.success(`已套用「${template.name}」模板`)
}

function ratingLabel(rating: ReviewRating) {
  return { positive: '好评', neutral: '中评', negative: '差评' }[rating]
}

function ticketLabel(status: ReviewTicketStatus | null) {
  return { open: '待处理', in_progress: '跟进中', resolved: '已解决' }[status ?? 'open']
}

function ticketType(status: ReviewTicketStatus | null) {
  return { open: 'danger', in_progress: 'warning', resolved: 'success' }[status ?? 'open'] as
    'danger' | 'warning' | 'success'
}

function wordSize(count: number) {
  return `${12 + Math.round((count / wordMax.value) * 14)}px`
}

function resetFilters() {
  filters.product_id = ''
  filters.rating = ''
  filters.ticket_status = ''
  filters.q = ''
}
</script>

<template>
  <div class="review-view">
    <header class="page-heading">
      <div>
        <div class="page-heading__eyebrow"><span>评论与舆情</span><b>演示数据</b></div>
        <h1>评论风险监控台</h1>
        <p>把差评、用户原话和跟进工单放在同一条处理链上，先解决影响口碑的真实问题。</p>
      </div>
      <div class="page-heading__meta">
        <el-icon><Clock /></el-icon>
        <span
          >更新于
          <strong>{{
            overview ? dayjs(overview.data_updated_at).format('MM-DD HH:mm') : '同步中'
          }}</strong></span
        >
        <el-button
          :icon="Refresh"
          :loading="reviewQuery.isFetching.value"
          @click="reviewQuery.refetch"
          >刷新</el-button
        >
      </div>
    </header>

    <el-alert
      class="demo-alert"
      title="当前为演示数据，评论来自本地 Mock；AI 仅生成待确认回复，不会自动发送。"
      type="info"
      :closable="false"
      show-icon
    />
    <div v-if="reviewQuery.isError.value" class="load-error-actions">
      <el-alert type="error" :closable="false" show-icon title="评论数据加载失败，请重试。" />
      <el-button type="primary" plain @click="reviewQuery.refetch">重试加载</el-button>
    </div>

    <section v-if="summary" class="review-summary" aria-label="评论摘要">
      <article class="summary-card summary-card--total">
        <span>监控评价</span><strong>{{ summary.total.toLocaleString() }}</strong
        ><small>覆盖 {{ summary.monitored_products }} 个商品</small>
      </article>
      <article class="summary-card summary-card--positive">
        <span>好评</span><strong>{{ summary.positive }}</strong
        ><small>正向体验反馈</small>
      </article>
      <article class="summary-card summary-card--neutral">
        <span>中评</span><strong>{{ summary.neutral }}</strong
        ><small>值得继续观察</small>
      </article>
      <article class="summary-card summary-card--negative">
        <span>差评</span><strong>{{ summary.negative }}</strong
        ><small>需要人工跟进</small>
      </article>
      <article class="summary-card summary-card--ticket">
        <span>未闭环工单</span><strong>{{ summary.open_tickets }}</strong
        ><small>含待处理与跟进中</small>
      </article>
    </section>

    <section class="review-toolbar panel-surface">
      <div class="toolbar-title"><span>评价列表</span><strong>全平台口碑明细</strong></div>
      <el-select
        v-model="filters.product_id"
        clearable
        filterable
        placeholder="选择监控商品"
        class="product-filter"
      >
        <el-option
          v-for="product in products"
          :key="product.id"
          :label="product.title"
          :value="product.id"
        />
      </el-select>
      <el-select v-model="filters.rating" clearable placeholder="评价类型" class="small-filter">
        <el-option label="全部评价" value="" /><el-option label="好评" value="positive" /><el-option
          label="中评"
          value="neutral"
        /><el-option label="差评" value="negative" />
      </el-select>
      <el-select
        v-model="filters.ticket_status"
        clearable
        placeholder="工单状态"
        class="small-filter"
      >
        <el-option label="待处理" value="open" /><el-option
          label="跟进中"
          value="in_progress"
        /><el-option label="已解决" value="resolved" />
      </el-select>
      <el-input
        v-model="filters.q"
        clearable
        :prefix-icon="Search"
        placeholder="搜索评价、商品或关键词"
        class="review-search"
      />
      <el-button @click="resetFilters">重置</el-button>
    </section>

    <main class="review-grid">
      <section class="review-list panel-surface">
        <div class="section-heading">
          <div>
            <span>用户原话</span>
            <h2>评价明细</h2>
          </div>
          <small>{{ reviews.length }} 条结果 · 关键词已提取</small>
        </div>
        <div v-if="reviewQuery.isLoading.value" class="loading-state">正在加载评论数据…</div>
        <EmptyState
          v-else-if="!reviews.length"
          title="没有匹配评价"
          description="可以放宽平台、商品或评价类型筛选。"
        />
        <div v-else class="review-items">
          <article
            v-for="review in reviews"
            :key="review.id"
            class="review-item"
            :class="{ 'review-item--negative': review.rating_label === 'negative' }"
          >
            <div class="review-item__top">
              <div class="review-item__identity">
                <span class="platform-dot" :class="`platform-dot--${review.platform}`"></span
                ><strong>{{ review.buyer_nickname }}</strong
                ><span class="muted">{{ review.platform_label }} · {{ review.shop_name }}</span>
              </div>
              <time>{{ dayjs(review.created_at).format('MM-DD HH:mm') }}</time>
            </div>
            <div class="review-item__rating">
              <span class="stars"
                ><el-icon
                  v-for="star in 5"
                  :key="star"
                  :class="{ 'star--active': star <= review.rating }"
                  ><Star /></el-icon></span
              ><el-tag
                size="small"
                :type="
                  review.rating_label === 'negative'
                    ? 'danger'
                    : review.rating_label === 'neutral'
                      ? 'warning'
                      : 'success'
                "
                >{{ ratingLabel(review.rating_label) }}</el-tag
              ><span class="muted">{{ review.product_title }}</span>
            </div>
            <p class="review-item__content">{{ review.content }}</p>
            <div class="review-item__foot">
              <div class="keyword-list">
                <span
                  v-for="keyword in review.keywords"
                  :key="keyword"
                  :class="{ 'keyword--negative': review.rating_label === 'negative' }"
                  ># {{ keyword }}</span
                >
              </div>
              <el-button
                v-if="review.rating_label === 'negative'"
                text
                type="danger"
                :icon="ChatDotRound"
                @click="openTicket(review)"
                >{{ review.ticket_id ? '处理工单' : '创建工单' }}</el-button
              ><span v-else class="handled-label"
                ><el-icon><CollectionTag /></el-icon>已纳入舆情分析</span
              >
            </div>
          </article>
        </div>
      </section>

      <aside class="review-side">
        <section class="panel-surface word-panel">
          <div class="section-heading">
            <div>
              <span>关键词聚合</span>
              <h2>舆情词云</h2>
            </div>
            <small>近 7 日</small>
          </div>
          <div class="word-cloud">
            <span
              v-for="word in overview?.words ?? []"
              :key="word.word"
              :class="`word--${word.sentiment}`"
              :style="{ fontSize: wordSize(word.count) }"
              >{{ word.word }}<sup>{{ word.count }}</sup></span
            >
          </div>
          <div class="word-legend">
            <span><i class="legend-positive"></i>正向</span
            ><span><i class="legend-neutral"></i>中性</span
            ><span><i class="legend-negative"></i>风险</span>
          </div>
        </section>
        <section class="panel-surface ticket-panel">
          <div class="section-heading">
            <div>
              <span>风险处置</span>
              <h2>差评工单</h2>
            </div>
            <el-tag type="danger" effect="plain">{{ negativeReviews.length }} 条差评</el-tag>
          </div>
          <div v-if="tickets.length" class="ticket-list">
            <button
              v-for="ticket in tickets"
              :key="ticket.id"
              type="button"
              class="ticket-row"
              @click="openTicket(reviews.find((review) => review.id === ticket.review_id)!)"
            >
              <span class="ticket-row__signal"></span
              ><span
                ><strong>{{ ticket.title }}</strong
                ><small
                  >{{ ticket.assignee }} ·
                  {{ dayjs(ticket.updated_at).format('MM-DD HH:mm') }}</small
                ></span
              ><el-tag size="small" :type="ticketType(ticket.status)">{{
                ticketLabel(ticket.status)
              }}</el-tag>
            </button>
          </div>
          <div v-else class="side-empty">暂无差评工单</div>
        </section>
      </aside>
    </main>

    <section class="panel-surface template-panel">
      <div class="section-heading">
        <div>
          <span>标准化回复</span>
          <h2>评论模板库</h2>
        </div>
        <small>选择模板后仍需人工确认再发送</small>
      </div>
      <div class="template-grid">
        <article v-for="template in overview?.templates ?? []" :key="template.id">
          <div>
            <el-tag size="small" effect="plain">{{ template.scenario }}</el-tag
            ><span>{{ template.tone }}</span>
          </div>
          <strong>{{ template.name }}</strong>
          <p>{{ template.content }}</p>
          <el-button
            text
            type="primary"
            :icon="EditPen"
            @click="activeReview ? applyTemplate(template) : ElMessage.info('请先打开一条差评工单')"
            >套用模板</el-button
          >
        </article>
      </div>
    </section>

    <el-drawer v-model="detailOpen" title="差评工单处置" size="min(520px, 100%)">
      <template v-if="activeReview">
        <div class="drawer-review">
          <div>
            <el-tag type="danger">{{ ratingLabel(activeReview.rating_label) }}</el-tag
            ><strong>{{ activeReview.product_title }}</strong>
          </div>
          <p>{{ activeReview.content }}</p>
          <small>{{ activeReview.buyer_nickname }} · {{ activeReview.platform_label }}</small>
        </div>
        <el-divider />
        <div class="drawer-form">
          <label>指派给</label
          ><el-select v-model="ticketForm.assignee"
            ><el-option label="运营待分配" value="运营待分配" /><el-option
              label="林小满"
              value="林小满" /><el-option label="周子涵" value="周子涵" /></el-select
          ><label>工单状态</label
          ><el-select v-model="ticketForm.status"
            ><el-option label="待处理" value="open" /><el-option
              label="跟进中"
              value="in_progress" /><el-option label="已解决" value="resolved" /></el-select
          ><label>回复草稿</label
          ><el-input
            v-model="ticketForm.reply_draft"
            type="textarea"
            :rows="5"
            placeholder="输入或套用模板生成待确认回复"
          /><label>跟进记录</label
          ><el-input
            v-model="ticketForm.follow_up_note"
            type="textarea"
            :rows="3"
            placeholder="记录联系结果、补发或退款处理"
          />
        </div>
        <div class="drawer-note">
          <el-icon><WarningFilled /></el-icon
          ><span>回复内容只保存为草稿，不会自动发送到任何平台。</span>
        </div>
        <div class="drawer-actions">
          <el-button @click="detailOpen = false">取消</el-button
          ><el-button
            type="primary"
            :loading="ticketMutation.isPending.value"
            @click="ticketMutation.mutate()"
            >保存工单</el-button
          >
        </div>
      </template>
    </el-drawer>
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
.review-view {
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
.review-summary {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}
.summary-card {
  display: grid;
  gap: 5px;
  min-height: 104px;
  padding: 16px 18px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border-top: 3px solid var(--primary);
}
.summary-card--positive {
  border-top-color: var(--success);
}
.summary-card--neutral {
  border-top-color: var(--warning);
}
.summary-card--negative {
  border-top-color: var(--danger);
}
.summary-card--ticket {
  border-top-color: #8a5cf6;
}
.summary-card span {
  color: var(--text-secondary);
  font-size: var(--font-size-label);
}
.summary-card strong {
  color: var(--text-primary);
  font-size: 27px;
  line-height: 1;
}
.summary-card small {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.panel-surface {
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}
.review-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  padding: 13px 16px;
}
.toolbar-title {
  display: grid;
  min-width: 140px;
  gap: 3px;
  margin-right: auto;
}
.toolbar-title span,
.section-heading span {
  color: var(--primary);
  font-size: var(--font-size-meta);
  font-weight: 700;
}
.toolbar-title strong {
  color: var(--text-primary);
  font-size: var(--font-size-subtitle);
}
.product-filter {
  width: 220px;
}
.small-filter {
  width: 130px;
}
.review-search {
  width: 220px;
}
.review-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.75fr);
  gap: 14px;
  align-items: start;
}
.review-list,
.word-panel,
.ticket-panel,
.template-panel {
  padding: 18px;
}
.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.section-heading h2 {
  margin: 4px 0 0;
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
  letter-spacing: -0.02em;
}
.section-heading small {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.review-items {
  display: grid;
  gap: 10px;
}
.review-item {
  padding: 15px 16px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  background: var(--surface-subtle);
}
.review-item--negative {
  border-left: 3px solid var(--danger);
  background: #fffafb;
}
.review-item__top,
.review-item__identity,
.review-item__rating,
.review-item__foot {
  display: flex;
  align-items: center;
  gap: 9px;
}
.review-item__top {
  justify-content: space-between;
}
.review-item__top time {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.review-item__identity {
  min-width: 0;
}
.review-item__identity strong {
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.muted {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.platform-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary);
}
.platform-dot--douyin {
  background: #111827;
}
.platform-dot--pinduoduo {
  background: #ef4444;
}
.review-item__rating {
  margin-top: 10px;
}
.stars {
  display: inline-flex;
  gap: 1px;
  color: #d6deea;
}
.stars :deep(.star--active) {
  color: #e79a16;
}
.stars .el-icon {
  font-size: var(--font-size-body);
}
.review-item__content {
  margin: 10px 0 12px;
  color: var(--text-primary);
  font-size: var(--font-size-body);
  line-height: 1.75;
}
.review-item__foot {
  justify-content: space-between;
  align-items: flex-end;
}
.keyword-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.keyword-list span {
  padding: 3px 7px;
  color: var(--success-dark);
  background: var(--success-soft);
  border-radius: 4px;
  font-size: var(--font-size-caption);
}
.keyword-list .keyword--negative {
  color: var(--danger-dark);
  background: var(--danger-soft);
}
.handled-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.review-side {
  display: grid;
  gap: 14px;
}
.word-cloud {
  display: flex;
  min-height: 174px;
  flex-wrap: wrap;
  align-content: center;
  justify-content: center;
  gap: 14px 17px;
  padding: 17px;
  background: var(--surface-subtle);
  border-radius: var(--radius-md);
}
.word-cloud span {
  font-weight: 700;
  line-height: 1;
}
.word-cloud sup {
  margin-left: 3px;
  color: currentColor;
  font-size: var(--font-size-caption);
  opacity: 0.65;
}
.word--positive {
  color: var(--success-dark);
}
.word--neutral {
  color: var(--warning-dark);
}
.word--negative {
  color: var(--danger);
}
.word-legend {
  display: flex;
  gap: 14px;
  margin-top: 12px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.word-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.word-legend i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.legend-positive {
  background: var(--success);
}
.legend-neutral {
  background: var(--warning);
}
.legend-negative {
  background: var(--danger);
}
.ticket-list {
  display: grid;
  gap: 7px;
}
.ticket-row {
  display: grid;
  grid-template-columns: 8px 1fr auto;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 10px;
  text-align: left;
  background: var(--surface-subtle);
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.ticket-row:hover {
  background: var(--primary-softer);
}
.ticket-row__signal {
  width: 7px;
  height: 7px;
  background: var(--danger);
  border-radius: 50%;
}
.ticket-row strong,
.ticket-row small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ticket-row strong {
  color: var(--text-primary);
  font-size: var(--font-size-meta);
}
.ticket-row small {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.side-empty,
.loading-state {
  padding: 24px;
  color: var(--text-tertiary);
  text-align: center;
  font-size: var(--font-size-label);
}
.template-panel {
  margin-top: 14px;
}
.template-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.template-grid article {
  padding: 13px;
  background: var(--surface-subtle);
  border-radius: var(--radius-md);
}
.template-grid article > div {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.template-grid article > div span {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.template-grid strong {
  display: block;
  margin-top: 9px;
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.template-grid p {
  min-height: 44px;
  margin: 8px 0 2px;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  line-height: 1.6;
}
.drawer-review {
  padding: 12px;
  background: var(--danger-soft);
  border-radius: var(--radius-md);
}
.drawer-review > div {
  display: flex;
  align-items: center;
  gap: 9px;
}
.drawer-review strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.drawer-review p {
  margin: 10px 0 7px;
  color: var(--text-secondary);
  font-size: var(--font-size-label);
  line-height: 1.7;
}
.drawer-review small {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.drawer-form {
  display: grid;
  gap: 8px;
}
.drawer-form label {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  font-weight: 700;
}
.drawer-note {
  display: flex;
  gap: 7px;
  margin-top: 15px;
  padding: 10px;
  color: var(--warning-dark);
  background: var(--warning-soft);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-meta);
  line-height: 1.5;
}
.drawer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 22px;
}
@media (max-width: 1180px) {
  .review-summary {
    grid-template-columns: repeat(3, 1fr);
  }
  .review-grid {
    grid-template-columns: 1fr;
  }
  .review-side {
    grid-template-columns: 1fr 1fr;
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
  .review-toolbar {
    flex-wrap: wrap;
  }
  .toolbar-title {
    width: 100%;
  }
  .product-filter,
  .small-filter,
  .review-search {
    width: calc(50% - 6px);
  }
  .review-side,
  .template-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 520px) {
  .review-summary {
    grid-template-columns: repeat(2, 1fr);
  }
  .summary-card {
    padding: 13px;
  }
  .review-toolbar {
    padding: 12px;
  }
  .product-filter,
  .small-filter,
  .review-search {
    width: 100%;
  }
  .review-item__identity .muted {
    display: none;
  }
  .review-item__foot {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
