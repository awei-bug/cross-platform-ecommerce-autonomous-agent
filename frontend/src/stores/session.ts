import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { authApi } from '../api'
import { SESSION_HANDOFF_PARAM } from '../app/unified-login'
import type { UserProfile } from '../types/api'

const TOKEN_KEY = 'ops-command-center.token'

/**
 * 云购统一会话端点：用浏览器 cookie 换取商家身份。
 * 该端点由云购侧提供；未就绪或跨域被拒时静默失败，不影响 token 回跳这条主路径。
 */
const MERCHANT_SESSION_URL = 'http://127.0.0.1:5000/user/session/'

interface MerchantSessionPayload {
  token?: string
  data?: { token?: string }
}

async function fetchMerchantSessionToken(): Promise<string | null> {
  const response = await fetch(MERCHANT_SESSION_URL, { credentials: 'include' })
  if (!response.ok) return null
  const payload = (await response.json()) as MerchantSessionPayload
  return payload.token ?? payload.data?.token ?? null
}

export const useSessionStore = defineStore('session', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<UserProfile | null>(null)
  const isRestoring = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value))

  function adopt(tokenValue: string) {
    token.value = tokenValue
    user.value = null
    localStorage.setItem(TOKEN_KEY, tokenValue)
  }

  /** 统一登录页回跳时把 token 收进 store，并从地址栏抹掉以免泄漏。 */
  function captureHandoffToken() {
    if (typeof window === 'undefined') return
    const url = new URL(window.location.href)
    const handoff = url.searchParams.get(SESSION_HANDOFF_PARAM) ?? url.searchParams.get('token')
    if (!handoff) return
    adopt(handoff)
    url.searchParams.delete(SESSION_HANDOFF_PARAM)
    url.searchParams.delete('token')
    window.history.replaceState(
      window.history.state,
      '',
      `${url.pathname}${url.search}${url.hash}`,
    )
  }

  /** 用云购 cookie 换取会话 token；成功即写入并校验。 */
  async function loginWithMerchantSession() {
    try {
      const merchantToken = await fetchMerchantSessionToken()
      if (!merchantToken) return false
      adopt(merchantToken)
      user.value = await authApi.me(merchantToken)
      return true
    } catch {
      return false
    }
  }

  /** 进入页面时恢复会话：先用已存 token 校验，失败再尝试统一会话。 */
  async function restore() {
    if (user.value) return true
    if (isRestoring.value) return false
    isRestoring.value = true
    try {
      if (token.value) {
        try {
          user.value = await authApi.me(token.value)
          return true
        } catch {
          logout()
        }
      }
      return await loginWithMerchantSession()
    } finally {
      isRestoring.value = false
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  function hasPermission(permission?: string) {
    if (!permission) return true
    // 云购超级管理员没有跨境动作码，但后端对 is_super 直接放行，前端必须同规则。
    if (user.value?.is_super) return true
    return Boolean(user.value?.permissions.includes(permission))
  }

  return {
    token,
    user,
    isRestoring,
    isAuthenticated,
    loginWithMerchantSession,
    captureHandoffToken,
    restore,
    logout,
    hasPermission,
  }
})
