<script setup lang="ts">
import { Close, Refresh, Upload } from '@element-plus/icons-vue'

import type { BatchAction } from '../../types/api'

defineProps<{ count: number; disabledActions?: BatchAction[] }>()
const emit = defineEmits<{ action: [action: BatchAction]; clear: [] }>()

function disabled(action: BatchAction, values: BatchAction[] | undefined) {
  return values?.includes(action) ?? false
}
</script>

<template>
  <aside class="batch-bar" aria-live="polite">
    <div>
      <strong>已选择 {{ count }} 个商品</strong>
      <span>操作将创建演示任务，并保留结果与失败原因。</span>
    </div>
    <div class="batch-bar__actions">
      <el-button
        :icon="Upload"
        :disabled="disabled('publish', disabledActions)"
        @click="emit('action', 'publish')"
        >上架</el-button
      >
      <el-button
        :disabled="disabled('unpublish', disabledActions)"
        @click="emit('action', 'unpublish')"
        >下架</el-button
      >
      <el-button
        :disabled="disabled('update_price', disabledActions)"
        @click="emit('action', 'update_price')"
        >改价</el-button
      >
      <el-button type="primary" :icon="Refresh" @click="emit('action', 'sync')">同步</el-button>
      <el-button text :icon="Close" aria-label="清空选择" @click="emit('clear')" />
    </div>
  </aside>
</template>

<style scoped lang="scss">
.batch-bar {
  position: sticky;
  z-index: 8;
  bottom: 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin: 14px auto 0;
  padding: 13px 16px;
  color: #fff;
  background: var(--nav-bg-deep);
  border: 1px solid rgb(255 255 255 / 10%);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
}
.batch-bar strong,
.batch-bar span {
  display: block;
}
.batch-bar strong {
  font-size: var(--font-size-body);
}
.batch-bar span {
  margin-top: 3px;
  color: var(--sidebar-text-muted);
  font-size: var(--font-size-meta);
}
.batch-bar__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
@media (max-width: 900px) {
  .batch-bar {
    align-items: stretch;
    flex-direction: column;
  }
  .batch-bar__actions {
    overflow-x: auto;
  }
}
</style>
