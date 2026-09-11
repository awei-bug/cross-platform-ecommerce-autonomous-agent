<script setup lang="ts">
import { ArrowRight, Check, Clock, Connection, WarningFilled } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useWorkspaceStore } from '../stores/workspace'

const workspace = useWorkspaceStore()
const router = useRouter()

const currency = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  maximumFractionDigits: 0,
})
const updatedAt = computed(() =>
  workspace.summary ? dayjs(workspace.summary.updated_at).format('YYYY年M月D日 HH:mm') : '正在同步',
)

const risks = [
  {
    level: 'critical',
    label: '紧急',
    title: '库存低于安全线',
    detail: '12 个 SKU 需要补货或调整投放',
    action: '进入商品中心',
    path: '/products',
  },
  {
    level: 'warning',
    label: '待处理',
    title: '售后即将超时',
    detail: '3 个退款申请剩余处理时间不足 2 小时',
    action: '查看订单售后',
    path: '/orders',
  },
  {
    level: 'normal',
    label: '常规',
    title: '本轮数据同步完成',
    detail: '商品、订单与活动数据已刷新',
    action: '查看同步状态',
    path: '/dashboard',
  },
]
</script>

<template>
  <div class="dashboard-foundation">
    <header class="page-heading">
      <div>
        <span class="page-heading__status">阶段 A · 基础骨架</span>
        <h1>运营总览</h1>
        <p>统一店铺上下文、权限、搜索、告警和 API 契约已经接入。</p>
      </div>
      <div class="page-heading__updated">
        <el-icon><Clock /></el-icon>
        <span
          >演示数据更新于<br /><strong>{{ updatedAt }}</strong></span
        >
      </div>
    </header>

    <section class="summary-strip" aria-label="经营摘要">
      <article>
        <span>今日销售额</span>
        <strong>{{
          workspace.summary ? currency.format(workspace.summary.today_sales) : '—'
        }}</strong>
        <small>下一阶段接入环比和趋势</small>
      </article>
      <article>
        <span>支付订单</span>
        <strong>{{ workspace.summary?.paid_orders.toLocaleString('zh-CN') ?? '—' }}</strong>
        <small>当前为统一数据契约</small>
      </article>
      <article class="summary-strip__risk">
        <span>活跃告警</span>
        <strong>{{ workspace.summary?.active_alerts ?? '—' }}</strong>
        <small>消息中心每 60 秒刷新</small>
      </article>
      <article>
        <span>待处理任务</span>
        <strong>{{ workspace.summary?.pending_tasks ?? '—' }}</strong>
        <small>批量任务状态将在阶段 B 接入</small>
      </article>
    </section>

    <section class="dashboard-grid">
      <article class="risk-queue surface-panel">
        <div class="section-heading">
          <div>
            <h2>风险处理队列</h2>
            <p>按风险等级、剩余时效和影响范围排序</p>
          </div>
          <span class="section-heading__count">3 条演示任务</span>
        </div>

        <div class="risk-list">
          <div
            v-for="risk in risks"
            :key="risk.title"
            class="risk-row"
            :class="`risk-row--${risk.level}`"
          >
            <span class="risk-row__indicator"></span>
            <span class="risk-row__label">{{ risk.label }}</span>
            <div class="risk-row__content">
              <strong>{{ risk.title }}</strong>
              <p>{{ risk.detail }}</p>
            </div>
            <button type="button" @click="router.push(risk.path)">
              {{ risk.action }} <el-icon><ArrowRight /></el-icon>
            </button>
          </div>
        </div>
      </article>

      <article class="capability-panel surface-panel">
        <div class="section-heading">
          <div>
            <h2>平台能力矩阵</h2>
            <p>动作能力跟随当前店铺授权变化</p>
          </div>
          <el-icon class="section-heading__icon"><Connection /></el-icon>
        </div>

        <div v-if="workspace.currentShopId === 'shop-all'" class="capability-empty">
          <el-icon :size="28"><WarningFilled /></el-icon>
          <strong>请选择单个店铺</strong>
          <p>全部店铺视角只聚合数据，不执行平台写操作。</p>
        </div>
        <div v-else class="capability-list">
          <div v-for="item in workspace.capabilities" :key="item.key" class="capability-row">
            <el-icon :class="`mode-${item.mode}`"><Check /></el-icon>
            <div>
              <strong>{{ item.label }}</strong
              ><small>{{ item.reason ?? '当前授权可用' }}</small>
            </div>
            <span :class="`mode-${item.mode}`">{{
              {
                direct: '直接执行',
                async: '异步任务',
                redirect: '平台跳转',
                unsupported: '未授权',
              }[item.mode]
            }}</span>
          </div>
        </div>
      </article>
    </section>

    <section class="foundation-track surface-panel">
      <div class="section-heading">
        <div>
          <h2>基础能力完成情况</h2>
          <p>先固定共用骨架，再进入商品中心和正式运营总览开发</p>
        </div>
        <span class="foundation-track__stage">下一步：阶段 B</span>
      </div>
      <div class="foundation-steps">
        <div class="foundation-step foundation-step--done">
          <span>01</span><strong>前后端工程</strong><small>Vue 3 / FastAPI</small>
        </div>
        <div class="foundation-step foundation-step--done">
          <span>02</span><strong>全局工作区</strong><small>组织 / 店铺 / 权限</small>
        </div>
        <div class="foundation-step foundation-step--done">
          <span>03</span><strong>契约与 Mock API</strong><small>OpenAPI / 演示数据</small>
        </div>
        <div class="foundation-step foundation-step--active">
          <span>04</span><strong>商品中心</strong><small>筛选 / 表格 / 批量任务</small>
        </div>
        <div class="foundation-step">
          <span>05</span><strong>运营总览</strong><small>指标 / 图表 / AI 上下文</small>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.dashboard-foundation {
  display: grid;
  gap: 18px;
}
.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 8px 4px 4px;
}
.page-heading__status {
  display: inline-block;
  margin-bottom: 9px;
  color: var(--primary);
  font-size: 12px;
  font-weight: 700;
}
.page-heading h1 {
  margin: 0;
  color: var(--text-primary);
  font-size: 32px;
  letter-spacing: -0.03em;
}
.page-heading p {
  margin: 8px 0 0;
  color: var(--text-secondary);
}
.page-heading__updated {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-tertiary);
  font-size: 12px;
  text-align: right;
}
.page-heading__updated strong {
  color: var(--text-secondary);
  font-weight: 600;
}
.summary-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.summary-strip article {
  position: relative;
  padding: 22px 24px;
}
.summary-strip article + article::before {
  position: absolute;
  inset: 20px auto 20px 0;
  width: 1px;
  content: '';
  background: var(--border-soft);
}
.summary-strip span,
.summary-strip strong,
.summary-strip small {
  display: block;
}
.summary-strip span {
  color: var(--text-secondary);
  font-size: 13px;
}
.summary-strip strong {
  margin: 7px 0 5px;
  color: var(--text-primary);
  font-size: 30px;
  letter-spacing: -0.035em;
}
.summary-strip small {
  color: var(--text-tertiary);
  font-size: 11px;
}
.summary-strip__risk strong {
  color: var(--danger);
}
.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(340px, 0.75fr);
  gap: 18px;
}
.surface-panel {
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.risk-queue,
.capability-panel,
.foundation-track {
  padding: 24px;
}
.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border-soft);
}
.section-heading h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 19px;
}
.section-heading p {
  margin: 6px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
}
.section-heading__count,
.foundation-track__stage {
  color: var(--primary);
  font-size: 12px;
  font-weight: 650;
}
.section-heading__icon {
  color: var(--primary);
  font-size: 22px;
}
.risk-list {
  display: grid;
}
.risk-row {
  display: grid;
  min-height: 82px;
  grid-template-columns: 8px 58px 1fr auto;
  align-items: center;
  gap: 14px;
  border-bottom: 1px solid var(--border-soft);
}
.risk-row:last-child {
  border-bottom: 0;
}
.risk-row__indicator {
  width: 8px;
  height: 8px;
  background: var(--success);
  border-radius: 50%;
}
.risk-row--critical .risk-row__indicator {
  background: var(--danger);
  box-shadow: 0 0 0 5px rgb(240 68 56 / 10%);
}
.risk-row--warning .risk-row__indicator {
  background: var(--warning);
}
.risk-row__label {
  color: var(--text-tertiary);
  font-size: 12px;
}
.risk-row__content strong {
  color: var(--text-primary);
  font-size: 14px;
}
.risk-row__content p {
  margin: 5px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}
.risk-row button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--primary);
  background: transparent;
  border: 0;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}
.capability-empty {
  display: grid;
  min-height: 220px;
  padding: 28px;
  place-items: center;
  align-content: center;
  color: var(--text-tertiary);
  text-align: center;
}
.capability-empty strong {
  margin-top: 12px;
  color: var(--text-primary);
}
.capability-empty p {
  max-width: 260px;
  margin: 8px 0 0;
  line-height: 1.6;
}
.capability-list {
  display: grid;
  padding-top: 8px;
}
.capability-row {
  display: grid;
  grid-template-columns: 26px 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 15px 0;
  border-bottom: 1px solid var(--border-soft);
}
.capability-row:last-child {
  border-bottom: 0;
}
.capability-row div strong,
.capability-row div small {
  display: block;
}
.capability-row div strong {
  color: var(--text-primary);
  font-size: 13px;
}
.capability-row div small {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 11px;
}
.capability-row > span {
  font-size: 11px;
  font-weight: 650;
}
.mode-direct {
  color: var(--success-dark);
}
.mode-async {
  color: var(--primary);
}
.mode-redirect {
  color: var(--warning-dark);
}
.mode-unsupported {
  color: var(--text-tertiary);
}
.foundation-steps {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  padding-top: 22px;
}
.foundation-step {
  position: relative;
  padding: 8px 20px 8px 0;
}
.foundation-step:not(:last-child)::after {
  position: absolute;
  top: 20px;
  right: 14px;
  left: 38px;
  height: 1px;
  content: '';
  background: var(--border);
}
.foundation-step span {
  position: relative;
  z-index: 1;
  display: grid;
  width: 28px;
  height: 28px;
  margin-bottom: 13px;
  place-items: center;
  color: var(--text-tertiary);
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 50%;
  font-size: 10px;
}
.foundation-step strong,
.foundation-step small {
  display: block;
}
.foundation-step strong {
  color: var(--text-secondary);
  font-size: 13px;
}
.foundation-step small {
  margin-top: 5px;
  color: var(--text-tertiary);
  font-size: 11px;
}
.foundation-step--done span {
  color: #fff;
  background: var(--success);
  border-color: var(--success);
}
.foundation-step--done strong {
  color: var(--text-primary);
}
.foundation-step--active span {
  color: #fff;
  background: var(--primary);
  border-color: var(--primary);
  box-shadow: 0 0 0 5px rgb(36 116 245 / 10%);
}
.foundation-step--active strong {
  color: var(--primary);
}
@media (max-width: 1180px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
  .summary-strip {
    grid-template-columns: repeat(2, 1fr);
  }
  .summary-strip article:nth-child(3)::before {
    display: none;
  }
  .summary-strip article:nth-child(n + 3) {
    border-top: 1px solid var(--border-soft);
  }
}
@media (max-width: 760px) {
  .page-heading {
    align-items: flex-start;
  }
  .page-heading__updated {
    display: none;
  }
  .summary-strip {
    grid-template-columns: 1fr 1fr;
  }
  .summary-strip article {
    padding: 18px;
  }
  .summary-strip strong {
    font-size: 24px;
  }
  .risk-row {
    grid-template-columns: 8px 1fr auto;
  }
  .risk-row__label {
    display: none;
  }
  .risk-row button {
    font-size: 0;
  }
  .risk-row button .el-icon {
    font-size: 16px;
  }
  .foundation-steps {
    grid-template-columns: 1fr;
    gap: 0;
  }
  .foundation-step {
    display: grid;
    grid-template-columns: 38px 1fr;
    padding-bottom: 16px;
  }
  .foundation-step span {
    grid-row: span 2;
  }
  .foundation-step:not(:last-child)::after {
    top: 37px;
    right: auto;
    bottom: 0;
    left: 14px;
    width: 1px;
    height: auto;
  }
}
</style>
