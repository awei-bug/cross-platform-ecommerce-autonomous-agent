import type { ConnectorState } from '../types/api'

export interface ConnectorStateDisplay {
  label: string
  /** Element Plus `el-tag` type。 */
  tag: 'success' | 'warning' | 'danger' | 'info'
  /** 该状态下允许的主要动作。 */
  action: 'authorize' | 'reauthorize' | 'none'
  description: string
}

const DISPLAYS: Record<ConnectorState, ConnectorStateDisplay> = {
  ready: {
    label: '已连接',
    tag: 'success',
    action: 'none',
    description: '已完成店铺授权与身份校验，读写范围以平台授权为准。',
  },
  authorization_required: {
    label: '待授权',
    tag: 'warning',
    action: 'authorize',
    description: '服务端凭证已就绪，需要店铺主账号完成一次 OAuth 授权。',
  },
  credentials_required: {
    label: '缺服务端配置',
    tag: 'info',
    action: 'none',
    description: '尚未配置该平台开放平台应用的 Key / Secret，无法发起授权。',
  },
  expired: {
    label: '已过期',
    tag: 'warning',
    action: 'reauthorize',
    description: '访问令牌已过期，重新授权后即可继续调用。',
  },
  revoked: { label: '已断开', tag: 'info', action: 'authorize', description: '店铺已解除授权。' },
  error: {
    label: '异常',
    tag: 'danger',
    action: 'reauthorize',
    description: '上一次授权或调用失败，请查看错误信息后重试。',
  },
  adapter_pending: {
    label: '适配器待接入',
    tag: 'info',
    action: 'none',
    description: '该平台的适配器尚未实现。',
  },
}

export function getConnectorStateDisplay(state: ConnectorState): ConnectorStateDisplay {
  return DISPLAYS[state]
}

export function isConnectorReady(state: ConnectorState): boolean {
  return state === 'ready'
}

/** 把 ISO 时间串渲染成运营可读的中文时间；空值统一显示为「—」。 */
export function formatConnectorTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (input: number) => String(input).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
