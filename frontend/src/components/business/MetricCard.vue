<script setup lang="ts">
import { InfoFilled } from '@element-plus/icons-vue'
import { computed } from 'vue'

import type { DashboardMetric } from '../../types/api'

const props = defineProps<{ metric: DashboardMetric }>()

const formattedValue = computed(() => {
  if (props.metric.unit === 'currency') {
    return new Intl.NumberFormat('zh-CN', {
      style: 'currency',
      currency: 'CNY',
      maximumFractionDigits: 0,
    }).format(props.metric.value)
  }
  if (props.metric.unit === 'percent') return `${props.metric.value.toFixed(1)}%`
  return Math.round(props.metric.value).toLocaleString('zh-CN')
})
</script>

<template>
  <article class="metric-card">
    <div class="metric-card__label">
      <span>{{ metric.label }}</span>
      <el-tooltip :content="metric.definition" placement="top">
        <el-icon aria-label="查看指标定义"><InfoFilled /></el-icon>
      </el-tooltip>
    </div>
    <strong>{{ formattedValue }}</strong>
    <p :class="{ negative: metric.comparison < 0 }">
      <b>{{ metric.comparison > 0 ? '+' : '' }}{{ metric.comparison }}%</b>
      {{ metric.comparison_label }}
    </p>
  </article>
</template>

<style scoped lang="scss">
.metric-card {
  min-width: 0;
  padding: 18px 20px;
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.metric-card__label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--text-secondary);
  font-size: var(--font-size-body);
}
.metric-card__label .el-icon {
  color: var(--text-tertiary);
  cursor: help;
}
.metric-card strong {
  display: block;
  margin-top: 12px;
  font-size: clamp(24px, 2vw, 32px);
  letter-spacing: -0.04em;
}
.metric-card p {
  margin: 8px 0 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
}
.metric-card p b {
  margin-right: 5px;
  color: var(--success-dark);
}
.metric-card p.negative b {
  color: var(--danger-dark);
}
</style>
