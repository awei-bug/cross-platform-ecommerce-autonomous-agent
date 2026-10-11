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
          path: 'automation',
          name: 'automation',
          component: () => import('../views/AutomationView.vue'),
          meta: {
            title: '自动化中心',
            permission: 'automation:manage',
            stage: '阶段 C',
            description: '规则扫描、人工确认任务和自动化执行记录。',
          },
        },
        {
          path: 'products',
          name: 'products',
          component: () => import('../views/ProductCenterView.vue'),
          meta: {
            title: '商品与库存',
            permission: 'product:read',
            stage: '阶段 B',
            description: '跨平台 SKU 管理、异常巡检、批量操作与详情抽屉。',
          },
        },
        {
          path: 'orders',
          name: 'orders',
          component: () => import('../views/OrderAfterSaleView.vue'),
          meta: {
            title: '订单与客户服务',
            permission: 'order:read',
            stage: '阶段 C',
            description: '统一订单风险监控、售后时效预警和 AI 回复建议。',
          },
        },
        {
          path: 'campaigns',
          name: 'campaigns',
          component: () => import('../views/CampaignsView.vue'),
          meta: {
            title: '营销与广告',
            permission: 'campaign:read',
            stage: '阶段 D',
            description: '广告账户、计划效率、预算告警与 AI 投放建议。',
          },
        },
        {
          path: 'reviews',
          name: 'reviews',
          component: () => import('../views/ReviewMonitoringView.vue'),
          meta: {
            title: '评论与舆情',
            permission: 'review:read',
            stage: '阶段 D',
            description: '全平台评价监控、差评工单、舆情关键词和标准回复模板。',
          },
        },
        {
          path: 'reports',
          name: 'reports',
          component: () => import('../views/ReportCenterView.vue'),
          meta: {
            title: '数据与复盘',
            permission: 'report:read',
            stage: '阶段 D',
            description: '报表模板、在线预览、导出任务和团队复盘笔记。',
          },
        },
        {
          path: 'assets',
          name: 'assets',
          component: () => import('../views/AssetsView.vue'),
          meta: {
            title: '内容与素材',
            permission: 'asset:read',
            stage: '阶段 D',
            description: '素材生产、质检、版本管理和跨平台分发。',
          },
        },
        {
          path: 'integrations',
          name: 'integrations',
          component: () => import('../views/PlatformConnectionsView.vue'),
          meta: {
            title: '平台连接',
            permission: 'integration:read',
            stage: '阶段 E',
            description: '淘宝、抖店、拼多多的 OAuth 授权状态与连接管理。',
          },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('../views/SettingsView.vue'),
          meta: {
            title: '系统设置',
            description: '管理 AI 服务、平台连接和工作区级配置。',
          },
        },
        {
          path: 'ai-settings',
          name: 'ai-settings',
          component: () => import('../views/AiSettingsView.vue'),
          meta: {
            title: 'AI 模型配置',
            permission: 'asset:read',
            stage: '阶段 D',
            description: '厂商连接、API Key 安全保存和可用模型发现。',
          },
        },
        {
          path: 'diagnostics',
          name: 'diagnostics',
          component: () => import('../views/ModulePlaceholderView.vue'),
          meta: {
            title: '数据诊断',
            permission: 'diagnostic:read',
            stage: '阶段 E',
            description: '店铺健康度、损失排序、经营复盘和 AI 诊断报告。',
          },
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
