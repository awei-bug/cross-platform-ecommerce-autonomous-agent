<script setup lang="ts">
import { ArrowRight, CircleCheck, Clock } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => String(route.meta.title ?? '业务模块'))
const stage = computed(() => String(route.meta.stage ?? '后续阶段'))
const description = computed(() => String(route.meta.description ?? '模块将在后续阶段实现。'))
</script>

<template>
  <section class="module-placeholder">
    <header>
      <span>{{ stage }}</span>
      <h1>{{ title }}</h1>
      <p>{{ description }}</p>
    </header>
    <div class="module-placeholder__body">
      <div class="module-placeholder__mark">
        <el-icon :size="34"><Clock /></el-icon>
      </div>
      <div>
        <strong>基础路由、权限与店铺上下文已接入</strong>
        <p>
          该页面会复用当前工作区、全局搜索、消息告警、API 契约和统一组件体系，不会另起一套实现。
        </p>
      </div>
    </div>
    <div class="module-placeholder__checks">
      <span
        ><el-icon><CircleCheck /></el-icon>路由守卫</span
      >
      <span
        ><el-icon><CircleCheck /></el-icon>店铺上下文</span
      >
      <span
        ><el-icon><CircleCheck /></el-icon>权限契约</span
      >
      <span
        ><el-icon><CircleCheck /></el-icon>Mock API</span
      >
    </div>
    <button type="button" @click="$router.push('/dashboard')">
      返回运营总览 <el-icon><ArrowRight /></el-icon>
    </button>
  </section>
</template>

<style scoped lang="scss">
.module-placeholder {
  min-height: 520px;
  padding: 54px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.module-placeholder header {
  max-width: 660px;
}
.module-placeholder header > span {
  color: var(--primary);
  font-size: var(--font-size-label);
  font-weight: 700;
}
.module-placeholder h1 {
  margin: 12px 0 10px;
  color: var(--text-primary);
  font-size: 38px;
  letter-spacing: -0.035em;
}
.module-placeholder header p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-subtitle);
  line-height: 1.7;
}
.module-placeholder__body {
  display: grid;
  max-width: 760px;
  grid-template-columns: 64px 1fr;
  gap: 20px;
  margin-top: 54px;
  padding: 24px 0;
  border-top: 1px solid var(--border-soft);
  border-bottom: 1px solid var(--border-soft);
}
.module-placeholder__mark {
  display: grid;
  width: 56px;
  height: 56px;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 10px;
}
.module-placeholder__body strong {
  color: var(--text-primary);
  font-size: var(--font-size-subtitle);
}
.module-placeholder__body p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}
.module-placeholder__checks {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  margin-top: 26px;
  color: var(--success-dark);
  font-size: var(--font-size-body);
}
.module-placeholder__checks span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.module-placeholder > button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 44px;
  padding: 11px 17px;
  color: #fff;
  background: var(--primary);
  border: 0;
  border-radius: 8px;
  font-weight: 650;
  cursor: pointer;
  box-shadow: 0 10px 22px rgb(36 116 245 / 20%);
}
.module-placeholder > button:hover {
  background: var(--primary-hover);
}
</style>
