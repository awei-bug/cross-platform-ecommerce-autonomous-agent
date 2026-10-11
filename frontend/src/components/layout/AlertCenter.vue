<script setup lang="ts">
import { Bell, Check } from '@element-plus/icons-vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed } from 'vue'

import { workspaceApi } from '../../api'
import { useSessionStore } from '../../stores/session'
import type { AlertItem } from '../../types/api'

const session = useSessionStore()
const queryClient = useQueryClient()
const queryKey = ['workspace-alerts'] as const
const {
  data: alerts,
  isPending,
  isError,
  refetch,
} = useQuery({
  queryKey,
  queryFn: () => workspaceApi.alerts(session.token as string),
  refetchInterval: 60_000,
  enabled: computed(() => Boolean(session.token)),
})

const markMutation = useMutation({
  mutationFn: ({ id, isRead }: { id: string; isRead: boolean }) =>
    workspaceApi.setAlertRead(session.token as string, id, isRead),
  onSuccess: (updated) => {
    queryClient.setQueryData<AlertItem[]>(queryKey, (current = []) =>
      current.map((item) => (item.id === updated.id ? updated : item)),
    )
  },
  onError: () => ElMessage.error('告警状态保存失败，请重试'),
})

const readAllMutation = useMutation({
  mutationFn: () => workspaceApi.readAllAlerts(session.token as string),
  onSuccess: ({ changed }) => {
    queryClient.setQueryData<AlertItem[]>(queryKey, (current = []) =>
      current.map((item) => ({ ...item, is_read: true })),
    )
    ElMessage.success(changed ? `已将 ${changed} 条告警标为已读` : '当前没有未读告警')
  },
  onError: () => ElMessage.error('批量已读保存失败，请重试'),
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
          <span>{{ unreadCount }} 条未读 · 状态已持久化</span>
        </div>
        <button
          type="button"
          :disabled="!unreadCount || readAllMutation.isPending.value"
          @click="readAllMutation.mutate()"
        >
          <el-icon><Check /></el-icon>
          {{ readAllMutation.isPending.value ? '保存中' : '全部已读' }}
        </button>
      </div>
      <div v-if="isPending" class="alert-panel__state">正在加载告警…</div>

      <div v-else-if="isError" class="alert-panel__state alert-panel__state--error">
        <p>告警加载失败，当前网络或服务暂不可用。</p>
        <button type="button" @click="refetch()">重新加载</button>
      </div>
      <div v-else-if="!alerts?.length" class="alert-panel__state">当前没有消息或风险告警。</div>
      <div v-else class="alert-panel__list">
        <article
          v-for="item in alerts"
          :key="item.id"
          class="alert-item"
          :class="[`alert-item--${item.severity}`, { 'alert-item--read': item.is_read }]"
        >
          <span class="alert-item__dot"></span>
          <div class="alert-item__body">
            <div class="alert-item__title">
              <span>{{ severityLabel[item.severity] }}</span>
              <strong>{{ item.title }}</strong>
              <time>{{ dayjs(item.created_at).format('HH:mm') }}</time>
            </div>
            <p>{{ item.description }}</p>
            <div class="alert-item__foot">
              <small>{{ item.shop_name }}</small>
              <button
                type="button"
                :disabled="markMutation.isPending.value"
                :aria-label="item.is_read ? `将${item.title}标为未读` : `将${item.title}标为已读`"
                @click="markMutation.mutate({ id: item.id, isRead: !item.is_read })"
              >
                {{ item.is_read ? '标为未读' : '标为已读' }}
              </button>
            </div>
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
.alert-trigger:focus-visible,
.alert-panel button:focus-visible {
  outline: 3px solid rgb(36 116 245 / 18%);
  outline-offset: 2px;
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
  font-size: var(--font-size-caption);
  font-weight: 700;
}
.alert-panel__head {
  display: flex;
  gap: 16px;
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
  font-size: var(--font-size-subtitle);
}
.alert-panel__head span {
  margin-top: 3px;
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
}
.alert-panel__head button,
.alert-item__foot button,
.alert-panel__state button {
  display: inline-flex;
  flex: none;
  gap: 4px;
  align-items: center;
  color: var(--primary);
  background: transparent;
  border: 0;
  cursor: pointer;
}
.alert-panel button:disabled {
  color: var(--text-tertiary);
  cursor: not-allowed;
}
.alert-panel__list {
  display: grid;
  gap: 4px;
  max-height: min(520px, 70vh);
  padding-top: 8px;
  overflow-y: auto;
}
.alert-panel__state {
  padding: 28px;
  color: var(--text-secondary);
  text-align: center;
}
.alert-panel__state p {
  margin: 0 0 10px;
}
.alert-panel__state--error {
  color: var(--danger-dark);
}
.alert-item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  gap: 8px;
  padding: 12px 8px;
  border-radius: 8px;
}
.alert-item:hover {
  background: var(--surface-muted);
}
.alert-item--read {
  opacity: 0.68;
}
.alert-item__dot {
  width: 8px;
  height: 8px;
  margin-top: 5px;
  background: var(--info);
  border-radius: 50%;
}
.alert-item--read .alert-item__dot {
  background: var(--text-tertiary);
}
.alert-item--critical .alert-item__dot {
  background: var(--danger);
}
.alert-item--warning .alert-item__dot {
  background: var(--warning);
}
.alert-item__body {
  min-width: 0;
}
.alert-item__title {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.alert-item__title span,
.alert-item__title time {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.alert-item__title strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-body);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.alert-item p {
  margin: 5px 0;
  overflow-wrap: anywhere;
  color: var(--text-secondary);
  line-height: 1.55;
  font-size: var(--font-size-body);
}
.alert-item__foot {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}
.alert-item small {
  min-width: 0;
  overflow: hidden;
  color: var(--text-tertiary);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.alert-item__foot button {
  font-size: var(--font-size-label);
}
</style>
