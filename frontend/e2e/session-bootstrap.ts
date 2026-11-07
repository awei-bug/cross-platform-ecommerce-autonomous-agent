import { expect, type Page } from '@playwright/test'

/**
 * 本站已没有登录页：身份统一由云购后台登录后带 token 回跳。
 * E2E 直接注入会话 token（与真实回跳后的 localStorage 形态一致）。
 */
const TOKEN_KEY = 'ops-command-center.token'

export function accessToken(): string {
  return process.env.E2E_ACCESS_TOKEN ?? 'demo-access-token'
}

export async function enterWorkbench(page: Page) {
  await page.addInitScript(
    ([key, token]) => {
      window.localStorage.setItem(key, token)
    },
    [TOKEN_KEY, accessToken()] as const,
  )
  await page.goto('/dashboard')
  await expect(page).toHaveURL(/\/dashboard$/)
}
