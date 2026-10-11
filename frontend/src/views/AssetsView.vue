<script setup lang="ts">
import { MagicStick, Picture, Refresh, Setting, Upload, VideoCamera } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { aiApi, assetApi } from '../api'
import { useSessionStore } from '../stores/session'
import type { AiConfiguration, AssetItem, AssetType, GenerationJob } from '../types/api'

const router = useRouter()
const session = useSessionStore()
const assets = ref<AssetItem[]>([])
const configurations = ref<AiConfiguration[]>([])
const selectedAssetId = ref<string | null>(null)
const assetType = ref<AssetType | ''>('')
const selectedModel = ref('')
const prompt = ref(
  '帮我为春季保湿面霜生成一版适合抖音商品卡的主图卖点文案，突出轻盈不粘和换季保湿。',
)
const selectedOutput = ref<AssetType>('copy')
const loading = ref(false)
const generating = ref(false)
const confirming = ref(false)
const uploading = ref(false)
const previewUrl = ref<string | null>(null)
const previewLoading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const currentJob = ref<GenerationJob | null>(null)
let pollTimer: number | undefined

const selectedAsset = computed(
  () => assets.value.find((item) => item.id === selectedAssetId.value) ?? assets.value[0] ?? null,
)
const currentVersion = computed(
  () =>
    selectedAsset.value?.versions.find(
      (version) => version.id === selectedAsset.value?.current_version_id,
    ) ??
    selectedAsset.value?.versions[0] ??
    null,
)
const readyConfigurations = computed(() =>
  configurations.value.filter(
    (item) => item.is_enabled && item.status === 'connected' && item.selected_model,
  ),
)
const modelOptions = computed(() =>
  readyConfigurations.value
    .flatMap((config) =>
      config.models.map((model) => ({
        ...model,
        configurationId: config.id,
        providerName: config.provider_name,
      })),
    )
    .sort((left, right) => Number(right.is_free === true) - Number(left.is_free === true)),
)
const activeConfigurationId = computed(
  () =>
    modelOptions.value.find((item) => item.model_id === selectedModel.value)?.configurationId ??
    configurations.value.find((item) => item.selected_model === selectedModel.value)?.id,
)

const typeLabels: Record<AssetType, string> = {
  copy: '文案',
  image: '图片',
  video_script: '视频脚本',
  video: '视频文件',
  template: '模板',
}
async function loadBinaryPreview(
  versionId: string | undefined,
  contentType: string | null | undefined,
) {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = null
  }
  if (
    !session.token ||
    !versionId ||
    !(contentType?.startsWith('image/') || contentType?.startsWith('video/'))
  ) {
    return
  }
  previewLoading.value = true
  try {
    const blob = await assetApi.preview(session.token, versionId)
    previewUrl.value = URL.createObjectURL(blob)
  } catch {
    // Keep the metadata preview available when an object is temporarily unavailable.
  } finally {
    previewLoading.value = false
  }
}

const typeIcons: Record<AssetType, typeof MagicStick> = {
  copy: MagicStick,
  image: Picture,
  video_script: VideoCamera,
  video: VideoCamera,
  template: Setting,
}

async function load() {
  if (!session.token) return
  loading.value = true
  try {
    const [assetResult, configResult] = await Promise.all([
      assetApi.list(session.token, assetType.value || undefined),
      aiApi.configurations(session.token),
    ])
    assets.value = assetResult.items
    configurations.value = configResult.items
    if (!selectedAssetId.value && assets.value[0]) selectedAssetId.value = assets.value[0].id
    if (!selectedModel.value)
      selectedModel.value = readyConfigurations.value[0]?.selected_model ?? 'demo-copy-v1'
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '素材数据加载失败')
  } finally {
    loading.value = false
  }
}

function openFilePicker() {
  fileInput.value?.click()
}

async function uploadFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!session.token || !file) return
  uploading.value = true
  try {
    const uploaded = await assetApi.upload(session.token, file, { title: file.name })
    await load()
    selectedAssetId.value = uploaded.id
    ElMessage.success('素材已上传并进入待质检状态')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '素材上传失败')
  } finally {
    uploading.value = false
  }
}

function chooseAsset(asset: AssetItem) {
  selectedAssetId.value = asset.id
}

async function generate() {
  if (!session.token || !prompt.value.trim()) return
  generating.value = true
  try {
    currentJob.value = await assetApi.createGenerationJob(session.token, {
      asset_id: selectedAsset.value?.id,
      asset_type: selectedOutput.value,
      prompt: prompt.value.trim(),
      configuration_id: activeConfigurationId.value,
      model_id: selectedModel.value || undefined,
    })
    ElMessage.success(
      currentJob.value.is_demo ? '演示生成任务已提交，结果需要人工确认' : '生成任务已提交',
    )
    if (currentJob.value.status !== 'succeeded') startPolling(currentJob.value.id)
    else await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '生成任务提交失败')
  } finally {
    generating.value = false
  }
}

function startPolling(jobId: string) {
  if (pollTimer) window.clearInterval(pollTimer)
  pollTimer = window.setInterval(async () => {
    if (!session.token) return
    try {
      currentJob.value = await assetApi.generationJob(session.token, jobId)
      if (['succeeded', 'failed'].includes(currentJob.value.status)) {
        if (pollTimer) window.clearInterval(pollTimer)
        if (currentJob.value.status === 'succeeded') await load()
      }
    } catch {
      if (pollTimer) window.clearInterval(pollTimer)
    }
  }, 900)
}

function selectModel(value: string) {
  selectedModel.value = value
}

function applyPrompt(value: string, type: AssetType) {
  prompt.value = value
  selectedOutput.value = type
}

watch(
  () => [currentVersion.value?.id, currentVersion.value?.content_type] as const,
  ([versionId, contentType]) => loadBinaryPreview(versionId, contentType),
  { immediate: true },
)

onMounted(load)
onUnmounted(() => {
  if (pollTimer) window.clearInterval(pollTimer)
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})

async function confirmCurrentVersion() {
  if (!session.token || !selectedAsset.value || !currentVersion.value) return
  confirming.value = true
  try {
    const updated = await assetApi.confirmVersion(
      session.token,
      selectedAsset.value.id,
      currentVersion.value.id,
    )
    const index = assets.value.findIndex((item) => item.id === updated.id)
    if (index >= 0) assets.value[index] = updated
    ElMessage.success('素材版本已确认入库；未自动发布到平台')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '确认素材版本失败')
  } finally {
    confirming.value = false
  }
}
</script>

<template>
  <section class="assets-page">
    <header class="page-heading">
      <div>
        <div class="heading-kicker"><span class="live-dot"></span>素材生产与复用工作区</div>
        <h1>素材 AI 中心</h1>
        <p>从商品上下文出发生产文案、图片创意和短视频脚本，先质检，再由运营确认入库。</p>
      </div>
      <div class="heading-actions">
        <el-tag type="warning" effect="light">演示数据 · 不自动发布</el-tag>
        <input
          ref="fileInput"
          class="sr-only"
          type="file"
          accept="image/*,video/*,text/plain"
          @change="uploadFile"
        />
        <el-button :icon="Upload" plain :loading="uploading" @click="openFilePicker"
          >上传素材</el-button
        >
        <el-button :icon="Setting" plain @click="router.push('/ai-settings')"
          >AI 模型配置</el-button
        >
        <el-button :icon="Refresh" plain :loading="loading" @click="load">刷新</el-button>
      </div>
    </header>

    <div class="workbench-toolbar">
      <div class="toolbar-context">
        <span>当前上下文</span><strong>柔肤电商事业部 · 全部店铺</strong><em>数据更新时间 09:40</em>
      </div>
      <div class="toolbar-controls">
        <el-select v-model="assetType" clearable placeholder="全部素材类型" @change="load">
          <el-option v-for="(label, key) in typeLabels" :key="key" :label="label" :value="key" />
        </el-select>
        <el-button type="primary" plain @click="router.push('/products')"
          >从商品中心选商品</el-button
        >
      </div>
    </div>

    <div class="asset-workspace">
      <aside class="asset-rail">
        <div class="panel-heading">
          <div>
            <span class="section-label">资产目录</span>
            <h2>我的素材</h2>
          </div>
          <el-tag size="small" effect="plain">{{ assets.length }} 项</el-tag>
        </div>
        <div v-loading="loading" class="asset-list">
          <button
            v-for="asset in assets"
            :key="asset.id"
            type="button"
            class="asset-row"
            :class="{ 'asset-row--active': selectedAsset?.id === asset.id }"
            @click="chooseAsset(asset)"
          >
            <span class="asset-row__icon"
              ><el-icon><component :is="typeIcons[asset.asset_type]" /></el-icon
            ></span>
            <span class="asset-row__copy"
              ><strong>{{ asset.title }}</strong
              ><small
                >{{ typeLabels[asset.asset_type] }} · {{ asset.product_id ?? '未绑定商品' }}</small
              ><span class="asset-tags"
                ><el-tag
                  v-for="tag in asset.tags.slice(0, 2)"
                  :key="tag"
                  size="small"
                  effect="plain"
                  >{{ tag }}</el-tag
                ></span
              ></span
            >
            <span class="asset-row__status" :class="`status--${asset.status}`">{{
              asset.status === 'approved' ? '已确认' : asset.status === 'review' ? '待确认' : '草稿'
            }}</span>
          </button>
          <el-empty v-if="!loading && !assets.length" description="暂无素材" />
        </div>
        <div class="rail-footnote">
          <strong>资产库原则</strong>
          <p>AI 只生成候选版本，不覆盖历史版本。每次确认都会留下版本与质检记录。</p>
        </div>
      </aside>

      <main class="generation-panel">
        <div class="panel-heading panel-heading--wide">
          <div>
            <span class="section-label">AI 生成工作区</span>
            <h2>把运营意图变成可复用素材</h2>
          </div>
          <span class="step-indicator"
            ><b>1</b> 描述目标 <i>→</i> <b>2</b> 生成候选 <i>→</i> <b>3</b> 人工确认</span
          >
        </div>
        <div class="generation-context">
          <span class="context-icon">✦</span>
          <div>
            <strong>{{ selectedAsset?.title ?? '未选择素材' }}</strong>
            <p>
              {{
                selectedAsset?.product_id
                  ? `关联商品 ${selectedAsset.product_id}`
                  : '生成后将创建新的素材资产'
              }}
            </p>
          </div>
          <el-tag type="info" effect="plain">{{
            selectedOutput === 'copy' ? '商品文案' : typeLabels[selectedOutput]
          }}</el-tag>
        </div>
        <label class="field-label" for="asset-prompt">生成目标</label>
        <el-input
          id="asset-prompt"
          v-model="prompt"
          type="textarea"
          :rows="7"
          resize="none"
          placeholder="描述商品、平台、目标人群和希望强调的卖点"
        />
        <div class="prompt-hints">
          <button
            type="button"
            @click="
              applyPrompt(
                '根据商品成分和使用场景生成 3 个淘宝详情页标题，语气可信，避免夸大功效。',
                'copy',
              )
            "
          >
            详情页标题</button
          ><button
            type="button"
            @click="
              applyPrompt(
                '生成 30 秒短视频脚本，前三秒抓住换季干燥痛点，结尾引导查看商品详情。',
                'video_script',
              )
            "
          >
            短视频脚本</button
          ><button
            type="button"
            @click="applyPrompt('生成 5 条不夸大、不承诺疗效的客服推荐话术。', 'copy')"
          >
            客服话术
          </button>
        </div>
        <div class="generation-options">
          <div>
            <span class="field-label">输出类型</span
            ><el-segmented
              v-model="selectedOutput"
              :options="
                Object.entries(typeLabels)
                  .filter(([value]) => value !== 'video')
                  .map(([value, label]) => ({ value, label }))
              "
            />
          </div>
          <div class="model-field">
            <span class="field-label">使用模型</span
            ><el-select v-model="selectedModel" placeholder="选择已连接模型" @change="selectModel"
              ><el-option
                v-for="model in modelOptions"
                :key="`${model.configurationId}-${model.model_id}`"
                :label="`${model.display_name} · ${model.providerName}`"
                :value="model.model_id"
                ><span class="model-option"
                  ><strong>{{ model.display_name }}</strong
                  ><el-tag v-if="model.is_free" size="small" type="success" effect="plain"
                    >免费</el-tag
                  ><small
                    >{{ model.providerName }} · {{ model.capabilities.join(' / ') }}</small
                  ></span
                ></el-option
              ><el-option
                v-if="!modelOptions.length"
                label="演示文案模型（无需 Key）"
                value="demo-copy-v1"
            /></el-select>
          </div>
        </div>
        <div class="generate-action">
          <el-button
            type="primary"
            size="large"
            :loading="generating"
            :icon="MagicStick"
            @click="generate"
            >生成候选素材</el-button
          ><small>生成结果进入待确认区，不会自动发布、改价或覆盖线上素材。</small>
        </div>
        <div v-if="currentJob" class="job-strip" :class="`job-strip--${currentJob.status}`">
          <span class="job-pulse"></span>
          <div>
            <strong>{{
              currentJob.status === 'succeeded'
                ? '候选素材已生成'
                : currentJob.status === 'running'
                  ? '正在生成候选素材'
                  : '生成任务已排队'
            }}</strong>
            <p>
              任务 {{ currentJob.id }} ·
              {{ currentJob.is_demo ? '演示 Provider' : currentJob.model_id }}
            </p>
          </div>
          <el-progress :percentage="currentJob.progress" :show-text="false" />
        </div>
      </main>

      <aside class="inspector-panel">
        <div class="panel-heading">
          <div>
            <span class="section-label">确认与质检</span>
            <h2>版本预览</h2>
          </div>
          <el-tag
            v-if="currentVersion"
            :type="currentVersion.quality_status === 'passed' ? 'success' : 'warning'"
            size="small"
            >{{ currentVersion.quality_status === 'passed' ? '质检通过' : '待质检' }}</el-tag
          >
        </div>
        <div v-if="currentVersion" class="preview-card">
          <div class="preview-meta">
            <span>V{{ currentVersion.version_number }}</span
            ><span>{{
              currentVersion.source === 'demo' || currentVersion.source === 'ai-demo'
                ? '演示生成'
                : '人工上传'
            }}</span>
          </div>
          <div v-if="currentVersion.content_type?.startsWith('image/')" class="media-preview">
            <el-image
              v-if="previewUrl"
              :src="previewUrl"
              fit="contain"
              :preview-src-list="[previewUrl]"
              preview-teleported
              alt="素材图片预览"
            />
            <el-skeleton v-else-if="previewLoading" animated :rows="5" />
            <el-empty v-else description="图片预览暂时不可用" />
          </div>
          <video
            v-else-if="currentVersion.content_type?.startsWith('video/') && previewUrl"
            class="media-preview media-preview--video"
            :src="previewUrl"
            controls
            preload="metadata"
          />
          <div v-else-if="currentVersion.content_type?.startsWith('video/')" class="media-preview">
            <el-skeleton v-if="previewLoading" animated :rows="5" />
            <el-empty v-else description="视频预览暂时不可用" />
          </div>
          <pre v-else>{{ currentVersion.content }}</pre>
          <div class="preview-foot">
            <span
              >{{
                new Date(currentVersion.created_at).toLocaleString('zh-CN', {
                  hour: '2-digit',
                  minute: '2-digit',
                })
              }}
              更新</span
            ><el-button
              v-if="selectedAsset?.status !== 'approved'"
              size="small"
              type="primary"
              plain
              :loading="confirming"
              @click="confirmCurrentVersion"
              >确认入库</el-button
            ><el-button v-else size="small" type="success" plain disabled>已确认</el-button>
          </div>
        </div>
        <el-empty v-else description="生成或选择一个素材" />
        <div class="quality-block">
          <div class="quality-heading"><strong>质检清单</strong><span>人工确认前</span></div>
          <div class="quality-row">
            <span class="check check--warning">!</span>
            <div><strong>平台尺寸与安全区</strong><small>图片类素材接入真实渲染后检查</small></div>
            <em>待接入</em>
          </div>
          <div class="quality-row">
            <span class="check check--warning">!</span>
            <div>
              <strong>敏感词与夸大宣传</strong><small>当前仅展示检查入口，未调用平台规则库</small>
            </div>
            <em>演示</em>
          </div>
          <div class="quality-row">
            <span class="check check--success">✓</span>
            <div><strong>版本可追溯</strong><small>已绑定生成任务与当前商品上下文</small></div>
            <em>通过</em>
          </div>
        </div>
        <div class="distribution-note">
          <strong>分发边界</strong>
          <p>真实淘宝、抖店、拼多多分发暂不执行。确认后的版本可在下一阶段接入平台能力矩阵。</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped lang="scss">
.assets-page {
  min-width: 0;
}
.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
}
.heading-kicker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--success-dark);
  font-size: var(--font-size-label);
  font-weight: 700;
}
.live-dot {
  width: 7px;
  height: 7px;
  background: var(--success);
  border-radius: 50%;
  box-shadow: 0 0 0 4px rgb(24 168 115 / 12%);
}
h1 {
  margin: 9px 0 6px;
  color: var(--text-primary);
  font-size: 30px;
  letter-spacing: -0.035em;
}
.page-heading p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-body);
  line-height: 1.6;
}
.heading-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.workbench-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.toolbar-context {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: var(--font-size-label);
}
.toolbar-context span {
  color: var(--text-tertiary);
}
.toolbar-context strong {
  color: var(--text-primary);
}
.toolbar-context em {
  color: var(--success-dark);
  font-style: normal;
}
.toolbar-controls {
  display: flex;
  gap: 10px;
}
.toolbar-controls .el-select {
  width: 150px;
}
.asset-workspace {
  display: grid;
  min-height: 660px;
  grid-template-columns: 278px minmax(420px, 1fr) 330px;
  gap: 14px;
}
.asset-rail,
.generation-panel,
.inspector-panel {
  min-width: 0;
  padding: 18px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.generation-panel {
  display: flex;
  flex-direction: column;
}
.inspector-panel {
  background: var(--surface-subtle);
}
.panel-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 16px;
}
.panel-heading--wide {
  align-items: center;
}
.section-label {
  color: var(--primary);
  font-size: var(--font-size-meta);
  font-weight: 800;
  letter-spacing: 0.06em;
}
.panel-heading h2 {
  margin: 5px 0 0;
  font-size: var(--font-size-section-title);
  letter-spacing: -0.02em;
}
.step-indicator {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
  white-space: nowrap;
}
.step-indicator b {
  display: inline-grid;
  width: 20px;
  height: 20px;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 50%;
}
.step-indicator i {
  margin: 0 5px;
  font-style: normal;
  color: var(--border-strong);
}
.asset-list {
  display: grid;
  gap: 6px;
  max-height: 480px;
  overflow: auto;
}
.asset-row {
  position: relative;
  display: grid;
  grid-template-columns: 32px 1fr;
  gap: 9px;
  width: 100%;
  padding: 10px;
  text-align: left;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 9px;
  cursor: pointer;
}
.asset-row:hover {
  background: var(--surface-subtle);
}
.asset-row--active {
  background: var(--primary-softer);
  border-color: #cfe0fb;
}
.asset-row__icon {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 7px;
}
.asset-row__copy {
  min-width: 0;
}
.asset-row__copy strong,
.asset-row__copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.asset-row__copy strong {
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.asset-row__copy small {
  margin-top: 3px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.asset-tags {
  display: flex;
  gap: 4px;
  margin-top: 7px;
}
.asset-tags :deep(.el-tag) {
  height: 19px;
  font-size: var(--font-size-caption);
}
.asset-row__status {
  grid-column: 2;
  justify-self: start;
  margin-top: 1px;
  font-size: var(--font-size-caption);
}
.status--approved {
  color: var(--success-dark);
}
.status--review {
  color: var(--warning-dark);
}
.status--draft {
  color: var(--text-tertiary);
}
.rail-footnote {
  margin-top: auto;
  padding: 14px 0 0;
  border-top: 1px solid var(--border-soft);
}
.rail-footnote strong {
  font-size: var(--font-size-label);
}
.rail-footnote p {
  margin: 6px 0 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
  line-height: 1.55;
}
.generation-context {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 22px;
  padding: 12px;
  background: var(--primary-softer);
  border: 1px solid #dce8fb;
  border-radius: var(--radius-md);
}
.context-icon {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  color: var(--primary);
  background: #fff;
  border-radius: 8px;
}
.generation-context div {
  min-width: 0;
  flex: 1;
}
.generation-context strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--font-size-label);
}
.generation-context p {
  margin: 3px 0 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.field-label {
  display: block;
  margin-bottom: 8px;
  color: var(--text-secondary);
  font-size: var(--font-size-label);
  font-weight: 700;
}
.generation-panel :deep(.el-textarea__inner) {
  padding: 12px;
  color: var(--text-primary);
  border-color: var(--border);
  box-shadow: none;
  line-height: 1.65;
}
.prompt-hints {
  display: flex;
  gap: 7px;
  margin-top: 9px;
  flex-wrap: wrap;
}
.prompt-hints button {
  padding: 5px 8px;
  color: var(--text-secondary);
  background: var(--surface-muted);
  border: 1px solid var(--border-soft);
  border-radius: 5px;
  font-size: var(--font-size-meta);
  cursor: pointer;
}
.prompt-hints button:hover {
  color: var(--primary);
  border-color: #bfd4f3;
}
.generation-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-top: 22px;
}
.generation-options > div {
  min-width: 0;
}
.generation-options :deep(.el-segmented) {
  width: 100%;
}
.generation-options :deep(.el-segmented__item-label) {
  padding-inline: 8px;
  font-size: var(--font-size-meta);
}
.model-field .el-select {
  width: 100%;
}
.model-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.model-option small {
  color: var(--text-tertiary);
}
.generate-action {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: auto;
  padding-top: 22px;
}
.generate-action small {
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
  line-height: 1.45;
}
.job-strip {
  display: grid;
  grid-template-columns: 10px 1fr 110px;
  align-items: center;
  gap: 9px;
  margin-top: 16px;
  padding: 10px 12px;
  background: var(--surface-muted);
  border: 1px solid var(--border-soft);
  border-radius: 8px;
}
.job-pulse {
  width: 8px;
  height: 8px;
  background: var(--warning);
  border-radius: 50%;
}
.job-strip--succeeded .job-pulse {
  background: var(--success);
}
.job-strip strong {
  font-size: var(--font-size-meta);
}
.job-strip p {
  margin: 3px 0 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.job-strip :deep(.el-progress-bar__outer) {
  background: #e7edf5;
}
.preview-card {
  padding: 13px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
}
.preview-meta,
.preview-foot {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.preview-meta span:first-child {
  color: var(--primary);
  font-weight: 800;
}
.media-preview {
  display: grid;
  min-height: 180px;
  place-items: center;
  overflow: hidden;
  border: 1px solid var(--line-subtle);
  border-radius: 14px;
  background: #f7f8fa;
}
.media-preview :deep(.el-image) {
  display: block;
  width: 100%;
  min-height: 180px;
}
.media-preview :deep(.el-image__inner) {
  max-height: 360px;
}
.media-preview--video {
  width: 100%;
  max-height: 360px;
}
.preview-card pre {
  min-height: 170px;
  margin: 12px 0;
  padding: 12px;
  color: var(--text-secondary);
  background: var(--surface-subtle);
  border: 1px solid var(--border-soft);
  border-radius: 7px;
  font-family: var(--font-sans);
  font-size: var(--font-size-meta);
  line-height: 1.65;
  white-space: pre-wrap;
}
.preview-foot {
  align-items: center;
}
.quality-block {
  margin-top: 20px;
}
.quality-heading {
  display: flex;
  justify-content: space-between;
  margin-bottom: 9px;
}
.quality-heading strong {
  font-size: var(--font-size-label);
}
.quality-heading span {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.quality-row {
  display: grid;
  grid-template-columns: 20px 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-soft);
}
.check {
  display: grid;
  width: 18px;
  height: 18px;
  place-items: center;
  border-radius: 50%;
  font-size: var(--font-size-meta);
  font-weight: 800;
}
.check--warning {
  color: var(--warning-dark);
  background: var(--warning-soft);
}
.check--success {
  color: var(--success-dark);
  background: var(--success-soft);
}
.quality-row strong,
.quality-row small {
  display: block;
}
.quality-row strong {
  font-size: var(--font-size-meta);
}
.quality-row small {
  margin-top: 3px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.quality-row em {
  color: var(--warning-dark);
  font-size: var(--font-size-caption);
  font-style: normal;
}
.quality-row:last-child em {
  color: var(--success-dark);
}
.distribution-note {
  margin-top: 20px;
  padding: 12px;
  color: var(--warning-dark);
  background: var(--warning-soft);
  border-radius: var(--radius-md);
}
.distribution-note strong {
  font-size: var(--font-size-meta);
}
.distribution-note p {
  margin: 5px 0 0;
  font-size: var(--font-size-caption);
  line-height: 1.55;
}
@media (max-width: 1200px) {
  .asset-workspace {
    grid-template-columns: 240px minmax(380px, 1fr);
  }
  .inspector-panel {
    grid-column: 1 / -1;
  }
  .preview-card {
    max-width: none;
  }
  .quality-block {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }
  .quality-heading {
    grid-column: 1 / -1;
  }
}
@media (max-width: 820px) {
  .page-heading,
  .workbench-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .heading-actions,
  .toolbar-controls {
    justify-content: flex-start;
  }
  .asset-workspace {
    grid-template-columns: 1fr;
  }
  .asset-rail {
    min-height: auto;
  }
  .asset-list {
    max-height: 260px;
  }
  .generation-options {
    grid-template-columns: 1fr;
  }
  .step-indicator {
    display: none;
  }
  .quality-block {
    display: block;
  }
}
</style>
