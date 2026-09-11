import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { authApi } from '../api'
import type { UserProfile } from '../types/api'

const TOKEN_KEY = 'ops-command-center.token'

export const useSessionStore = defineStore('session', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<UserProfile | null>(null)
  const isRestoring = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value))

  async function login(account: string, password: string) {
    const result = await authApi.login(account, password)
    token.value = result.access_token
    user.value = result.user
    localStorage.setItem(TOKEN_KEY, result.access_token)
  }

  async function restore() {
    if (!token.value || user.value || isRestoring.value) return
    isRestoring.value = true
    try {
      user.value = await authApi.me(token.value)
    } catch {
      logout()
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
    return !permission || Boolean(user.value?.permissions.includes(permission))
  }

  return { token, user, isRestoring, isAuthenticated, login, restore, logout, hasPermission }
})
