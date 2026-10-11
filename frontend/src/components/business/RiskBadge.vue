<script setup lang="ts">
import { CircleCheckFilled, WarningFilled } from '@element-plus/icons-vue'

import type { ProductRisk } from '../../types/api'

const props = defineProps<{ risk: ProductRisk; compact?: boolean }>()

const labels: Record<ProductRisk, string> = {
  critical: '紧急风险',
  warning: '待处理',
  normal: '正常',
}
</script>

<template>
  <span class="risk-badge" :class="[`risk-badge--${props.risk}`, { 'is-compact': compact }]">
    <el-icon><CircleCheckFilled v-if="props.risk === 'normal'" /><WarningFilled v-else /></el-icon>
    {{ labels[props.risk] }}
  </span>
</template>

<style scoped lang="scss">
.risk-badge {
  display: inline-flex;
  min-width: 76px;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 5px 8px;
  border-radius: 6px;
  font-size: var(--font-size-label);
  font-weight: 700;
  white-space: nowrap;
}
.risk-badge.is-compact {
  min-width: auto;
  padding: 4px 6px;
}
.risk-badge--critical {
  color: var(--danger-dark);
  background: var(--danger-soft);
}
.risk-badge--warning {
  color: var(--warning-dark);
  background: var(--warning-soft);
}
.risk-badge--normal {
  color: var(--success-dark);
  background: var(--success-soft);
}
</style>
