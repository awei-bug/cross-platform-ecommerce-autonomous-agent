export type Platform = 'all' | 'taobao' | 'douyin' | 'pinduoduo'
export type Severity = 'critical' | 'warning' | 'info'
export type CapabilityMode = 'direct' | 'async' | 'redirect' | 'unsupported'

export interface UserProfile {
  id: string
  name: string
  avatar_url: string | null
  role_name: string
  organization_id: string
  permissions: string[]
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserProfile
}

export interface Organization {
  id: string
  name: string
}

export interface Shop {
  id: string
  name: string
  platform: Platform
  platform_label: string
  status: string
  last_synced_at: string
}

export interface WorkspaceContext {
  organization_id: string
  shop_id: string
  platform: Platform
  time_range: string
}

export interface WorkspaceSummary {
  today_sales: number
  paid_orders: number
  active_alerts: number
  pending_tasks: number
  updated_at: string
}

export interface WorkspaceBootstrap {
  organization: Organization
  shops: Shop[]
  context: WorkspaceContext
  summary: WorkspaceSummary
}

export interface AlertItem {
  id: string
  title: string
  description: string
  severity: Severity
  shop_id: string
  shop_name: string
  created_at: string
  is_read: boolean
}

export interface SearchResult {
  id: string
  type: 'sku' | 'order' | 'campaign' | string
  title: string
  subtitle: string
  route: string
}

export interface PlatformCapability {
  key: string
  label: string
  mode: CapabilityMode
  reason: string | null
}
