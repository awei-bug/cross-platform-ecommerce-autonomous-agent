import { chromium, expect } from '@playwright/test'
import { writeFile } from 'node:fs/promises'

const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await page.goto(process.env.CHAIN_CONTENT_WEB)
  await page.getByRole('button', { name: '商品批量内容' }).click()
  await page.getByLabel('商品数据（CSV）').fill('商品名称,核心卖点,售价,库存\n内容入口测试杯,轻便便携,129,30')
  await page.getByRole('button', { name: '导入商品', exact: true }).click()
  await expect(page.getByText('已导入 1 条产品数据。')).toBeVisible()
  const product = page.locator('.commerce-product-list li').filter({ hasText: '内容入口测试杯' })
  await expect(product).toBeVisible()
  const idText = await product.innerText()
  const externalId = idText.match(/cc-[\w-]+/)?.[0]
  if (!externalId) throw new Error(`未显示数据中心商品 ID: ${idText}`)
  await page.getByLabel('产品图片').uncheck()
  await page.getByLabel('产品视频').uncheck()
  expect((await page.request.get(`${process.env.DATA_HUB_URL}/test/fail-next`)).status()).toBe(200)
  await page.getByRole('button', { name: '创建内容任务' }).click()
  await expect(page.getByText('任务状态：已完成', { exact: false })).toBeVisible({ timeout: 20000 })
  await expect(page.getByText('测试标题')).toBeVisible()
  await expect(page.getByText('商品同步：数据中心同步失败', { exact: false })).toBeVisible({ timeout: 20000 })
  await page.getByRole('button', { name: '重新同步商品' }).click()
  await expect(page.getByText('商品同步：商品知识已同步', { exact: false })).toBeVisible({ timeout: 20000 })
  const response = await page.request.get(`${process.env.DATA_HUB_URL}/hub/products/chain-test/${externalId}`, {
    headers: { 'X-Hub-Tenant': 'chain-test', 'X-Hub-Token': process.env.DATA_HUB_TOKEN },
  })
  expect(response.status()).toBe(200)
  const item = (await response.json()).item
  expect(item.title).toBe('内容入口测试杯')
  expect(item.stock).toBe(30)
  expect(item.price).toBe(129)
  expect(item.desc_en).toBe('生成正文，仅供联调')
  await writeFile(process.env.CHAIN_ID_FILE, externalId, 'utf8')
  console.log('PASS 内容浏览器：导入、任务、模拟回调和商品知识自动同步')
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } })
  await mobile.goto(process.env.CHAIN_CONTENT_WEB)
  await mobile.getByRole('button', { name: '商品批量内容' }).click()
  await expect(mobile.getByLabel('商品数据（CSV）')).toBeVisible()
  if (await mobile.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) {
    throw new Error('内容工作台在 390px 视口横向溢出')
  }
  console.log('PASS 内容浏览器：390px 商品工作台布局')
} finally {
  await browser.close()
}
