<script setup lang="ts">
import { Link, Refresh, UploadFilled, VideoPlay } from '@element-plus/icons-vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'

import { contentStudioApi } from '../api'
import { useSessionStore } from '../stores/session'
import type { ContentPublishStatus } from '../types/api'

const session = useSessionStore()
const queryClient = useQueryClient()

const draftForm = ref({ title: '', text: '', video_url: '' })

const statusQuery = useQuery({
  queryKey: ['content-connect-status'],
  queryFn: () => contentStudioApi.connectStatus(session.token!),
  enabled: computed(() => Boolean(session.token)),
})

const publishesQuery = useQuery({
  queryKey: ['content-publishes'],
  queryFn: () => contentStudioApi.publishes(session.token!),
  enabled: computed(() => Boolean(session.token)),
})
const publishes = computed(() => publishesQuery.data.value?.items ?? [])

const isConnected = computed(() => statusQuery.data.value?.state === 'ready')

const authorizeMutation = useMutation({
  mutationFn: () => contentStudioApi.authorize(session.token!),
  onSuccess: (data) => {
    window.open(data.authorization_url, '_blank', 'noopener')
    ElMessage.success('已打开抖音授权页，授权完成后点击「刷新连接状态」')
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '发起授权失败')
  },
})

const disconnectMutation = useMutation({
  mutationFn: () => contentStudioApi.disconnect(session.token!),
  onSuccess: () => {
    ElMessage.success('已断开抖音内容账号')
    void queryClient.invalidateQueries({ queryKey: ['content-connect-status'] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '断开连接失败')
  },
})

const createDraftMutation = useMutation({
  mutationFn: () =>
    contentStudioApi.createDraft(session.token!, {
      title: draftForm.value.title.trim(),
      text: draftForm.value.text.trim(),
      video_url: draftForm.value.video_url.trim() || undefined,
    }),
  onSuccess: () => {
    ElMessage.success('草稿已保存')
    draftForm.value = { title: '', text: '', video_url: '' }
    void queryClient.invalidateQueries({ queryKey: ['content-publishes'] })
  },
  onError: (error) => {
    ElMessage.error(error instanceof Error ? error.message : '保存草稿失败')
  },
})

const publishMutation = useMutation({
  mutationFn: (publishId: string) => contentStudioApi.publish(session.token!, publishId),
  onSuccess: () => {
    ElMessage.success('已提交到抖音，发布成功')
    void queryClient.invalidateQueries({ queryKey: ['content-publishes'] })
  },
  onError: (error: unknown) => {
    const detail = (error as { detail?: unknown })?.detail
    const message =
      (typeof detail === 'string' && detail) ||
      (detail && typeof detail === 'object' && 'message' in detail
        ? String((detail as { message: unknown }).message)
        : '') ||
      (error instanceof Error ? error.message : '发布失败')
    ElMessage.error(message)
    void queryClient.invalidateQueries({ queryKey: ['content-publishes'] })
  },
})

function statusType(status: ContentPublishStatus) {
  return status === 'published'
    ? 'success'
    : status === 'failed'
      ? 'danger'
      : status === 'publishing'
        ? 'primary'
        : 'info'
}

function statusLabel(status: ContentPublishStatus) {
  return { draft: '草稿', publishing: '发布中', published: '已发布', failed: '失败' }[status]
}
</script>

<template>
  <div class="content-studio">
    <header class="page-heading">
      <div>
        <div class="page-heading__eyebrow">
          <span>抖音内容投稿</span><b>官方开放能力</b>
        </div>
        <h1>内容发布工作台</h1>
        <p>撰写短视频文案、关联视频，授权抖音内容账号后一键投稿到抖音。真实发布需用户 OAuth 授权。</p>
      </div>
      <div class="page-heading__meta">
        <el-icon><VideoPlay /></el-icon>
        <span>连接状态：<strong>{{ isConnected ? '已连接' : '未连接' }}</strong></span>
        <el-button :icon="Refresh" :loading="statusQuery.isFetching.value" @click="statusQuery.refetch">
          刷新连接状态
        </el-button>
      </div>
    </header>

    <el-alert
      class="studio-alert"
      type="info"
      :closable="false"
      show-icon
      :title="statusQuery.data.value?.message || '连接抖音内容账号后即可发布'"
    />

    <section class="connect-panel panel-surface">
      <div class="section-heading">
        <div>
          <span>第一步</span>
          <h2>连接抖音内容账号</h2>
        </div>
        <small>个人可在抖音开放平台申请「投稿到抖音」开放能力</small>
      </div>
      <div v-if="isConnected" class="connect-row connect-row--ready">
        <el-tag type="success" effect="light">已授权</el-tag>
        <span class="connect-user">{{ statusQuery.data.value?.platform_user_name }}</span>
        <span v-if="statusQuery.data.value?.authorized_at" class="connect-time">
          授权于 {{ dayjs(statusQuery.data.value.authorized_at).format('YYYY-MM-DD HH:mm') }}
        </span>
        <el-button
          class="connect-disconnect"
          size="small"
          type="danger"
          plain
          :loading="disconnectMutation.isPending.value"
          @click="disconnectMutation.mutate()"
          >断开连接</el-button
        >
      </div>
      <div v-else class="connect-row">
        <p class="connect-hint">
          未连接抖音内容账号时，草稿可正常保存，但发布会被拦截并提示先完成授权。
        </p>
        <el-button
          type="primary"
          :icon="Link"
          :loading="authorizeMutation.isPending.value"
          @click="authorizeMutation.mutate()"
          >连接抖音账号</el-button
        >
      </div>
    </section>

    <section class="draft-panel panel-surface">
      <div class="section-heading">
        <div>
          <span>第二步</span>
          <h2>撰写内容草稿</h2>
        </div>
        <small>标题与文案，关联视频链接</small>
      </div>
      <el-form label-position="top" class="draft-form">
        <el-form-item label="标题">
          <el-input
            v-model="draftForm.title"
            maxlength="200"
            show-word-limit
            placeholder="例如：秋冬补水精华实测"
          />
        </el-form-item>
        <el-form-item label="文案">
          <el-input
            v-model="draftForm.text"
            type="textarea"
            :rows="3"
            maxlength="2000"
            show-word-limit
            placeholder="支持话题与@，会作为视频描述发布到抖音"
          />
        </el-form-item>
        <el-form-item label="视频链接">
          <el-input
            v-model="draftForm.video_url"
            placeholder="可公开访问的视频文件直链（投稿时需可下载为二进制）"
          />
        </el-form-item>
        <el-button
          type="primary"
          :icon="UploadFilled"
          :loading="createDraftMutation.isPending.value"
          :disabled="draftForm.title.trim().length < 1"
          @click="createDraftMutation.mutate()"
          >保存草稿</el-button
        >
      </el-form>
    </section>

    <section class="list-panel panel-surface">
      <div class="section-heading">
        <div>
          <span>第三步</span>
          <h2>发布队列（{{ publishes.length }}）</h2>
        </div>
        <el-button
          size="small"
          :icon="Refresh"
          :loading="publishesQuery.isFetching.value"
          @click="publishesQuery.refetch"
          >刷新</el-button
        >
      </div>
      <div v-if="publishes.length" class="publish-list">
        <article v-for="item in publishes" :key="item.id" class="publish-row">
          <div class="publish-head">
            <strong>{{ item.title }}</strong>
            <el-tag size="small" :type="statusType(item.status)" effect="light">{{
              statusLabel(item.status)
            }}</el-tag>
          </div>
          <p v-if="item.text" class="publish-text">{{ item.text }}</p>
          <p v-if="item.error_message" class="publish-error">失败原因：{{ item.error_message }}</p>
          <div class="publish-foot">
            <span class="publish-time">{{ dayjs(item.created_at).format('MM-DD HH:mm') }}</span>
            <div class="publish-controls">
              <el-link
                v-if="item.external_url"
                type="primary"
                :href="item.external_url"
                target="_blank"
                :underline="false"
                >查看作品</el-link
              >
              <el-button
                v-if="item.status === 'draft'"
                size="small"
                type="primary"
                :icon="VideoPlay"
                :loading="publishMutation.isPending.value"
                @click="publishMutation.mutate(item.id)"
                >投稿到抖音</el-button
              >
            </div>
          </div>
        </article>
      </div>
      <el-empty v-else description="还没有内容草稿，先撰写一条吧" :image-size="60" />
    </section>
  </div>
</template>

<style scoped lang="scss">
.content-studio {
  min-width: 0;
}
.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
}
.page-heading__eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--primary);
  font-size: var(--font-size-label);
  font-weight: 700;
}
.page-heading__eyebrow b {
  padding: 3px 6px;
  color: var(--warning-dark);
  background: var(--warning-soft);
  border-radius: 4px;
  font-size: var(--font-size-caption);
}
.page-heading h1 {
  margin: 7px 0 5px;
  color: var(--text-primary);
  font-size: 32px;
}
.page-heading p {
  margin: 0;
  max-width: 640px;
  color: var(--text-secondary);
  font-size: var(--font-size-body);
}
.page-heading__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
  white-space: nowrap;
}
.page-heading__meta strong {
  color: var(--text-secondary);
}
.studio-alert {
  margin-bottom: 14px;
}
.panel-surface {
  padding: 18px;
  margin-bottom: 14px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}
.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.section-heading span {
  display: block;
  color: var(--primary);
  font-size: var(--font-size-meta);
  font-weight: 700;
}
.section-heading h2 {
  margin: 4px 0 0;
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
}
.section-heading small {
  padding-top: 3px;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.connect-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.connect-row--ready {
  gap: 14px;
}
.connect-hint {
  margin: 0;
  width: 100%;
  color: var(--text-tertiary);
  font-size: var(--font-size-meta);
}
.connect-user {
  color: var(--text-secondary);
  font-weight: 600;
}
.connect-time {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.connect-disconnect {
  margin-left: auto;
}
.draft-form {
  max-width: 720px;
}
.publish-list {
  display: grid;
  gap: 10px;
}
.publish-row {
  padding: 12px 14px;
  background: var(--surface-subtle);
  border-radius: var(--radius-sm);
}
.publish-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.publish-head strong {
  color: var(--text-primary);
  font-size: var(--font-size-label);
}
.publish-text {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-meta);
  line-height: 1.6;
  white-space: pre-wrap;
}
.publish-error {
  margin: 6px 0 0;
  color: var(--danger);
  font-size: var(--font-size-caption);
}
.publish-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 8px;
}
.publish-time {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
.publish-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}
@media (max-width: 640px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
