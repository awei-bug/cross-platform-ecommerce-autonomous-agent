const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

interface ApiRequestOptions extends RequestInit {
  token?: string | null
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function errorMessage(payload: { detail?: unknown }, fallback: string): string {
  if (typeof payload.detail === 'string') return payload.detail
  if (Array.isArray(payload.detail)) {
    return payload.detail
      .map(
        (item: { loc?: unknown[]; msg?: string }) =>
          `${item.loc?.slice(1).join('.') ?? '参数'}：${item.msg ?? '校验失败'}`,
      )
      .join('；')
  }
  if (payload.detail && typeof payload.detail === 'object' && 'message' in payload.detail) {
    return String(payload.detail.message)
  }
  return fallback
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')

  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (options.token) {
    headers.set('Authorization', `Bearer ${options.token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  if (!response.ok) {
    let message = '请求失败，请稍后重试'
    try {
      const payload = (await response.json()) as { detail?: unknown }
      message = errorMessage(payload, message)
    } catch {
      // Keep the recoverable default message when the body is not JSON.
    }
    throw new ApiError(message, response.status)
  }
  return (await response.json()) as T
}

export async function apiRequestBlob(path: string, options: ApiRequestOptions = {}): Promise<Blob> {
  const headers = new Headers(options.headers)
  headers.set('Accept', '*/*')
  if (options.token) {
    headers.set('Authorization', `Bearer ${options.token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  if (!response.ok) {
    let message = '素材预览加载失败，请稍后重试'
    try {
      const payload = (await response.json()) as { detail?: unknown }
      message = errorMessage(payload, message)
    } catch {
      // Keep the safe default for non-JSON error responses.
    }
    throw new ApiError(message, response.status)
  }
  return response.blob()
}
