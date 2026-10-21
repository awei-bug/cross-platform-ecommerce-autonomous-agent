import { describe, expect, it } from 'vitest'

import { router } from './router'

describe('application routes', () => {
  it('registers the business pages behind explicit permissions', () => {
    const expected = new Map([
      ['dashboard', 'dashboard:read'],
      ['products', 'product:read'],
      ['orders', 'order:read'],
      ['campaigns', 'campaign:read'],
      ['reviews', 'review:read'],
      ['reports', 'report:read'],
      ['agent', 'diagnostic:read'],
      ['ecomops', 'automation:manage'],
      ['settings', undefined],
    ])

    for (const [name, permission] of expected) {
      const route = router.getRoutes().find((item) => item.name === name)
      expect(route, `${name} route should exist`).toBeDefined()
      expect(route?.meta.permission).toBe(permission)
    }
  })

  it('loads the completed order and after-sale workbench for /orders', async () => {
    const route = router.getRoutes().find((item) => item.name === 'orders')
    const loader = route?.components?.default as
      (() => Promise<{ default: { __name?: string } }>) | undefined

    expect(loader).toBeTypeOf('function')
    const module = await loader!()
    expect(module.default.__name).toBe('OrderAfterSaleView')
  })

  it('loads the completed report and review workbenches', async () => {
    for (const [name, viewName] of [
      ['reviews', 'ReviewMonitoringView'],
      ['reports', 'ReportCenterView'],
    ] as const) {
      const route = router.getRoutes().find((item) => item.name === name)
      const loader = route?.components?.default as
        (() => Promise<{ default: { __name?: string } }>) | undefined

      expect(loader, `${name} route should expose a lazy view`).toBeTypeOf('function')
      const module = await loader!()
      expect(module.default.__name).toBe(viewName)
    }
  })

  it('keeps login as the only public route', () => {
    const publicRoutes = router.getRoutes().filter((item) => item.meta.public)
    expect(publicRoutes.map((item) => item.name)).toEqual(['login'])
  })
})
