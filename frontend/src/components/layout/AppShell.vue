<script setup lang="ts">
import { ArrowDown, Fold, SwitchButton } from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useSessionStore } from '../../stores/session'
import { useWorkspaceStore } from '../../stores/workspace'
import AlertCenter from './AlertCenter.vue'
import GlobalSearch from './GlobalSearch.vue'
import SideNav from './SideNav.vue'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const workspace = useWorkspaceStore()
const desktopCollapsed = ref(false)
const isNarrow = ref(false)
const mobileNavOpen = ref(false)
let narrowViewport: MediaQueryList | null = null

const navCollapsed = computed(() =>
  isNarrow.value ? !mobileNavOpen.value : desktopCollapsed.value,
)
const frameCollapsed = computed(() => isNarrow.value || desktopCollapsed.value)

const pageTitle = computed(() => String(route.meta.title ?? '工作台'))
const syncedAt = computed(() => {
  const value = workspace.currentShop?.last_synced_at
  if (!value) return '等待首次同步'
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(
    new Date(value),
  )
})

function syncViewport(event: MediaQueryListEvent | MediaQueryList) {
  isNarrow.value = event.matches
  if (!event.matches) mobileNavOpen.value = false
}

function toggleNav() {
  if (isNarrow.value) {
    mobileNavOpen.value = !mobileNavOpen.value
    return
  }
  desktopCollapsed.value = !desktopCollapsed.value
}

onMounted(() => {
  void workspace.load()
  narrowViewport = window.matchMedia('(max-width: 820px)')
  syncViewport(narrowViewport)
  narrowViewport.addEventListener('change', syncViewport)
})

onBeforeUnmount(() => narrowViewport?.removeEventListener('change', syncViewport))

async function changeShop(value: string) {
  await workspace.selectShop(value)
}

function logout() {
  session.logout()
  void router.replace('/login')
}
</script>

<template>
  <div class="app-frame" :class="{ 'app-frame--collapsed': frameCollapsed }">
    <SideNav :collapsed="navCollapsed" @toggle="toggleNav" />
    <button
      v-if="isNarrow && mobileNavOpen"
      class="nav-scrim"
      type="button"
      aria-label="关闭导航"
      @click="mobileNavOpen = false"
    ></button>

    <header class="global-header">
      <div class="global-header__context">
        <button class="mobile-nav-trigger" type="button" aria-label="切换导航" @click="toggleNav">
          <el-icon><Fold /></el-icon>
        </button>
        <div class="context-copy">
          <span>{{ workspace.organization?.name ?? '正在载入组织' }}</span>
          <strong>{{ pageTitle }}</strong>
        </div>
        <span class="sync-copy">数据更新至 {{ syncedAt }}</span>
      </div>

      <div class="global-header__actions">
        <GlobalSearch />
        <AlertCenter />
        <el-dropdown trigger="click">
          <button class="user-menu" type="button">
            <span class="user-menu__avatar">{{ session.user?.name.slice(0, 1) ?? '运' }}</span>
            <span class="user-menu__copy">
              <strong>{{ session.user?.name ?? '运营用户' }}</strong>
              <small>{{ session.user?.role_name ?? '加载中' }}</small>
            </span>
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>{{ session.user?.role_name }}</el-dropdown-item>
              <el-dropdown-item divided @click="logout">
                <el-icon><SwitchButton /></el-icon>退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <main class="app-main">
      <section class="workspace-bar" aria-label="工作区上下文">
        <div class="workspace-bar__label">
          <span class="workspace-bar__signal"></span>
          当前工作区
        </div>
        <el-select
          :model-value="workspace.currentShopId"
          class="shop-select"
          :loading="workspace.isLoading"
          aria-label="选择店铺"
          @change="changeShop"
        >
          <el-option
            v-for="shop in workspace.shops"
            :key="shop.id"
            :label="`${shop.platform_label}｜${shop.name}`"
            :value="shop.id"
          />
        </el-select>
        <div class="workspace-bar__scope">
          <span>{{ workspace.currentShop?.platform_label ?? '全平台' }}</span>
          <strong>{{ workspace.currentShop?.name ?? '全部店铺' }}</strong>
        </div>
      </section>
      <RouterView />
    </main>
  </div>
</template>

<style scoped lang="scss">
.app-frame {
  min-height: 100vh;
  padding-left: var(--sidebar-width);
}
.app-frame--collapsed {
  padding-left: var(--sidebar-width-collapsed);
}
.global-header {
  position: fixed;
  inset: 0 0 auto var(--sidebar-width);
  z-index: 20;
  display: flex;
  height: var(--header-height);
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 0 28px;
  background: rgb(255 255 255 / 96%);
  border-bottom: 1px solid var(--border-soft);
}
.app-frame--collapsed .global-header {
  left: var(--sidebar-width-collapsed);
}
.global-header__context,
.global-header__actions,
.user-menu,
.workspace-bar,
.workspace-bar__label,
.workspace-bar__scope {
  display: flex;
  align-items: center;
}
.global-header__context {
  min-width: 0;
  gap: 18px;
}
.context-copy span,
.context-copy strong {
  display: block;
}
.context-copy span {
  margin-bottom: 3px;
  color: var(--text-tertiary);
  font-size: 11px;
}
.context-copy strong {
  color: var(--text-primary);
  font-size: 18px;
}
.sync-copy {
  padding-left: 18px;
  color: var(--text-tertiary);
  border-left: 1px solid var(--border);
  font-size: 12px;
  white-space: nowrap;
}
.global-header__actions {
  gap: 10px;
}
.user-menu {
  gap: 10px;
  padding: 4px 6px;
  color: var(--text-primary);
  background: transparent;
  border: 0;
  border-radius: 9px;
  cursor: pointer;
}
.user-menu:hover {
  background: var(--surface-muted);
}
.user-menu__avatar {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  color: #fff;
  background: var(--navy-700);
  border-radius: 9px;
  font-weight: 700;
}
.user-menu__copy {
  display: block;
  text-align: left;
}
.user-menu__copy strong,
.user-menu__copy small {
  display: block;
}
.user-menu__copy strong {
  font-size: 13px;
}
.user-menu__copy small {
  margin-top: 2px;
  color: var(--text-tertiary);
  font-size: 11px;
}
.mobile-nav-trigger {
  display: none;
}
.nav-scrim {
  position: fixed;
  inset: 0;
  z-index: 25;
  padding: 0;
  background: rgb(8 27 55 / 48%);
  border: 0;
}
.app-main {
  min-height: 100vh;
  padding: calc(var(--header-height) + 18px) 28px 36px;
  background: var(--page-bg);
}
.workspace-bar {
  min-height: 60px;
  gap: 16px;
  margin-bottom: 18px;
  padding: 9px 14px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.workspace-bar__label {
  gap: 9px;
  color: var(--text-secondary);
  font-size: 13px;
}
.workspace-bar__signal {
  width: 8px;
  height: 8px;
  background: var(--success);
  border-radius: 50%;
  box-shadow: 0 0 0 4px rgb(25 189 133 / 12%);
}
.shop-select {
  width: 250px;
}
.shop-select :deep(.el-select__wrapper) {
  min-height: 40px;
  border-radius: 8px;
  box-shadow: 0 0 0 1px var(--border) inset;
}
.workspace-bar__scope {
  gap: 8px;
  margin-left: auto;
}
.workspace-bar__scope span {
  padding: 4px 7px;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 5px;
  font-size: 11px;
}
.workspace-bar__scope strong {
  color: var(--text-primary);
  font-size: 13px;
}
@media (max-width: 1100px) {
  .sync-copy,
  .user-menu__copy {
    display: none;
  }
  .global-search {
    width: 320px;
  }
}
@media (max-width: 820px) {
  .app-frame,
  .app-frame--collapsed {
    padding-left: var(--sidebar-width-collapsed);
  }
  .global-header,
  .app-frame--collapsed .global-header {
    left: var(--sidebar-width-collapsed);
    padding-inline: 16px;
  }
  .mobile-nav-trigger {
    display: grid;
    width: 36px;
    height: 36px;
    place-items: center;
    background: transparent;
    border: 0;
  }
  .context-copy span {
    display: none;
  }
  .global-search {
    display: none;
  }
  .app-main {
    padding-inline: 16px;
  }
  .workspace-bar__label,
  .workspace-bar__scope {
    display: none;
  }
  .shop-select {
    width: 100%;
  }
}
</style>
