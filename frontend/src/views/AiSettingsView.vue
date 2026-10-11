<script setup lang="ts">
import {
  ArrowLeft,
  Check,
  Connection,
  Delete,
  Key,
  Refresh,
  Setting,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { aiApi } from '../api'
import { useSessionStore } from '../stores/session'
import type { AiConfiguration, AiModelProbeResponse, AiProviderCatalogItem } from '../types/api'

const router = useRouter()
const session = useSessionStore()
const providers = ref<AiProviderCatalogItem[]>([])
const configurations = ref<AiConfiguration[]>([])
const selectedProviderId = ref('')
const displayName = ref('')
const baseUrl = ref('')
const apiKey = ref('')
const selectedModel = ref('')
const saving = ref(false)
const testingId = ref<string | null>(null)
const editingId = ref<string | null>(null)
const showAllModels = ref(false)
const probingId = ref<string | null>(null)
const probeResults = ref<Record<string, AiModelProbeResponse>>({})

const selectedProvider = computed(
  () => providers.value.find((provider) => provider.id === selectedProviderId.value) ?? null,
)
const editingConfiguration = computed(
  () => configurations.value.find((item) => item.id === editingId.value) ?? null,
)
const canSubmit = computed(() =>
  Boolean(
    selectedProvider.value &&
    baseUrl.value.trim() &&
    (apiKey.value.trim() ||
      editingConfiguration.value?.api_key_masked ||
      !selectedProvider.value.requires_api_key),
  ),
)

function chooseProvider(provider: AiProviderCatalogItem) {
  selectedProviderId.value = provider.id
  baseUrl.value = provider.default_base_url
  displayName.value = provider.name
  apiKey.value = ''
  selectedModel.value = ''
  editingId.value = null
}

function editConfiguration(config: AiConfiguration) {
  const provider = providers.value.find((item) => item.id === config.provider_id)
  editingId.value = config.id
  selectedProviderId.value = config.provider_id
  displayName.value = config.display_name
  baseUrl.value = config.base_url
  apiKey.value = ''
  selectedModel.value = config.selected_model ?? ''
  if (provider) baseUrl.value = config.base_url || provider.default_base_url
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function resetForm() {
  editingId.value = null
  selectedProviderId.value = ''
  displayName.value = ''
  baseUrl.value = ''
  apiKey.value = ''
  selectedModel.value = ''
}

async function load() {
  if (!session.token) return
  try {
    ;[providers.value, configurations.value] = await Promise.all([
      aiApi.providers(session.token),
      aiApi.configurations(session.token),
    ]).then(([providerResult, configResult]) => [providerResult, configResult.items])
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : 'AI 配置加载失败')
  }
}

async function save() {
  if (!session.token || !selectedProvider.value || !canSubmit.value) return
  saving.value = true
  try {
    if (editingId.value) {
      const updated = await aiApi.updateConfiguration(session.token, editingId.value, {
        display_name: displayName.value.trim(),
        base_url: baseUrl.value.trim(),
        ...(apiKey.value.trim() ? { api_key: apiKey.value.trim() } : {}),
        ...(selectedModel.value ? { selected_model: selectedModel.value } : {}),
      })
      configurations.value = configurations.value.map((item) =>
        item.id === updated.id ? updated : item,
      )
      ElMessage.success('配置已更新；请重新测试连接以刷新模型列表')
    } else {
      const created = await aiApi.createConfiguration(session.token, {
        provider_id: selectedProvider.value.id,
        display_name: displayName.value.trim(),
        base_url: baseUrl.value.trim(),
        ...(apiKey.value.trim() ? { api_key: apiKey.value.trim() } : {}),
      })
      configurations.value.push(created)
      editingId.value = created.id
      ElMessage.success('配置已保存，请点击“测试连接并拉取模型”')
    }
    apiKey.value = ''
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '配置保存失败')
  } finally {
    saving.value = false
  }
}

async function testConnection(config: AiConfiguration) {
  if (!session.token) return
  testingId.value = config.id
  try {
    const result = await aiApi.testConfiguration(session.token, config.id)
    configurations.value = configurations.value.map((item) =>
      item.id === config.id ? result.configuration : item,
    )
    if (result.configuration.selected_model)
      selectedModel.value = result.configuration.selected_model
    ElMessage.success(result.message)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '连接测试失败')
    await load()
  } finally {
    testingId.value = null
  }
}

async function probeModel(config: AiConfiguration) {
  if (!session.token || !config.selected_model) return
  probingId.value = config.id
  try {
    const result = await aiApi.probeModel(session.token, config.id, config.selected_model)
    probeResults.value[config.id] = result
    if (result.status === 'ok') ElMessage.success(result.message)
    else ElMessage.info(result.message)
  } catch (error) {
    probeResults.value[config.id] = {
      status: 'error',
      model_id: config.selected_model,
      message: error instanceof Error ? error.message : '模型验证失败',
      is_demo: config.is_demo,
    }
    ElMessage.error(error instanceof Error ? error.message : '模型验证失败')
  } finally {
    probingId.value = null
  }
}

async function removeConfiguration(config: AiConfiguration) {
  if (!session.token) return
  try {
    await ElMessageBox.confirm(
      `确认删除“${config.display_name}”配置？删除后不会影响线上平台数据。`,
      '删除 AI 配置',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await aiApi.deleteConfiguration(session.token, config.id)
    configurations.value = configurations.value.filter((item) => item.id !== config.id)
    if (editingId.value === config.id) resetForm()
    ElMessage.success('配置已删除')
  } catch {
    /* 用户取消 */
  }
}

function hasPricing(config: AiConfiguration) {
  return config.models.some((model) => model.is_free !== null && model.is_free !== undefined)
}
function freeCount(config: AiConfiguration) {
  return config.models.filter((model) => model.is_free === true).length
}
function visibleModels(config: AiConfiguration) {
  if (showAllModels.value || !hasPricing(config)) return config.models
  return config.models.filter((model) => model.is_free === true)
}

function chooseDefaultModel(config: AiConfiguration, modelId: string) {
  if (!session.token) return
  aiApi
    .updateConfiguration(session.token, config.id, { selected_model: modelId })
    .then((updated) => {
      configurations.value = configurations.value.map((item) =>
        item.id === updated.id ? updated : item,
      )
      ElMessage.success('默认模型已保存')
    })
    .catch((error) => ElMessage.error(error instanceof Error ? error.message : '默认模型保存失败'))
}

onMounted(load)
</script>

<template>
  <section class="settings-page">
    <header class="page-heading">
      <div>
        <button class="back-link" type="button" @click="router.push('/assets')">
          <el-icon><ArrowLeft /></el-icon>返回素材 AI
        </button>
        <div class="heading-kicker">
          <span class="kicker-icon"
            ><el-icon><Setting /></el-icon></span
          >服务端安全配置
        </div>
        <h1>AI 模型配置</h1>
        <p>
          选择厂商后自动填充请求地址，API Key
          只提交到服务端加密保存；测试连接成功后自动拉取可用模型。
        </p>
      </div>
      <el-tag type="warning" effect="light">密钥不回显 · 不写入日志</el-tag>
    </header>

    <div class="settings-grid">
      <main class="config-editor">
        <div class="panel-title">
          <div>
            <span class="section-label">1 · 选择厂商</span>
            <h2>{{ editingId ? '编辑已有配置' : '新增模型服务' }}</h2>
          </div>
          <el-button v-if="editingId" size="small" text @click="resetForm">取消编辑</el-button>
        </div>
        <div class="provider-grid">
          <button
            v-for="provider in providers"
            :key="provider.id"
            type="button"
            class="provider-card"
            :class="{ 'provider-card--active': selectedProviderId === provider.id }"
            @click="chooseProvider(provider)"
          >
            <span class="provider-mark">{{ provider.name.slice(0, 1) }}</span
            ><span
              ><strong>{{ provider.name }}</strong
              ><small
                >{{ provider.protocol }} · {{ provider.capabilities.join(' / ') }}</small
              ></span
            ><el-icon v-if="selectedProviderId === provider.id" class="provider-check"
              ><Check
            /></el-icon>
          </button>
        </div>
        <div v-if="selectedProvider" class="selected-provider-note">
          <span class="note-icon"
            ><el-icon><Connection /></el-icon
          ></span>
          <div>
            <strong>{{ selectedProvider.name }}</strong>
            <p>{{ selectedProvider.description }}</p>
          </div>
          <el-tag size="small" effect="plain">{{
            selectedProvider.requires_api_key ? '需要 API Key' : '无需 API Key'
          }}</el-tag>
        </div>

        <div class="form-section">
          <span class="section-label">2 · 填写连接信息</span>
          <div class="form-grid">
            <div class="form-field form-field--wide">
              <label for="display-name">配置名称</label
              ><el-input id="display-name" v-model="displayName" placeholder="例如：生产文案模型" />
            </div>
            <div class="form-field form-field--wide">
              <label for="base-url">请求地址 Base URL <span>可修改</span></label
              ><el-input id="base-url" v-model="baseUrl" placeholder="选择厂商后自动填入" />
            </div>
            <div class="form-field form-field--wide">
              <label for="api-key">API Key <span>仅本次提交，不会回显</span></label
              ><el-input
                id="api-key"
                v-model="apiKey"
                type="password"
                show-password
                autocomplete="off"
                :placeholder="
                  editingConfiguration?.api_key_masked
                    ? `已保存 ${editingConfiguration.api_key_masked}，留空表示不修改`
                    : selectedProvider?.requires_api_key
                      ? '粘贴厂商 API Key'
                      : '该厂商无需 Key'
                "
                :disabled="selectedProvider ? !selectedProvider.requires_api_key : false"
              />
            </div>
          </div>
          <div class="security-note">
            <el-icon><Key /></el-icon
            ><span
              >密钥由服务端使用 Fernet 加密保存，接口只返回掩码；浏览器不会直接请求厂商 API。</span
            >
          </div>
        </div>
        <div class="form-actions">
          <el-button type="primary" :loading="saving" :disabled="!canSubmit" @click="save">{{
            editingId ? '保存修改' : '保存配置'
          }}</el-button
          ><el-button @click="resetForm">清空</el-button
          ><small>保存后再测试，系统才会拉取该账号实际可用的模型。</small>
        </div>
      </main>

      <aside class="configuration-list">
        <div class="panel-title">
          <div>
            <span class="section-label">3 · 连接状态</span>
            <h2>已配置服务</h2>
          </div>
          <el-button :icon="Refresh" circle text @click="load" />
        </div>
        <div v-if="configurations.length" class="config-items">
          <article v-for="config in configurations" :key="config.id" class="config-item">
            <div class="config-item__top">
              <div>
                <strong>{{ config.display_name }}</strong
                ><span>{{ config.provider_name }} · {{ config.base_url }}</span>
              </div>
              <el-tag
                :type="
                  config.status === 'connected'
                    ? 'success'
                    : config.status === 'error'
                      ? 'danger'
                      : 'info'
                "
                size="small"
                >{{
                  config.status === 'connected'
                    ? '已连接'
                    : config.status === 'error'
                      ? '连接失败'
                      : '未测试'
                }}</el-tag
              >
            </div>
            <div class="config-key">
              <el-icon><Key /></el-icon>{{ config.api_key_masked ?? '无需 API Key'
              }}<span v-if="config.last_tested_at"
                >最近测试
                {{
                  new Date(config.last_tested_at).toLocaleString('zh-CN', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })
                }}</span
              >
            </div>
            <div v-if="config.last_error" class="config-error">{{ config.last_error }}</div>
            <div v-if="config.models.length" class="model-list">
              <div class="model-list__head">
                <strong>已发现模型 · {{ config.models.length }}</strong
                ><el-checkbox v-model="showAllModels" size="small">显示全部（含付费）</el-checkbox>
              </div>
              <el-select
                :model-value="config.selected_model ?? ''"
                class="model-select"
                filterable
                placeholder="选择默认模型"
                @change="(value: string) => chooseDefaultModel(config, value)"
                ><el-option
                  v-for="model in visibleModels(config)"
                  :key="model.id"
                  :label="model.display_name"
                  :value="model.model_id"
                  ><span class="model-option"
                    ><strong>{{ model.display_name }}</strong
                    ><el-tag v-if="model.is_free" size="small" type="success" effect="plain"
                      >免费</el-tag
                    ><small
                      >{{ model.model_id }} · {{ model.capabilities.join(' / ') }}</small
                    ></span
                  ></el-option
                ></el-select
              >
              <div class="probe-row">
                <el-button
                  size="small"
                  plain
                  :loading="probingId === config.id"
                  :disabled="!config.selected_model"
                  @click="probeModel(config)"
                  >验证模型可用</el-button
                ><small>向该模型发一次最小真实请求，确认可正常返回内容</small>
              </div>
              <div
                v-if="probeResults[config.id]"
                class="probe-result"
                :class="`probe-result--${probeResults[config.id].status}`"
              >
                <strong>{{
                  probeResults[config.id].status === 'ok'
                    ? '模型可用'
                    : probeResults[config.id].status === 'skipped'
                      ? '无需验证'
                      : '验证失败'
                }}</strong>
                <p>{{ probeResults[config.id].message }}</p>
                <code v-if="probeResults[config.id].preview"
                  >模型回复：{{ probeResults[config.id].preview }}</code
                >
              </div>
              <small v-if="hasPricing(config)" class="model-hint"
                >默认只列出 {{ freeCount(config) }} 个免费模型，勾选后可查看全部
                {{ config.models.length }} 个。</small
              >
            </div>
            <div class="config-item__actions">
              <el-button
                type="primary"
                plain
                size="small"
                :loading="testingId === config.id"
                :icon="Connection"
                @click="testConnection(config)"
                >测试连接并拉取模型</el-button
              ><el-button size="small" text @click="editConfiguration(config)">编辑</el-button
              ><el-button
                size="small"
                text
                type="danger"
                :icon="Delete"
                aria-label="删除配置"
                @click="removeConfiguration(config)"
              />
            </div>
          </article>
        </div>
        <el-empty v-else description="还没有配置模型服务" />
        <div class="list-footnote">
          <strong>推荐流程</strong>
          <p>选择厂商 → 自动确认地址 → 填入 Key → 测试连接 → 选择默认模型 → 回到素材 AI 使用。</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped lang="scss">
.settings-page {
  min-width: 0;
}
.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 13px;
  padding: 0;
  color: var(--primary);
  background: transparent;
  border: 0;
  font-size: var(--font-size-label);
  cursor: pointer;
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
.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(340px, 0.92fr);
  gap: 16px;
}
.config-editor,
.configuration-list {
  min-width: 0;
  padding: 20px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.configuration-list {
  background: var(--surface-subtle);
}
.panel-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 17px;
}
.section-label {
  color: var(--primary);
  font-size: var(--font-size-meta);
  font-weight: 800;
  letter-spacing: 0.05em;
}
.panel-title h2 {
  margin: 5px 0 0;
  font-size: var(--font-size-section-title);
}
.provider-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
}
.provider-card {
  display: flex;
  position: relative;
  align-items: center;
  gap: 10px;
  min-height: 67px;
  padding: 10px;
  text-align: left;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 9px;
  cursor: pointer;
  transition:
    border-color 160ms ease,
    background-color 160ms ease;
}
.provider-card:hover {
  border-color: #b8d0f4;
  background: var(--primary-softer);
}
.provider-card--active {
  background: var(--primary-softer);
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgb(36 116 245 / 10%);
}
.provider-mark {
  display: grid;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  place-items: center;
  color: #fff;
  background: var(--nav-bg);
  border-radius: 8px;
  font-size: var(--font-size-body);
  font-weight: 800;
}
.provider-card strong,
.provider-card small {
  display: block;
}
.provider-card strong {
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.provider-card small {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.provider-check {
  position: absolute;
  top: 9px;
  right: 9px;
  color: var(--primary);
}
.selected-provider-note {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  padding: 11px;
  background: var(--primary-softer);
  border: 1px solid #dce8fb;
  border-radius: 8px;
}
.note-icon {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  color: var(--primary);
  background: #fff;
  border-radius: 7px;
}
.selected-provider-note div {
  min-width: 0;
  flex: 1;
}
.selected-provider-note strong {
  font-size: var(--font-size-label);
}
.selected-provider-note p {
  margin: 3px 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
}
.form-section {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--border-soft);
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  margin-top: 14px;
}
.form-field--wide:first-child {
  grid-column: 1 / -1;
}
.form-field label {
  display: block;
  margin-bottom: 7px;
  color: var(--text-secondary);
  font-size: var(--font-size-label);
  font-weight: 700;
}
.form-field label span {
  margin-left: 4px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  font-weight: 400;
}
.security-note {
  display: flex;
  gap: 7px;
  margin-top: 14px;
  padding: 10px 11px;
  color: var(--text-secondary);
  background: var(--surface-muted);
  border-radius: 7px;
  font-size: var(--font-size-meta);
  line-height: 1.5;
}
.security-note .el-icon {
  color: var(--success-dark);
}
.form-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 22px;
}
.form-actions small {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.config-items {
  display: grid;
  gap: 11px;
}
.config-item {
  padding: 13px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 9px;
}
.config-item__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.config-item__top strong,
.config-item__top span {
  display: block;
}
.config-item__top strong {
  font-size: var(--font-size-body);
}
.config-item__top span {
  max-width: 220px;
  margin-top: 4px;
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.config-key {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
}
.config-key span {
  margin-left: auto;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.config-error {
  margin-top: 9px;
  padding: 8px;
  color: var(--danger-dark);
  background: var(--danger-soft);
  border-radius: 6px;
  font-size: var(--font-size-caption);
  line-height: 1.4;
}
.model-list {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border-soft);
}
.model-list__head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
}
.model-list__head strong {
  font-size: var(--font-size-meta);
}
.model-list__head span {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.model-select {
  width: 100%;
}
.model-option {
  display: flex;
  align-items: center;
  gap: 6px;
}
.model-option strong {
  font-size: var(--font-size-meta);
}
.model-option small {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.probe-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.probe-row small {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.probe-result {
  margin-top: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  background: var(--surface-subtle);
}
.probe-result strong {
  font-size: var(--font-size-meta);
}
.probe-result p {
  margin: 3px 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: 1.5;
}
.probe-result code {
  display: block;
  margin-top: 5px;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  word-break: break-all;
}
.probe-result--ok {
  border-color: var(--success);
}
.probe-result--error {
  border-color: var(--danger);
}
.model-hint {
  display: block;
  margin-top: 6px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.config-item__actions {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border-soft);
}
.list-footnote {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--border-soft);
}
.list-footnote strong {
  font-size: var(--font-size-meta);
}
.list-footnote p {
  margin: 5px 0 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  line-height: 1.5;
}
@media (max-width: 900px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 620px) {
  .provider-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }
  .form-field--wide:first-child {
    grid-column: auto;
  }
  .form-actions {
    align-items: flex-start;
    flex-direction: column;
  }
  .page-heading {
    flex-direction: column;
  }
}
</style>
