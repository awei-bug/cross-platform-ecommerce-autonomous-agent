export type SlaTone = 'overdue' | 'urgent' | 'today' | 'safe' | 'none'

export interface SlaDisplay {
  label: string
  tone: SlaTone
}

export function getSlaDisplay(remainingMinutes: number | null): SlaDisplay {
  if (remainingMinutes === null) return { label: '无处理时限', tone: 'none' }
  if (remainingMinutes < 0) {
    const overdue = Math.abs(remainingMinutes)
    return {
      label: overdue < 60 ? `已超时 ${overdue} 分钟` : `已超时 ${Math.floor(overdue / 60)} 小时`,
      tone: 'overdue',
    }
  }
  if (remainingMinutes <= 120) {
    return {
      label:
        remainingMinutes < 60
          ? `剩余 ${remainingMinutes} 分钟`
          : `剩余 ${Math.floor(remainingMinutes / 60)} 小时 ${remainingMinutes % 60} 分钟`,
      tone: 'urgent',
    }
  }
  if (remainingMinutes <= 24 * 60) {
    return { label: `今日剩余 ${Math.ceil(remainingMinutes / 60)} 小时`, tone: 'today' }
  }
  return { label: `剩余 ${Math.ceil(remainingMinutes / (24 * 60))} 天`, tone: 'safe' }
}
