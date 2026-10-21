<script setup lang="ts">
import {
  Calendar,
  Connection,
  Cpu,
  Document,
  Goods,
  HomeFilled,
  MagicStick,
  Monitor,
  Picture,
  Setting,
  Tickets,
  TrendCharts,
  VideoPlay,
} from '@element-plus/icons-vue'
import type { Component } from 'vue'
import { useRoute } from 'vue-router'

import BrandMark from '../shared/BrandMark.vue'

withDefaults(defineProps<{ collapsed?: boolean; embedded?: boolean }>(), {
  collapsed: false,
  embedded: false,
})

defineEmits<{ toggle: []; navigate: [] }>()

const route = useRoute()
const groups: Array<{
  label: string
  items: Array<{ path: string; label: string; icon: Component }>
}> = [
  {
    label: '工作台',
    items: [
      { path: '/dashboard', label: '运营总览', icon: HomeFilled },
      { path: '/ecomops', label: '跨境智能体中枢', icon: Connection },
      { path: '/automation', label: '自动化中心', icon: Cpu },
    ],
  },
  {
    label: '业务运营',
    items: [
      { path: '/products', label: '商品与库存', icon: Goods },
      { path: '/orders', label: '订单与客户服务', icon: Tickets },
      { path: '/campaigns', label: '营销与广告', icon: Calendar },
      { path: '/reviews', label: '评论与舆情', icon: Tickets },
    ],
  },
  {
    label: '内容',
    items: [
      { path: '/assets', label: '内容与素材', icon: Picture },
      { path: '/content-studio', label: '内容发布', icon: VideoPlay },
    ],
  },
  {
    label: '分析',
    items: [
      { path: '/agent', label: '智能体复盘', icon: MagicStick },
      { path: '/reports', label: '数据与复盘', icon: Document },
      { path: '/diagnostics', label: '数据诊断', icon: TrendCharts },
    ],
  },
  {
    label: '系统',
    items: [
      { path: '/integrations', label: '平台连接', icon: Connection },
      { path: '/ops', label: '任务运维', icon: Monitor },
      { path: '/settings', label: '系统设置', icon: Setting },
    ],
  },
]
function isActive(path: string) {
  return route.path.startsWith(path) || (path === '/settings' && route.path === '/ai-settings')
}
</script>

<template>
  <aside
    class="side-nav"
    :class="{ 'side-nav--collapsed': collapsed, 'side-nav--embedded': embedded }"
  >
    <div v-if="!embedded" class="side-nav__brand">
      <BrandMark :compact="collapsed" />
    </div>

    <nav class="side-nav__menu" aria-label="主导航">
      <details
        v-for="group in groups"
        :key="group.label"
        :open="collapsed || group.items.some((item) => isActive(item.path))"
        class="nav-group"
      >
        <summary :class="{ 'nav-group--active': group.items.some((item) => isActive(item.path)) }">
          {{ group.label }}
        </summary>
        <RouterLink
          v-for="item in group.items"
          :key="item.path"
          :to="item.path"
          class="side-nav__item"
          :class="{ 'side-nav__item--active': isActive(item.path) }"
          :aria-label="item.label"
          :title="collapsed ? item.label : undefined"
          @click="$emit('navigate')"
        >
          <el-icon :size="20"><component :is="item.icon" /></el-icon>
          <span v-if="!collapsed">{{ item.label }}</span>
        </RouterLink>
      </details>
    </nav>

    <button
      v-if="!embedded"
      class="side-nav__toggle"
      type="button"
      :aria-label="collapsed ? '展开导航' : '收起导航'"
      @click="$emit('toggle')"
    >
      <span>{{ collapsed ? '›' : '‹' }}</span>
    </button>

    <div v-if="!collapsed" class="side-nav__footer">
      <span class="side-nav__status-dot"></span>
      运营中枢 · 演示环境
    </div>
  </aside>
</template>

<style scoped lang="scss">
.side-nav {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 30;
  display: flex;
  width: var(--sidebar-width);
  flex-direction: column;
  color: var(--sidebar-text);
  background: var(--sidebar-bg);
  border-right: 1px solid rgb(255 255 255 / 8%);
}

.side-nav--collapsed {
  width: var(--sidebar-width-collapsed);
}
.side-nav__brand {
  display: flex;
  height: var(--header-height);
  align-items: center;
  padding: 0 24px;
}
.side-nav--collapsed .side-nav__brand {
  padding-inline: 12px;
}
.side-nav__menu {
  flex: 1;
  padding: 16px 12px;
  overflow-y: auto;
  min-height: 0;
}
.side-nav__item {
  display: flex;
  min-height: 44px;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  color: var(--sidebar-text-muted);
  text-decoration: none;
  border-radius: var(--radius-sm);
  transition:
    color 160ms ease,
    background-color 160ms ease,
    transform 160ms var(--ease-out);
}
.side-nav__item:hover {
  color: #fff;
  background: rgb(255 255 255 / 8%);
  transform: translateX(2px);
}
.side-nav__item:focus-visible {
  outline: 3px solid rgb(88 189 255 / 45%);
  outline-offset: 2px;
}
.side-nav__item--active {
  color: #fff;
  background: var(--primary);
  box-shadow: 0 10px 24px rgb(20 102 232 / 24%);
}
.side-nav--collapsed .side-nav__item {
  justify-content: center;
  padding-inline: 0;
}
.side-nav__toggle {
  position: absolute;
  top: 94px;
  right: -14px;
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  color: var(--primary);
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 50%;
  box-shadow: 0 6px 16px rgb(22 49 90 / 16%);
  cursor: pointer;
}
.side-nav__toggle span {
  transform: translateY(-1px);
  font-size: 23px;
  line-height: 1;
}
.side-nav__footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: auto;
  padding: 20px 24px;
  color: #b7c8e3;
  font-size: var(--font-size-label);
}
.nav-group + .nav-group {
  margin-top: 8px;
}
.nav-group > summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 44px;
  padding: 0 12px;
  color: var(--sidebar-text-muted);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  list-style: none;
}
.nav-group > summary::-webkit-details-marker {
  display: none;
}
.nav-group > summary::after {
  content: '›';
  font-size: 18px;
}
.nav-group[open] > summary::after {
  transform: rotate(90deg);
}
.nav-group > summary:hover,
.nav-group > .nav-group--active {
  color: #fff;
}
.nav-group > summary:focus-visible {
  outline: 2px solid #fff;
  outline-offset: -2px;
}
.nav-group .side-nav__item + .side-nav__item {
  margin-top: 4px;
}
.side-nav--collapsed .nav-group > summary {
  display: none;
}
.side-nav--collapsed .nav-group + .nav-group {
  padding-top: 8px;
  border-top: 1px solid rgb(255 255 255 / 16%);
}
.side-nav--embedded {
  position: static;
  width: 100%;
  height: 100%;
  border: 0;
}
.side-nav__status-dot {
  width: 8px;
  height: 8px;
  background: var(--success);
  border-radius: 50%;
  box-shadow: 0 0 0 4px rgb(25 189 133 / 14%);
}
</style>
