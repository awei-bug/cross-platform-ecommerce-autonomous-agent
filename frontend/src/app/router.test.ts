import { describe, expect, it } from 'vitest'

import { router } from './router'

describe('application routes', () => {
  it('registers the six product modules behind explicit permissions', () => {
    const expected = new Map([
      ['dashboard', 'dashboard:read'],
      ['products', 'product:read'],
      ['orders', 'order:read'],
      ['campaigns', 'campaign:read'],
      ['assets', 'asset:read'],
      ['diagnostics', 'diagnostic:read'],
    ])

    for (const [name, permission] of expected) {
      const route = router.getRoutes().find((item) => item.name === name)
      expect(route, `${name} route should exist`).toBeDefined()
      expect(route?.meta.permission).toBe(permission)
    }
  })

  it('keeps login as the only public route', () => {
    const publicRoutes = router.getRoutes().filter((item) => item.meta.public)
    expect(publicRoutes.map((item) => item.name)).toEqual(['login'])
  })
})
