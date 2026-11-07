import { chromium, expect } from '@playwright/test'

const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  await context.addInitScript(() => localStorage.setItem('mall_tenant_slug', 'chain-test'))
  const page = await context.newPage()
  await page.goto(process.env.CHAIN_MALL_URL + '/?tenant=chain-test')
  const name = process.env.CHAIN_PRODUCT_TITLE
  const card = page.locator('.product-card').filter({ hasText: name })
  await expect(card).toBeVisible({ timeout: 20000 })
  await expect(card).toContainText('129.00')
  await expect(card).toContainText('库存 12')
  await card.getByRole('button', { name: '查看并购买' }).click()
  await expect(page).toHaveURL(/\/product\//)
  await expect(page.getByText(name).first()).toBeVisible()
  await page.getByRole('button', { name: '导购客服' }).click()
  const chat = page.locator('.cs-panel')
  await chat.locator('.composer input').fill(`有没有${name}`)
  await chat.getByRole('button', { name: '发送' }).click()
  await expect(chat.locator('.msg.assistant').last()).toBeVisible({ timeout: 30000 })
  await expect(chat.getByText('回答依据')).toBeVisible({ timeout: 30000 })
  await expect(chat.locator('.citations')).toContainText(name)
  console.log('PASS 云购浏览器：商品列表、价格库存、商品详情和客服知识引用')
  await context.close()
} finally {
  await browser.close()
}
