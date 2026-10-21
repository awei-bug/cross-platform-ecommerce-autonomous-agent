<script setup lang="ts">
import { ArrowRight, Connection, Cpu, Setting } from '@element-plus/icons-vue'
import { useQuery } from '@tanstack/vue-query'
import { computed } from 'vue'

import { aiApi, integrationApi } from '../api'
import { ecomApi } from '../api/ecomops'
import { useSessionStore } from '../stores/session'
import { useWorkspaceStore } from '../stores/workspace'
import { getConnectorStateDisplay } from '../utils/integrations'

const session = useSessionStore()
const workspace = useWorkspaceStore()
const ai = useQuery({
  queryKey: ['settings', 'ai'],
  queryFn: () => aiApi.configurations(session.token!),
  enabled: computed(() => session.hasPermission('asset:read')),
})
const connections = useQuery({
  queryKey: ['settings', 'connections'],
  queryFn: () => integrationApi.connectors(session.token!),
  enabled: computed(() => session.hasPermission('integration:read')),
})
const policy = useQuery({
  queryKey: ['ecomops', 'overview'],
  queryFn: () => ecomApi.overview(session.token!),
  enabled: computed(() => session.hasPermission('automation:manage')),
})
const aiStatus = computed(() => {
  if (ai.isError.value) return '状态读取失败'
  if (ai.isPending.value) return '正在读取'
  const ready =
    ai.data.value?.items.filter(
      (item) => item.is_enabled && item.status === 'connected' && item.selected_model,
    ) ?? []
  const live = ready.filter((item) => !item.is_demo).length
  if (live) return `${live} 个正式配置已连接`
  return ready.length ? '仅演示模型可用' : '尚无已验证模型'
})
async function refresh() {
  await Promise.all([
    ...(session.hasPermission('asset:read') ? [ai.refetch()] : []),
    ...(session.hasPermission('integration:read') ? [connections.refetch()] : []),
    ...(session.hasPermission('automation:manage') ? [policy.refetch()] : []),
  ])
}
</script>

<template>
  <section class="settings-hub" aria-labelledby="settings-title">
    <header class="settings-heading">
      <div>
        <h1 id="settings-title">组织配置</h1>
        <p>{{ workspace.organization?.name ?? '当前组织' }} · 管理模型、平台连接和跨境业务权限。</p>
      </div>
      <el-button @click="refresh">刷新配置状态</el-button>
    </header>
    <div class="settings-list">
      <RouterLink
        v-if="session.hasPermission('asset:read')"
        to="/ai-settings"
        class="settings-row"
        aria-label="AI 模型配置"
      >
        <el-icon class="settings-icon"><Cpu /></el-icon>
        <span class="settings-copy"
          ><strong>AI 模型配置</strong><small>厂商连接、密钥、模型发现和默认模型</small
          ><span class="settings-status" :class="{ 'settings-status--error': ai.isError.value }">{{
            aiStatus
          }}</span></span
        >
        <el-icon><ArrowRight /></el-icon>
      </RouterLink>
      <RouterLink
        v-if="session.hasPermission('integration:read')"
        to="/integrations"
        class="settings-row"
        aria-label="平台连接"
      >
        <el-icon class="settings-icon"><Connection /></el-icon>
        <span class="settings-copy"
          ><strong>平台连接</strong><small>查看电商授权、连接有效期与数据同步</small
          ><span
            class="settings-status"
            :class="{ 'settings-status--error': connections.isError.value }"
            ><template v-if="connections.isError.value">状态读取失败</template
            ><template v-else-if="connections.isPending.value">正在读取</template
            ><template v-else-if="connections.data.value?.length"
              ><span v-for="item in connections.data.value" :key="item.platform"
                >{{ item.platform_label }}：{{ getConnectorStateDisplay(item.state).label }}
              </span></template
            ><template v-else>尚无平台连接</template></span
          ></span
        >
        <el-icon><ArrowRight /></el-icon>
      </RouterLink>
      <RouterLink
        v-if="session.hasPermission('automation:manage')"
        to="/ecomops?tab=policy"
        class="settings-row"
        aria-label="风控与授权"
      >
        <el-icon class="settings-icon"><Setting /></el-icon>
        <span class="settings-copy"
          ><strong>风控与授权</strong><small>备货金额、广告预算、退款阈值与合规规则</small
          ><span
            class="settings-status"
            :class="{ 'settings-status--error': policy.isError.value }"
            >{{
              policy.isError.value
                ? '状态读取失败'
                : policy.data.value
                  ? `当前规则 v${policy.data.value.configuration.version}`
                  : '正在读取'
            }}</span
          ></span
        >
        <el-icon><ArrowRight /></el-icon>
      </RouterLink>
    </div>
    <p class="settings-note">
      配置按组织隔离。平台授权与跨境业务接入状态分别验证，连接目录不代表业务已接通。
    </p>
  </section>
</template>

<style scoped lang="scss">
.settings-hub {
  max-width: 960px;
  min-width: 0;
}
.settings-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 24px;
}
h1 {
  margin: 0 0 8px;
  font-size: 26px;
}
p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}
.settings-list {
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
}
.settings-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px;
  color: var(--text-primary);
  text-decoration: none;
}
.settings-row + .settings-row {
  border-top: 1px solid var(--border-soft);
}
.settings-row:hover {
  background: var(--primary-softer);
}
.settings-row:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}
.settings-icon {
  color: var(--primary-active);
  font-size: 24px;
  flex-shrink: 0;
}
.settings-copy {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 6px;
}
.settings-copy small,
.settings-status {
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-secondary);
}
.settings-status {
  color: var(--primary-active);
}
.settings-status--error {
  color: var(--danger-dark);
}
.settings-note {
  margin-top: 20px;
  font-size: 14px;
}
@media (max-width: 640px) {
  .settings-heading {
    flex-direction: column;
    gap: 12px;
  }
  .settings-row {
    padding: 20px 16px;
  }
}
</style>
