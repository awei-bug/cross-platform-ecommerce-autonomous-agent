import type {
  AlertItem,
  LoginResponse,
  PlatformCapability,
  SearchResult,
  UserProfile,
  WorkspaceBootstrap,
} from '../types/api'
import { apiRequest } from './http'

export const authApi = {
  login(account: string, password: string) {
    return apiRequest<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ account, password }),
    })
  },
  me(token: string) {
    return apiRequest<UserProfile>('/auth/me', { token })
  },
}

export const workspaceApi = {
  bootstrap(token: string) {
    return apiRequest<WorkspaceBootstrap>('/workspace/bootstrap', { token })
  },
  alerts(token: string, unreadOnly = false) {
    return apiRequest<AlertItem[]>(`/workspace/alerts?unread_only=${unreadOnly}`, { token })
  },
  capabilities(token: string, shopId: string) {
    return apiRequest<PlatformCapability[]>(
      `/workspace/capabilities?shop_id=${encodeURIComponent(shopId)}`,
      { token },
    )
  },
  search(token: string, keyword: string) {
    return apiRequest<SearchResult[]>(`/search?q=${encodeURIComponent(keyword)}`, { token })
  },
}
