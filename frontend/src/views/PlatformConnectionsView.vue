<script setup lang="ts">
import {
  CircleClose,
  Connection,
  Delete,
  Download,
  InfoFilled,
  Refresh,
  SuccessFilled,
  WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Component } from 'vue'
import { computed, onMounted, ref } from 'vue'

import { integrationApi } from '../api'
import { ApiError } from '../api/http'
import { useSessionStore } from '../stores/session'
import type { ConnectorPlatform, ConnectorStatus, ProductSyncResponse } from '../types/api'
import {
  formatConnectorTime,
  getConnectorStateDisplay,
  isConnectorReady,
} from '../utils/integrations'

interface PlatformMeta {
  platform: ConnectorPlatform
  icon: Component
  hint: string
  accent: string
}

const PLATFORM_META: PlatformMeta[] = [
  {
    platform: 'douyin',
    icon: Connection,
    accent: 'douyin',
    hint: '抖店开放平台提供官方测试店铺，注册开发者即可拿到真实 token，无需自有店铺也能跑通 live 链路。',
  },
]

const session = useSessionStore()
const connectors = ref<ConnectorStatus[]>([])
const loading = ref(false)
const loadError = ref('')
const actingPlatform = ref<ConnectorPlatform | null>(null)
const syncResults = ref<Partial<Record<ConnectorPlatform, ProductSyncResponse>>>({})

// 目前仅抖店具备真实商品同步能力，其它平台的入口不展示，避免点了才报 404。
const SYNC_CAPABLE_PLATFORMS: ConnectorPlatform[] = ['douyin']

const readyCount = computed(
  () => connectors.value.filter((item) => isConnectorReady(item.state)).length,
)

const orderedCards = computed(() => {
  const byPlatform = new Map(connectors.value.map((item) => [item.platform, item]))
  return PLATFORM_META.map((meta) => ({ meta, status: byPlatform.get(meta.platform) ?? null }))
})

function findStatus(platform: ConnectorPlatform): ConnectorStatus | null {
  return connectors.value.find((item) => item.platform === platform) ?? null
}

async function load() {
  if (!session.token) return
  loading.value = true
  loadError.value = ''
  try {
    connectors.value = await integrationApi.connectors(session.token)
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '平台连接状态加载失败'
  } finally {
    loading.value = false
  }
}

async function refreshOne(platform: ConnectorPlatform) {
  if (!session.token) return
  actingPlatform.value = platform
  try {
    const status = await integrationApi.status(session.token, platform)
    connectors.value = connectors.value.map((item) => (item.platform === platform ? status : item))
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '状态刷新失败'
  } finally {
    actingPlatform.value = null
  }
}

async function authorize(platform: ConnectorPlatform) {
  if (!session.token) return
  actingPlatform.value = platform
  try {
    const result = await integrationApi.authorize(session.token, platform)
    if (result.authorization_url) {
      window.open(result.authorization_url, '_blank', 'noopener,noreferrer')
    }
    ElMessage.info('已打开平台授权页，完成授权后返回本页点击“刷新状态”')
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      ElMessage.warning({
        message: '服务端尚未配置该平台的应用凭证，请先在环境变量中补齐 Key / Secret',
        duration: 5000,
      })
    } else {
      ElMessage.error(error instanceof Error ? error.message : '发起授权失败')
    }
  } finally {
    actingPlatform.value = null
  }
}

async function disconnect(platform: ConnectorPlatform) {
  if (!session.token) return
  const status = findStatus(platform)
  try {
    await ElMessageBox.confirm(
      `确认解除「${status?.platform_label ?? platform}」的店铺授权？解绑后该平台的读写任务将回落到受限模式。`,
      '解除授权',
      { type: 'warning', confirmButtonText: '确认解除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  actingPlatform.value = platform
  try {
    await integrationApi.disconnect(session.token, platform)
    ElMessage.success('已解除授权，连接状态回到待授权')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '解除授权失败')
  } finally {
    actingPlatform.value = null
  }
}

function syncResultText(platform: ConnectorPlatform): string {
  const result = syncResults.value[platform]
  if (!result) return ''
  const parts = [
    `共拉取 ${result.total_fetched} 件`,
    `新增 ${result.created} / 更新 ${result.updated} / 无变化 ${result.unchanged}`,
    `数据源 ${result.data_source}`,
  ]
  if (result.warnings.length) parts.push(result.warnings[0])
  return parts.join('｜')
}

async function syncProducts(platform: ConnectorPlatform) {
  if (!session.token) return
  actingPlatform.value = platform
  try {
    const result = await integrationApi.syncProducts(session.token, platform)
    if (!result.is_live) {
      ElMessage.warning('本次未真实调用平台 API，数据仍是种子演示数据')
      return
    }
    syncResults.value = { ...syncResults.value, [platform]: result }
    ElMessage.success(
      `已同步真实商品：新增 ${result.created} / 更新 ${result.updated} / 无变化 ${result.unchanged}`,
    )
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      const detail = error instanceof ApiError ? error.message : ''
      ElMessage.warning({ message: detail || '同步前置条件不满足', duration: 6000 })
    } else {
      ElMessage.error(error instanceof Error ? error.message : '同步失败')
    }
  } finally {
    actingPlatform.value = null
  }
}

onMounted(load)
</script>

<template>
  <section class="connector-page">
    <header class="page-heading">
      <div>
        <div class="heading-kicker">
          <span class="kicker-icon"
            ><el-icon><Connection /></el-icon
          ></span>
          平台连接器
        </div>
        <h1>平台连接</h1>
        <p>
          统一查看抖店的授权状态。所有 token
          经服务端加密存储，前端只展示状态，不接触任何密钥。
        </p>
      </div>
      <div class="heading-actions">
        <el-tag type="info" effect="light" round>
          已连接 {{ readyCount }} / {{ PLATFORM_META.length }}
        </el-tag>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新状态</el-button>
      </div>
    </header>

    <el-alert
      v-if="loadError"
      class="connector-alert"
      type="error"
      show-icon
      :closable="false"
      :title="loadError"
    />

    <div v-if="loading && !connectors.length" class="connector-grid">
      <el-skeleton v-for="meta in PLATFORM_META" :key="meta.platform" animated :rows="4" />
    </div>

    <div v-else class="connector-grid">
      <article
        v-for="card in orderedCards"
        :key="card.meta.platform"
        class="connector-card"
        :class="`connector-card--${card.meta.accent}`"
      >
        <header class="connector-card__head">
          <span class="connector-card__icon">
            <el-icon :size="20"><component :is="card.meta.icon" /></el-icon>
          </span>
          <div class="connector-card__title">
            <strong>{{ card.status?.platform_label ?? card.meta.platform }}</strong>
            <small>{{ card.meta.hint }}</small>
          </div>
          <el-tag
            v-if="card.status"
            :type="getConnectorStateDisplay(card.status.state).tag"
            effect="light"
            size="small"
          >
            {{ getConnectorStateDisplay(card.status.state).label }}
          </el-tag>
        </header>

        <p v-if="card.status" class="connector-card__message">
          <el-icon>
            <component
              :is="
                isConnectorReady(card.status.state)
                  ? SuccessFilled
                  : card.status.state === 'error'
                    ? WarningFilled
                    : InfoFilled
              "
            />
          </el-icon>
          {{ card.status.message }}
        </p>

        <dl v-if="card.status" class="connector-card__meta">
          <div>
            <dt>授权店铺</dt>
            <dd>{{ card.status.platform_shop_name || '—' }}</dd>
          </div>
          <div>
            <dt>店铺 ID</dt>
            <dd>{{ card.status.platform_shop_id || '—' }}</dd>
          </div>
          <div>
            <dt>平台账号</dt>
            <dd>{{ card.status.platform_user_name || '—' }}</dd>
          </div>
          <div>
            <dt>令牌过期</dt>
            <dd>{{ formatConnectorTime(card.status.access_token_expires_at) }}</dd>
          </div>
          <div>
            <dt>授权时间</dt>
            <dd>{{ formatConnectorTime(card.status.authorized_at) }}</dd>
          </div>
          <div>
            <dt>只读范围</dt>
            <dd>{{ card.status.read_scopes.length ? card.status.read_scopes.join('、') : '—' }}</dd>
          </div>
        </dl>

        <el-alert
          v-if="card.status?.missing_secrets.length"
          class="connector-card__notice"
          type="info"
          show-icon
          :closable="false"
          title="缺失服务端配置"
          :description="card.status.missing_secrets.join('、')"
        />

        <el-alert
          v-if="card.status?.last_error"
          class="connector-card__notice"
          type="error"
          show-icon
          :closable="false"
          title="最近错误"
          :description="card.status.last_error"
        />

        <el-alert
          v-if="syncResults[card.meta.platform]"
          class="connector-card__sync"
          type="success"
          :closable="false"
          title="已从真实店铺同步商品"
          :description="syncResultText(card.meta.platform)"
        />

        <footer class="connector-card__actions">
          <el-button
            v-if="card.status && getConnectorStateDisplay(card.status.state).action !== 'none'"
            type="primary"
            :loading="actingPlatform === card.meta.platform"
            @click="authorize(card.meta.platform)"
          >
            {{
              getConnectorStateDisplay(card.status.state).action === 'reauthorize'
                ? '重新授权'
                : '发起授权'
            }}
          </el-button>
          <el-button v-else-if="card.status" disabled :icon="CircleClose">
            {{ isConnectorReady(card.status.state) ? '授权有效' : '暂不可授权' }}
          </el-button>

          <el-button
            v-if="
              card.status &&
              card.status.state !== 'revoked' &&
              card.status.state !== 'credentials_required'
            "
            :icon="Refresh"
            :loading="actingPlatform === card.meta.platform"
            @click="refreshOne(card.meta.platform)"
          >
            刷新
          </el-button>

          <el-button
            v-if="
              card.status &&
              isConnectorReady(card.status.state) &&
              SYNC_CAPABLE_PLATFORMS.includes(card.meta.platform)
            "
            :icon="Download"
            type="success"
            plain
            :loading="actingPlatform === card.meta.platform"
            @click="syncProducts(card.meta.platform)"
          >
            同步商品
          </el-button>

          <el-button
            v-if="card.status && isConnectorReady(card.status.state)"
            :icon="Delete"
            type="danger"
            plain
            :loading="actingPlatform === card.meta.platform"
            @click="disconnect(card.meta.platform)"
          >
            解除授权
          </el-button>
        </footer>
      </article>
    </div>

    <footer class="connector-page__footer">
      <el-icon><InfoFilled /></el-icon>
      <span>
        抖店连接器已完成 OAuth、签名、身份校验与真实商品同步/写入（改动 items 均走平台 API
        并落审计），可用官方测试店铺跑通 live 链路。
      </span>
    </footer>
  </section>
</template>

<style scoped lang="scss">
.connector-page {
  min-width: 0;
}
.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
}
.heading-kicker {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--success-dark);
  font-size: var(--font-size-label);
  font-weight: 700;
}
.kicker-icon {
  display: inline-grid;
  width: 20px;
  height: 20px;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 6px;
}
h1 {
  margin: 7px 0 6px;
  font-size: 30px;
  letter-spacing: -0.035em;
}
.page-heading p {
  max-width: 720px;
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-body);
  line-height: 1.6;
}
.heading-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.connector-alert {
  margin-bottom: 14px;
}
.connector-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 14px;
}
.connector-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-top: 3px solid var(--primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.connector-card--douyin {
  border-top-color: var(--navy-700);
}
.connector-card__head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.connector-card__icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 9px;
}
.connector-card__title {
  min-width: 0;
  flex: 1;
}
.connector-card__title strong {
  display: block;
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.connector-card__title small {
  display: block;
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  line-height: 1.5;
}
.connector-card__message {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  line-height: 1.5;
}
.connector-card__message .el-icon {
  margin-top: 3px;
}
.connector-card__meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
  margin: 0;
  padding: 12px;
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
}
.connector-card__meta dt {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.connector-card__meta dd {
  margin: 2px 0 0;
  color: var(--text-primary);
  font-size: var(--font-size-meta);
  font-weight: 600;
  word-break: break-all;
}
.connector-card__notice {
  --el-alert-padding: 8px 10px;
}
.connector-card__sync {
  margin-bottom: 12px;
}
.connector-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: auto;
}
.connector-page__footer {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 16px;
  padding: 12px 14px;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  line-height: 1.6;
  background: var(--surface-subtle);
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
}
.connector-page__footer .el-icon {
  margin-top: 4px;
  color: var(--primary);
}
@media (max-width: 620px) {
  .page-heading {
    flex-direction: column;
  }
  .connector-card__meta {
    grid-template-columns: 1fr;
  }
}
</style>
