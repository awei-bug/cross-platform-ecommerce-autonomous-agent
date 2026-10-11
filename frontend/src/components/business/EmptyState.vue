<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'

defineProps<{ title: string; description: string; actionLabel?: string }>()
defineEmits<{ action: [] }>()
</script>

<template>
  <div class="empty-state">
    <el-icon :size="30"><Search /></el-icon>
    <strong>{{ title }}</strong>
    <p>{{ description }}</p>
    <el-button v-if="actionLabel" @click="$emit('action')">{{ actionLabel }}</el-button>
  </div>
</template>

<style scoped lang="scss">
.empty-state {
  display: grid;
  min-height: 260px;
  place-items: center;
  align-content: center;
  gap: 8px;
  padding: 32px;
  color: var(--text-tertiary);
  text-align: center;
}
.empty-state strong {
  color: var(--text-primary);
  font-size: var(--font-size-subtitle);
}
.empty-state p {
  max-width: 420px;
  margin: 0 0 8px;
  line-height: 1.6;
}
</style>
