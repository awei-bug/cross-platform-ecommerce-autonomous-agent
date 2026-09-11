<script setup lang="ts">
import { Bell } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useQuery } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { computed } from 'vue'

import { workspaceApi } from '../../api'
import { useSessionStore } from '../../stores/session'

const session = useSessionStore()
const {
  data: alerts,
  isPending,
  isError,
} = useQuery({
  queryKey: ['workspace-alerts'],
  queryFn: () => workspaceApi.alerts(session.token as string),
  refetchInterval: 60_000,
  enabled: computed(() => Boolean(session.token)),
})

const unreadCount = computed(() => alerts.value?.filter((item) => !item.is_read).length ?? 0)
const severityLabel = { critical: '紧急', warning: '提醒', info: '通知' }
</script>

<template>
  <el-popover placement="bottom-end" :width="390" trigger="click" popper-class="alert-popover">
    <template #reference>
      <button class="alert-trigger" type="button" aria-label="消息告警">
        <el-icon :size="22"><Bell /></el-icon>
        <span v-if="unreadCount" class="alert-trigger__badge">{{ unreadCount }}</span>
      </button>
    </template>

    <div class="alert-panel">
      <div class="alert-panel__head">
        <div>
          <strong>消息与告警</strong>
          <span>{{ unreadCount }} 条未读</span>
        </div>
        <button type="button" @click="ElMessage.info('消息中心将在后续阶段接入')">
          进入消息中心
        </button>
      </div>
      <div v-if="isPending" class="alert-panel__state">正在加载告警…</div>

      <div v-else-if="isError" class="alert-panel__state alert-panel__state--error">
        告警加载失败，请稍后重试。
      </div>
      <div v-else class="alert-panel__list">
        <article
          v-for="item in alerts"
          :key="item.id"
          class="alert-item"
          :class="`alert-item--${item.severity}`"
        >
          <span class="alert-item__dot"></span>
          <div>
            <div class="alert-item__title">
              <span>{{ severityLabel[item.severity] }}</span>
              <strong>{{ item.title }}</strong>
              <time>{{ dayjs(item.created_at).format('HH:mm') }}</time>
            </div>
            <p>{{ item.description }}</p>
            <small>{{ item.shop_name }}</small>
          </div>
        </article>
      </div>
    </div>
  </el-popover>
</template>

<style scoped lang="scss">
.alert-trigger {
  position: relative;
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  color: var(--text-primary);
  background: #fff;
  border: 1px solid transparent;
  border-radius: 9px;
  cursor: pointer;
}
.alert-trigger:hover {
  color: var(--primary);
  background: var(--primary-soft);
}
.alert-trigger:focus-visible {
  outline: 3px solid rgb(36 116 245 / 18%);
  border-color: var(--primary);
}
.alert-trigger__badge {
  position: absolute;
  top: 3px;
  right: 2px;
  display: grid;
  min-width: 18px;
  height: 18px;
  padding-inline: 4px;
  place-items: center;
  color: #fff;
  background: var(--danger);
  border: 2px solid #fff;
  border-radius: 9px;
  font-size: 10px;
  font-weight: 700;
}
.alert-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 4px 12px;
  border-bottom: 1px solid var(--border-soft);
}
.alert-panel__head strong,
.alert-panel__head span {
  display: block;
}
.alert-panel__head strong {
  color: var(--text-primary);
  font-size: 16px;
}
.alert-panel__head span {
  margin-top: 3px;
  color: var(--text-tertiary);
  font-size: 12px;
}
.alert-panel__head button {
  color: var(--primary);
  background: transparent;
  border: 0;
  cursor: pointer;
}
.alert-panel__list {
  display: grid;
  gap: 4px;
  padding-top: 8px;
}
.alert-panel__state {
  padding: 28px;
  color: var(--text-secondary);
  text-align: center;
}
.alert-panel__state--error {
  color: var(--danger-dark);
}
.alert-item {
  display: grid;
  grid-template-columns: 10px 1fr;
  gap: 8px;
  padding: 12px 8px;
  border-radius: 8px;
}
.alert-item:hover {
  background: var(--surface-muted);
}
.alert-item__dot {
  width: 8px;
  height: 8px;
  margin-top: 5px;
  background: var(--info);
  border-radius: 50%;
}
.alert-item--critical .alert-item__dot {
  background: var(--danger);
}
.alert-item--warning .alert-item__dot {
  background: var(--warning);
}
.alert-item__title {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
}
.alert-item__title span {
  color: var(--text-tertiary);
  font-size: 11px;
}
.alert-item__title strong {
  color: var(--text-primary);
  font-size: 14px;
}
.alert-item__title time {
  color: var(--text-tertiary);
  font-size: 11px;
}
.alert-item p {
  margin: 5px 0;
  color: var(--text-secondary);
  line-height: 1.55;
  font-size: 13px;
}
.alert-item small {
  color: var(--text-tertiary);
}
</style>
