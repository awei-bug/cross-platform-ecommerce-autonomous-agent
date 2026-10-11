<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { workspaceApi } from '../../api'
import { ApiError } from '../../api/http'
import { useSessionStore } from '../../stores/session'
import type { SearchResult } from '../../types/api'

const router = useRouter()
const session = useSessionStore()
const root = ref<HTMLElement | null>(null)
const keyword = ref('')
const results = ref<SearchResult[]>([])
const isLoading = ref(false)
const isOpen = ref(false)
const errorMessage = ref('')
let requestSequence = 0

async function search() {
  const value = keyword.value.trim()
  if (!value || !session.token) {
    results.value = []
    isOpen.value = false
    return
  }

  const sequence = ++requestSequence
  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await workspaceApi.search(session.token, value)
    if (sequence === requestSequence) {
      results.value = response
      isOpen.value = true
    }
  } catch (error) {
    if (sequence === requestSequence) {
      results.value = []
      errorMessage.value = error instanceof ApiError ? error.message : '搜索暂时不可用，请稍后重试'
      isOpen.value = true
    }
  } finally {
    if (sequence === requestSequence) isLoading.value = false
  }
}

function navigate(result: SearchResult) {
  isOpen.value = false
  keyword.value = ''
  void router.push(result.route)
}

function closeOnEscape(event: KeyboardEvent) {
  if (event.key === 'Escape') isOpen.value = false
}

function closeOnOutside(event: PointerEvent) {
  if (root.value && !root.value.contains(event.target as Node)) isOpen.value = false
}

onMounted(() => {
  window.addEventListener('keydown', closeOnEscape)
  window.addEventListener('pointerdown', closeOnOutside)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', closeOnEscape)
  window.removeEventListener('pointerdown', closeOnOutside)
})
</script>

<template>
  <div ref="root" class="global-search">
    <el-input
      v-model="keyword"
      :prefix-icon="Search"
      placeholder="搜索订单号、SKU、活动"
      clearable
      aria-label="全局搜索"
      @keyup.enter="search"
      @clear="isOpen = false"
    >
      <template #suffix>
        <span v-if="isLoading" class="global-search__loading">检索中</span>
        <kbd v-else>Enter</kbd>
      </template>
    </el-input>

    <div v-if="isOpen" class="global-search__panel">
      <div class="global-search__panel-title">跨店铺搜索结果</div>
      <button
        v-for="result in results"
        :key="result.id"
        type="button"
        class="global-search__result"
        @click="navigate(result)"
      >
        <span class="global-search__type">{{ result.type }}</span>
        <span>
          <strong>{{ result.title }}</strong>
          <small>{{ result.subtitle }}</small>
        </span>
      </button>
      <div v-if="errorMessage" class="global-search__empty global-search__empty--error">
        {{ errorMessage }}
      </div>
      <div v-else-if="results.length === 0" class="global-search__empty">
        没有找到匹配内容，请尝试完整订单号或 SKU。
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.global-search {
  position: relative;
  width: min(420px, 34vw);
}
.global-search :deep(.el-input__wrapper) {
  min-height: 42px;
  padding-inline: 15px;
  background: var(--surface-muted);
  border-radius: 11px;
  box-shadow: inset 0 0 0 1px transparent;
}
.global-search :deep(.el-input__wrapper.is-focus) {
  background: #fff;
  box-shadow:
    0 0 0 3px rgb(36 116 245 / 12%),
    inset 0 0 0 1px var(--primary);
}
kbd {
  padding: 2px 6px;
  color: var(--text-tertiary);
  font: 11px/1.4 var(--font-sans);
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 4px;
}
.global-search__loading {
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
}
.global-search__panel {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  left: 0;
  z-index: 60;
  overflow: hidden;
  padding: 8px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  box-shadow: var(--shadow-lg);
}
.global-search__panel-title {
  padding: 8px 10px 10px;
  color: var(--text-tertiary);
  font-size: var(--font-size-label);
}
.global-search__result {
  display: grid;
  width: 100%;
  grid-template-columns: 58px 1fr;
  gap: 10px;
  padding: 11px 10px;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: 8px;
  cursor: pointer;
}
.global-search__result:hover {
  background: var(--primary-soft);
}
.global-search__result strong,
.global-search__result small {
  display: block;
}
.global-search__result strong {
  margin-bottom: 3px;
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.global-search__result small {
  color: var(--text-secondary);
}
.global-search__type {
  align-self: start;
  padding: 3px 7px;
  color: var(--primary);
  text-align: center;
  background: var(--primary-soft);
  border-radius: 5px;
  font-size: var(--font-size-meta);
  text-transform: uppercase;
}
.global-search__empty {
  padding: 22px 12px;
  color: var(--text-secondary);
  text-align: center;
  font-size: var(--font-size-body);
}
.global-search__empty--error {
  color: var(--danger-dark);
  background: var(--danger-soft);
  border-radius: 8px;
}
</style>
