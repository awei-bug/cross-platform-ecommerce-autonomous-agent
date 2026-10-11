import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { workspaceApi } from '../api'
import type { Platform, PlatformCapability, Shop, WorkspaceBootstrap } from '../types/api'
import { useSessionStore } from './session'

const SHOP_IDS_KEY = 'ops-command-center.shop-ids'
const LEGACY_SHOP_KEY = 'ops-command-center.shop-id'
const PLATFORM_KEY = 'ops-command-center.platform-filter'
const GROUPS_KEY = 'ops-command-center.shop-groups'

export interface ShopGroup {
  id: string
  name: string
  shop_ids: string[]
  platform: Platform
}

function storageValue(key: string) {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(key)
}

function readShopIds() {
  const saved = storageValue(SHOP_IDS_KEY)
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      if (Array.isArray(parsed))
        return parsed.filter((value): value is string => typeof value === 'string')
    } catch {
      // Fall back to the legacy single-shop preference below.
    }
  }
  return [storageValue(LEGACY_SHOP_KEY) ?? 'shop-all']
}

function readGroups(): ShopGroup[] {
  const saved = storageValue(GROUPS_KEY)
  if (!saved) return []
  try {
    const parsed = JSON.parse(saved)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((group): group is ShopGroup =>
      Boolean(
        group &&
        typeof group.id === 'string' &&
        typeof group.name === 'string' &&
        Array.isArray(group.shop_ids) &&
        group.shop_ids.every((value: unknown) => typeof value === 'string'),
      ),
    )
  } catch {
    return []
  }
}

function persist(key: string, value: unknown) {
  if (typeof window !== 'undefined') window.localStorage.setItem(key, JSON.stringify(value))
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const bootstrapData = ref<WorkspaceBootstrap | null>(null)
  const selectedShopIds = ref<string[]>(readShopIds())
  const platformFilter = ref<Platform>((storageValue(PLATFORM_KEY) as Platform | null) ?? 'all')
  const shopGroups = ref<ShopGroup[]>(readGroups())
  const capabilities = ref<PlatformCapability[]>([])
  const isLoading = ref(false)

  const shops = computed(() => bootstrapData.value?.shops ?? [])
  const selectableShops = computed(() => shops.value.filter((shop) => shop.id !== 'shop-all'))
  const filteredShops = computed(() =>
    selectableShops.value.filter(
      (shop) => platformFilter.value === 'all' || shop.platform === platformFilter.value,
    ),
  )
  const activeShopIds = computed(() => {
    const availableIds = new Set(filteredShops.value.map((shop) => shop.id))
    if (selectedShopIds.value.includes('shop-all')) return [...availableIds]
    return selectedShopIds.value.filter((shopId) => availableIds.has(shopId))
  })
  const selectedShops = computed(() =>
    activeShopIds.value
      .map((shopId) => shops.value.find((shop) => shop.id === shopId))
      .filter((shop): shop is Shop => Boolean(shop)),
  )
  const isSingleShop = computed(() => activeShopIds.value.length === 1)
  const currentShopId = computed(() => {
    if (platformFilter.value === 'all' && selectedShopIds.value.includes('shop-all'))
      return 'shop-all'
    return activeShopIds.value.join(',') || 'shop-all'
  })
  const currentShop = computed(() =>
    isSingleShop.value
      ? selectedShops.value[0]
      : shops.value.find((shop) => shop.id === 'shop-all'),
  )
  const scopeLabel = computed(() => {
    if (!activeShopIds.value.length) return '暂无店铺'
    if (
      activeShopIds.value.length === selectableShops.value.length &&
      platformFilter.value === 'all'
    ) {
      return '全部店铺'
    }
    if (activeShopIds.value.length === 1) return selectedShops.value[0]?.name ?? '当前店铺'
    return `${activeShopIds.value.length} 个店铺`
  })
  const scopePlatformLabel = computed(() => {
    if (platformFilter.value !== 'all') return filteredShops.value[0]?.platform_label ?? '全平台'
    const platforms = new Set(selectedShops.value.map((shop) => shop.platform_label))
    return platforms.size === 1 ? [...platforms][0] : '全平台'
  })
  const summary = computed(() => bootstrapData.value?.summary ?? null)
  const organization = computed(() => bootstrapData.value?.organization ?? null)

  function normalizeSelection(values: string[]) {
    const validIds = new Set(selectableShops.value.map((shop) => shop.id))
    const normalized = [...new Set(values.filter((shopId) => validIds.has(shopId)))]
    selectedShopIds.value = normalized.length ? normalized : ['shop-all']
    persist(SHOP_IDS_KEY, selectedShopIds.value)
  }

  async function load() {
    const session = useSessionStore()
    if (!session.token || isLoading.value) return
    isLoading.value = true
    try {
      bootstrapData.value = await workspaceApi.bootstrap(session.token)
      if (!['all', 'taobao', 'douyin', 'pinduoduo'].includes(platformFilter.value)) {
        platformFilter.value = 'all'
      }
      if (selectedShopIds.value.includes('shop-all')) {
        selectedShopIds.value = ['shop-all']
      } else {
        normalizeSelection(selectedShopIds.value)
      }
      await loadCapabilities()
    } finally {
      isLoading.value = false
    }
  }

  async function selectShops(shopIds: string[]) {
    if (shopIds.includes('shop-all') || shopIds.length === 0) {
      selectedShopIds.value = ['shop-all']
      persist(SHOP_IDS_KEY, selectedShopIds.value)
    } else {
      normalizeSelection(shopIds)
    }
    await loadCapabilities()
  }

  async function selectShop(shopId: string) {
    await selectShops([shopId])
  }

  async function setPlatformFilter(platform: Platform) {
    platformFilter.value = platform
    persist(PLATFORM_KEY, platform)
    if (platform !== 'all' && !selectedShopIds.value.includes('shop-all')) {
      const allowed = new Set(
        selectableShops.value.filter((shop) => shop.platform === platform).map((shop) => shop.id),
      )
      const next = selectedShopIds.value.filter((shopId) => allowed.has(shopId))
      selectedShopIds.value = next.length ? next : ['shop-all']
      persist(SHOP_IDS_KEY, selectedShopIds.value)
    }
    await loadCapabilities()
  }

  async function loadCapabilities() {
    const session = useSessionStore()
    if (!session.token || !isSingleShop.value) {
      capabilities.value = []
      return
    }
    capabilities.value = await workspaceApi.capabilities(session.token, activeShopIds.value[0])
  }

  function saveGroup(name: string) {
    const trimmed = name.trim()
    if (!trimmed) return
    const group: ShopGroup = {
      id: `group-${Date.now()}`,
      name: trimmed,
      shop_ids: selectedShopIds.value.includes('shop-all')
        ? ['shop-all']
        : [...selectedShopIds.value],
      platform: platformFilter.value,
    }
    shopGroups.value = [group, ...shopGroups.value.filter((item) => item.name !== trimmed)].slice(
      0,
      12,
    )
    persist(GROUPS_KEY, shopGroups.value)
  }

  async function applyGroup(groupId: string) {
    const group = shopGroups.value.find((item) => item.id === groupId)
    if (!group) return
    platformFilter.value = group.platform
    selectedShopIds.value = [...group.shop_ids]
    persist(PLATFORM_KEY, platformFilter.value)
    persist(SHOP_IDS_KEY, selectedShopIds.value)
    await loadCapabilities()
  }

  function deleteGroup(groupId: string) {
    shopGroups.value = shopGroups.value.filter((item) => item.id !== groupId)
    persist(GROUPS_KEY, shopGroups.value)
  }

  return {
    bootstrapData,
    selectedShopIds,
    platformFilter,
    shopGroups,
    currentShopId,
    activeShopIds,
    capabilities,
    isLoading,
    shops,
    selectableShops,
    filteredShops,
    selectedShops,
    isSingleShop,
    currentShop,
    scopeLabel,
    scopePlatformLabel,
    summary,
    organization,
    load,
    selectShop,
    selectShops,
    setPlatformFilter,
    saveGroup,
    applyGroup,
    deleteGroup,
    loadCapabilities,
  }
})
