import { createRouter, createWebHistory } from 'vue-router'

import { useSessionStore } from '../stores/session'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/',
      component: () => import('../components/layout/AppShell.vue'),
      children: [
        { path: '', redirect: '/dashboard' },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('../views/DashboardFoundationView.vue'),
          meta: { title: '运营总览', permission: 'dashboard:read' },
        },
        {
          path: 'products',
          name: 'products',
          component: () => import('../views/ModulePlaceholderView.vue'),
          meta: { title: '商品中心', permission: 'product:read', stage: '阶段 B', description: '跨平台 SKU 管理、异常巡检、批量操作与详情抽屉。' },
        },
        {
          path: 'orders',
          name: 'orders',
          component: () => import('../views/ModulePlaceholderView.vue'),
          meta: { title: '订单与售后', permission: 'order:read', stage: '阶段 C', description: '统一订单风险监控、售后时效预警和 AI 回复建议。' },
        },
        {
          path: 'campaigns',
          name: 'campaigns',
          component: () => import('../views/ModulePlaceholderView.vue'),
          meta: { title: '营销活动', permission: 'campaign:read', stage: '阶段 D', description: '活动排期、报名提醒、预算录入与优惠冲突检测。' },
        },
        {
          path: 'assets',
          name: 'assets',
          component: () => import('../views/ModulePlaceholderView.vue'),
          meta: { title: '素材 AI', permission: 'asset:read', stage: '阶段 D', description: '素材生产、质检、版本管理和跨平台分发。' },
        },
        {
          path: 'diagnostics',
          name: 'diagnostics',
          component: () => import('../views/ModulePlaceholderView.vue'),
          meta: { title: '数据诊断', permission: 'diagnostic:read', stage: '阶段 E', description: '店铺健康度、损失排序、经营复盘和 AI 诊断报告。' },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach(async (to) => {
  const session = useSessionStore()
  if (session.token && !session.user) await session.restore()

  if (!to.meta.public && !session.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && session.isAuthenticated) return { name: 'dashboard' }

  const permission = to.meta.permission as string | undefined
  if (permission && !session.hasPermission(permission)) return { name: 'dashboard' }

  document.title = `${String(to.meta.title ?? '工作台')} · 运营中枢`
  return true
})
