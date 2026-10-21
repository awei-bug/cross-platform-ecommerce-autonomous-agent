import type { Page } from '@playwright/test'

/** Navigate through the same grouped/overlay menu exposed to users. */
export async function openNavigationGroup(page: Page, label: string) {
  const navigation = page.getByRole('navigation', { name: '主导航' })
  if (!(await navigation.isVisible())) {
    await page.getByRole('button', { name: '切换导航' }).click()
  }
  const group = navigation.locator('details').filter({
    has: page.getByRole('link', { name: label, exact: true, includeHidden: true }),
  })
  if (!(await group.evaluate((node) => (node as HTMLDetailsElement).open))) {
    await group.locator('summary').click()
  }
}

export async function navigateTo(page: Page, label: string) {
  await openNavigationGroup(page, label)
  await page
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: label, exact: true })
    .click()
}
