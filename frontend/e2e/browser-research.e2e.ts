import { expect, test } from '@playwright/test'

test('公开竞品：文件入库、来源回看、费率重算与币种隔离', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/login')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await page.getByRole('link', { name: '跨境智能体中枢' }).click()
  await page.getByRole('tab', { name: '数据中台' }).click()
  const panel = page.locator('.browser-research')
  const collectionId = `browser-e2e-${Date.now()}`
  const observation = {
    source_url: 'https://example.com/public-product',
    title: 'E2E public research fixture',
    price: 20,
    currency: 'USD',
    collected_at: new Date().toISOString(),
    specifications: { size: '72x72' },
    price_evidence: 'Test fixture visible $20.00',
    evidence_file: 'test.png',
    evidence_sha256: 'a'.repeat(64),
  }
  await panel.locator('input[type=file]').setInputFiles({
    name: 'observations.json',
    mimeType: 'application/json',
    buffer: Buffer.from(
      JSON.stringify({
        collection_id: collectionId,
        country: 'US',
        category: 'E2E research fixture',
        observations: [
          observation,
          { ...observation, source_url: 'https://example.com/eur', price: 99, currency: 'EUR' },
        ],
      }),
    ),
  })
  await expect(page.getByText('公开竞品证据已入库')).toBeVisible()
  await expect(panel.getByRole('status')).toContainText('1 件有效价格样本')
  await expect(panel.getByRole('status')).toContainText('1 件因价格')
  await expect(panel.getByRole('cell', { name: 'USD 12.00', exact: true })).toBeVisible()
  await panel.getByRole('spinbutton', { name: '佣金假设' }).fill('20')
  await panel.getByRole('spinbutton', { name: '佣金假设' }).blur()
  await expect(panel.getByRole('cell', { name: 'USD 11.00', exact: true })).toBeVisible()
  await panel.getByText('查看页面证据').click()
  await expect(panel.getByRole('link', { name: '打开原商品页' })).toHaveAttribute(
    'href',
    observation.source_url,
  )
  await expect(panel.getByText('72x72', { exact: true })).toBeVisible()
  await panel
    .locator('.el-select__wrapper')
    .filter({
      has: page.getByRole('combobox', { name: '分析币种' }),
    })
    .click()
  await page.getByRole('option', { name: 'EUR', exact: true }).click()
  await expect(panel.getByRole('cell', { name: 'EUR 54.45', exact: true })).toBeVisible()
  await expect(panel.getByRole('cell', { name: 'USD 20', exact: true })).toHaveCount(0)
  const invalid = { ...observation, price: -1 }
  await panel.locator('input[type=file]').setInputFiles({
    name: 'invalid.json',
    mimeType: 'application/json',
    buffer: Buffer.from(
      JSON.stringify({
        collection_id: 'invalid-fixture',
        country: 'US',
        category: 'invalid',
        observations: [invalid],
      }),
    ),
  })
  await expect(page.locator('.el-message--error')).toBeVisible()
  await expect(panel.getByRole('cell', { name: 'EUR 54.45', exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
})
