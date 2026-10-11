<script setup lang="ts">
import { CircleCheckFilled, WarningFilled } from '@element-plus/icons-vue'

import type { OrderActionJob } from '../../types/api'

const props = defineProps<{ job: OrderActionJob }>()
defineEmits<{ close: []; retry: [] }>()

const stateLabels = {
  queued: '等待平台队列',
  running: '正在执行',
  succeeded: '全部成功',
  partial: '部分成功',
  failed: '执行失败',
}

const actionLabels = {
  remind_ship: '催促发货',
  approve_refund: '同意退款',
  reject_refund: '拒绝退款',
  send_reply: '发送回复',
  mark_follow_up: '标记跟进',
}
</script>

<template>
  <section class="action-job" aria-live="polite">
    <div class="action-job__heading">
      <div>
        <span>{{ actionLabels[props.job.action] }} · 可审计演示任务</span>
        <strong>{{ stateLabels[props.job.status] }}</strong>
      </div>
      <div>
        <el-button v-if="props.job.failed" type="primary" text @click="$emit('retry')">
          重试失败项
        </el-button>
        <el-button text @click="$emit('close')">收起</el-button>
      </div>
    </div>
    <el-progress
      :percentage="props.job.progress"
      :status="
        props.job.status === 'failed'
          ? 'exception'
          : props.job.progress === 100
            ? 'success'
            : undefined
      "
    />
    <p>共 {{ props.job.total }} 单，成功 {{ props.job.succeeded }}，失败 {{ props.job.failed }}</p>
    <ul v-if="props.job.results.length">
      <li v-for="result in props.job.results" :key="result.order_id">
        <el-icon :class="result.success ? 'success' : 'failure'">
          <CircleCheckFilled v-if="result.success" />
          <WarningFilled v-else />
        </el-icon>
        <strong>{{ result.order_no }}</strong>
        <span>{{ result.message }}</span>
      </li>
    </ul>
  </section>
</template>

<style scoped lang="scss">
.action-job {
  margin-bottom: 14px;
  padding: 14px 16px;
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.action-job__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
.action-job__heading span,
.action-job__heading strong {
  display: block;
}
.action-job__heading span {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.action-job__heading strong {
  margin-top: 3px;
}
.action-job p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-label);
}
.action-job ul {
  display: grid;
  gap: 7px;
  margin: 12px 0 0;
  padding: 10px 0 0;
  border-top: 1px solid var(--border-soft);
  list-style: none;
}
.action-job li {
  display: grid;
  grid-template-columns: 18px minmax(140px, 190px) 1fr;
  align-items: center;
  gap: 7px;
  font-size: var(--font-size-label);
}
.success {
  color: var(--success);
}
.failure {
  color: var(--danger);
}
@media (max-width: 680px) {
  .action-job__heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .action-job li {
    grid-template-columns: 18px 1fr;
  }
  .action-job li span {
    grid-column: 2;
  }
}
</style>
