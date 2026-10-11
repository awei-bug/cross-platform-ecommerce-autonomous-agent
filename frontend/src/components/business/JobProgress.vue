<script setup lang="ts">
import { CircleCheckFilled, WarningFilled } from '@element-plus/icons-vue'

import type { BatchJob } from '../../types/api'

defineProps<{ job: BatchJob }>()
defineEmits<{ close: []; retry: [] }>()

const labels = {
  queued: '等待执行',
  running: '执行中',
  succeeded: '全部成功',
  partial: '部分成功',
  failed: '执行失败',
}
</script>

<template>
  <section class="job-progress" aria-live="polite">
    <div class="job-progress__heading">
      <div>
        <span>批量任务 · 演示数据</span>
        <strong>{{ labels[job.status] }}</strong>
      </div>
      <div>
        <el-button v-if="job.failed" type="primary" text @click="$emit('retry')"
          >重试失败项</el-button
        ><el-button text @click="$emit('close')">收起</el-button>
      </div>
    </div>
    <el-progress
      :percentage="job.progress"
      :status="job.status === 'failed' ? 'exception' : job.progress === 100 ? 'success' : undefined"
    />
    <p>共 {{ job.total }} 项，成功 {{ job.succeeded }}，失败 {{ job.failed }}</p>
    <ul v-if="job.results.length">
      <li v-for="result in job.results" :key="result.product_id">
        <el-icon :class="result.success ? 'success' : 'failure'">
          <CircleCheckFilled v-if="result.success" /><WarningFilled v-else />
        </el-icon>
        <strong>{{ result.sku }}</strong
        ><span>{{ result.message }}</span>
      </li>
    </ul>
  </section>
</template>

<style scoped lang="scss">
.job-progress {
  margin-bottom: 14px;
  padding: 14px 16px;
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.job-progress__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.job-progress__heading span,
.job-progress__heading strong {
  display: block;
}
.job-progress__heading span {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.job-progress__heading strong {
  margin-top: 3px;
}
.job-progress p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-label);
}
.job-progress ul {
  display: grid;
  gap: 7px;
  margin: 12px 0 0;
  padding: 10px 0 0;
  border-top: 1px solid var(--border-soft);
  list-style: none;
}
.job-progress li {
  display: grid;
  grid-template-columns: 18px 100px 1fr;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-label);
}
.success {
  color: var(--success);
}
.failure {
  color: var(--danger);
}
</style>
