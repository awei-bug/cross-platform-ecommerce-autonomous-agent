import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { workspaceApi } from '../api'
import type { PlatformCapability, WorkspaceBootstrap } from '../types/api'
import { useSessionStore } from './session'

const SHOP_KEY = 'ops-command-center.shop-id'

export const useWorkspaceStore = defineStore('workspace', () => {
  const bootstrapData = ref<WorkspaceBootstrap | null>(null)
  const currentShopId = ref(localStorage.getItem(SHOP_KEY) ?? 'shop-all')
  const capabilities = ref<PlatformCapability[]>([])
  const isLoading = ref(false)

  const shops = computed(() => bootstrapData.value?.shops ?? [])
  const currentShop = computed(
    () => shops.value.find((shop) => shop.id === currentShopId.value) ?? shops.value[0],
  )
  const summary = computed(() => bootstrapData.value?.summary ?? null)
  const organization = computed(() => bootstrapData.value?.organization ?? null)

  async function load() {
    const session = useSessionStore()
    if (!session.token || isLoading.value) return
    isLoading.value = true
    try {
      bootstrapData.value = await workspaceApi.bootstrap(session.token)
      if (!shops.value.some((shop) => shop.id === currentShopId.value)) {
        currentShopId.value = bootstrapData.value.context.shop_id
      }
      await loadCapabilities()
    } finally {
      isLoading.value = false
    }
  }

  async function selectShop(shopId: string) {
    currentShopId.value = shopId
    localStorage.setItem(SHOP_KEY, shopId)
    await loadCapabilities()
  }

  async function loadCapabilities() {
    const session = useSessionStore()
    if (!session.token || currentShopId.value === 'shop-all') {
      capabilities.value = []
      return
    }
    capabilities.value = await workspaceApi.capabilities(session.token, currentShopId.value)
  }

  return {
    bootstrapData,
    currentShopId,
    capabilities,
    isLoading,
    shops,
    currentShop,
    summary,
    organization,
    load,
    selectShop,
    loadCapabilities,
  }
})
