import { describe, expect, it } from 'vitest'

import { getSlaDisplay } from './orders'

describe('order SLA display', () => {
  it('uses server-provided minutes without recalculating against browser time', () => {
    expect(getSlaDisplay(-25)).toEqual({ label: '已超时 25 分钟', tone: 'overdue' })
    expect(getSlaDisplay(70)).toEqual({ label: '剩余 1 小时 10 分钟', tone: 'urgent' })
    expect(getSlaDisplay(null)).toEqual({ label: '无处理时限', tone: 'none' })
  })
})
