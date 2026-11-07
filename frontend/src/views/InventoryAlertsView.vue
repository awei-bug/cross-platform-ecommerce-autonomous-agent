<script setup lang="ts">
import { Refresh, WarningFilled } from '@element-plus/icons-vue'
import { useQuery } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { computed, ref } from 'vue'

import { inventoryApi } from '../api'
import { useSessionStore } from '../stores/session'

const session = useSessionStore()
const threshold = ref(25)

const alertsQuery = useQuery({
  queryKey: computed(() => ['inventory-alerts', session.token, threshold.value]),
  queryFn: () => inventoryApi.alerts(session.token!, threshold.value),
  enabled: computed(() => Boolean(session.token)),
})

const alerts = computed(() => alertsQuery.data.value?.items ?? [])
const totalProjections = computed(() => alertsQuery.data.value?.total_projections ?? 0)

function refresh() {
  void alertsQuery.refetch()
}

function formatTime(value: string) {
  return dayjs(value).format('YYYY-MM-DD HH:mm:ss')
}
</script>

<template>
  <section class="inventory-page">
    <header class="inventory-page__head">
      <div>
        <h1>库存预警</h1>
        <p>
          数据来自云购 <code>stock.changed</code> 事件，由后台消费器投影到本地读模型。
          每条预警都能回溯到云购的具体事件，页面不生成也不补任何演示数据。
        </p>
      </div>
      <div class="inventory-page__actions">
        <el-input-number v-model="threshold" :min="0" :max="10000" :step="5" size="small" />
        <el-button :icon="Refresh" size="small" :loading="alertsQuery.isFetching.value" @click="refresh">
          刷新
        </el-button>
      </div>
    </header>

    <el-alert
      v-if="alertsQuery.isError.value"
      type="error"
      :closable="false"
      show-icon
      title="库存预警加载失败"
      :description="(alertsQuery.error.value as Error)?.message ?? '请稍后重试'"
    />

    <div class="inventory-page__summary">
      <span>阈值：库存低于 {{ threshold }} 件</span>
      <span>已投影事件：{{ totalProjections }} 条</span>
      <span>命中预警：{{ alerts.length }} 个商品</span>
    </div>

    <el-table
      v-loading="alertsQuery.isLoading.value"
      :data="alerts"
      size="small"
      empty-text="暂无低库存商品。在云购下单扣减库存后，这里会自动出现记录。"
    >
      <el-table-column prop="item_title" label="商品" min-width="180" />
      <el-table-column prop="product_id" label="云购商品 ID" width="120" />
      <el-table-column label="当前库存" width="110">
        <template #default="{ row }">
          <span :class="['inventory-page__stock', row.stock_after <= 0 ? 'is-out' : '']">
            <el-icon><WarningFilled /></el-icon>
            {{ row.stock_after }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="delta" label="本次变动" width="100" />
      <el-table-column prop="organization_id" label="所属组织" min-width="150" />
      <el-table-column label="来源" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="row.source === 'event' ? 'success' : 'info'">
            {{ row.source === 'event' ? '云购事件' : row.source }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="事件时间" width="170">
        <template #default="{ row }">{{ formatTime(row.occurred_at) }}</template>
      </el-table-column>
    </el-table>
  </section>
</template>

<style scoped>
.inventory-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.inventory-page__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.inventory-page__head h1 {
  margin: 0 0 6px;
  font-size: 20px;
}

.inventory-page__head p {
  margin: 0;
  max-width: 720px;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.inventory-page__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.inventory-page__summary {
  display: flex;
  gap: 24px;
  padding: 10px 14px;
  border-radius: 8px;
  background: var(--surface-subtle, #f7f7f5);
  color: var(--text-muted);
  font-size: 13px;
}

.inventory-page__stock {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
}

.inventory-page__stock.is-out {
  color: #c45656;
}
</style>
