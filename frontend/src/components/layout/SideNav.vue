<script setup lang="ts">
import {
  Calendar,
  Connection,
  Cpu,
  Document,
  Goods,
  HomeFilled,
  Picture,
  Setting,
  Tickets,
} from '@element-plus/icons-vue'
import type { Component } from 'vue'
import { useRoute } from 'vue-router'

import BrandMark from '../shared/BrandMark.vue'

withDefaults(defineProps<{ collapsed?: boolean }>(), { collapsed: false })

defineEmits<{ toggle: [] }>()

const route = useRoute()
const items: Array<{ path: string; label: string; icon: Component }> = [
  { path: '/dashboard', label: '运营总览', icon: HomeFilled },
  { path: '/automation', label: '自动化中心', icon: Cpu },
  { path: '/products', label: '商品与库存', icon: Goods },
  { path: '/orders', label: '订单与客户服务', icon: Tickets },
  { path: '/campaigns', label: '营销与广告', icon: Calendar },
  { path: '/assets', label: '内容与素材', icon: Picture },
  { path: '/reports', label: '数据与复盘', icon: Document },
  { path: '/integrations', label: '平台连接', icon: Connection },
  { path: '/settings', label: '系统设置', icon: Setting },
]
</script>

<template>
  <aside class="side-nav" :class="{ 'side-nav--collapsed': collapsed }">
    <div class="side-nav__brand">
      <BrandMark :compact="collapsed" />
    </div>

    <nav class="side-nav__menu" aria-label="主导航">
      <RouterLink
        v-for="item in items"
        :key="item.path"
        :to="item.path"
        class="side-nav__item"
        :class="{ 'side-nav__item--active': route.path.startsWith(item.path) }"
        :aria-label="item.label"
      >
        <el-icon :size="20"><component :is="item.icon" /></el-icon>
        <span v-if="!collapsed">{{ item.label }}</span>
      </RouterLink>
    </nav>

    <button
      class="side-nav__toggle"
      type="button"
      :aria-label="collapsed ? '展开导航' : '收起导航'"
      @click="$emit('toggle')"
    >
      <span>{{ collapsed ? '›' : '‹' }}</span>
    </button>

    <div v-if="!collapsed" class="side-nav__footer">
      <span class="side-nav__status-dot"></span>
      演示环境 · API 已连接
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
  display: grid;
  gap: 6px;
  padding: 18px 14px;
}
.side-nav__item {
  display: flex;
  min-height: 48px;
  align-items: center;
  gap: 14px;
  padding: 0 16px;
  color: var(--sidebar-text-muted);
  text-decoration: none;
  border-radius: 10px;
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
.side-nav__status-dot {
  width: 8px;
  height: 8px;
  background: var(--success);
  border-radius: 50%;
  box-shadow: 0 0 0 4px rgb(25 189 133 / 14%);
}
</style>
