import { expect, test, type Page } from '@playwright/test'

import { navigateTo } from './navigation'

const E2E_CONFIG_PREFIX = 'E2E 演示配置'

async function enterWorkbench(page: Page) {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
}

async function removeE2eConfigurations(page: Page) {
  const token = await page.evaluate(() => localStorage.getItem('ops-command-center.token'))
  if (!token) return
  const response = await page.request.get('/api/v1/ai/configurations', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok()) return
  const payload = (await response.json()) as { items: Array<{ id: string; display_name: string }> }
  await Promise.all(
    payload.items
      .filter((item) => item.display_name.startsWith(E2E_CONFIG_PREFIX))
      .map((item) =>
        page.request.delete(`/api/v1/ai/configurations/${item.id}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ),
  )
}

test.describe('素材 AI 与模型配置验收', () => {
  test('可以配置演示模型、发现模型并生成待确认素材', async ({ page }) => {
    await enterWorkbench(page)
    await removeE2eConfigurations(page)
    const configName = `${E2E_CONFIG_PREFIX} ${Date.now()}`

    try {
      await navigateTo(page, '内容与素材')
      await expect(page).toHaveURL(/\/assets$/)
      await expect(page.getByRole('heading', { name: '素材 AI 中心' })).toBeVisible()
      await expect(page.getByText('演示数据 · 不自动发布')).toBeVisible()
      await expect(page.getByRole('heading', { name: '我的素材' })).toBeVisible()

      await page.getByRole('button', { name: 'AI 模型配置' }).click()
      await expect(page).toHaveURL(/\/ai-settings$/)
      await expect(page.getByRole('heading', { name: 'AI 模型配置' })).toBeVisible()

      await page.getByRole('button', { name: /演示模型（无需 Key）/ }).click()
      await expect(page.getByRole('textbox', { name: /请求地址 Base URL/ })).toHaveValue(
        'http://demo.local',
      )
      await page.getByRole('textbox', { name: '配置名称' }).fill(configName)
      await page.getByRole('button', { name: '保存配置' }).click()

      const configItem = page.locator('.config-item').filter({ hasText: configName })
      await expect(configItem).toBeVisible()

      await configItem.getByRole('button', { name: '测试连接并拉取模型' }).click()
      await expect(page.getByText('连接成功，已发现 3 个模型')).toBeVisible()
      await expect(configItem).toContainText('已连接')
      await expect(configItem).toContainText('已发现模型 · 3')

      const modelSelect = configItem.locator('.model-select')
      await modelSelect.click()
      await expect(page.getByRole('option')).toHaveCount(3)
      await page.getByRole('option').nth(1).click()
      await expect(page.getByText('默认模型已保存')).toBeVisible()

      await page.getByRole('button', { name: /返回素材 AI/ }).click()
      await expect(page).toHaveURL(/\/assets$/)
      await expect(page.getByRole('heading', { name: '素材 AI 中心' })).toBeVisible()
      await expect(page.getByText(/使用模型/)).toBeVisible()

      await page.getByRole('textbox', { name: '生成目标' }).fill('生成一条春季保湿面霜的短卖点')
      await page.getByRole('button', { name: '生成候选素材' }).click()
      await expect(page.getByText('候选素材已生成')).toBeVisible()
      await expect(page.getByText('待质检')).toBeVisible()
      await expect(
        page.getByText('生成结果进入待确认区，不会自动发布、改价或覆盖线上素材。'),
      ).toBeVisible()
    } finally {
      await removeE2eConfigurations(page)
    }
  })

  test('可以从页面上传文本素材、进入待确认并通过鉴权读取预览', async ({ page }) => {
    await enterWorkbench(page)
    await navigateTo(page, '内容与素材')
    await expect(page).toHaveURL(/\/assets$/)

    const title = `E2E-upload-${Date.now()}.txt`
    const content = 'E2E 素材上传验收：文件只进入待质检，不自动发布。'
    await page.locator('input[type="file"]').setInputFiles({
      name: title,
      mimeType: 'text/plain',
      buffer: Buffer.from(content, 'utf8'),
    })

    await expect(page.getByText('素材已上传并完成尺寸与敏感词质检')).toBeVisible()
    const assetRow = page.locator('.asset-row').filter({ hasText: title })
    await expect(assetRow).toBeVisible()
    await expect(assetRow).toContainText('待确认')
    await expect(page.getByText('人工上传')).toBeVisible()
    await expect(page.getByText(content)).toBeVisible()
    await expect(
      page.locator('.inspector-panel').getByText('质检通过', { exact: true }),
    ).toBeVisible()

    const token = await page.evaluate(() => localStorage.getItem('ops-command-center.token'))
    expect(token).toBeTruthy()
    const assetsResponse = await page.request.get('/api/v1/assets', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(assetsResponse.ok()).toBeTruthy()
    const assets = (await assetsResponse.json()) as {
      items: Array<{ title: string; versions: Array<{ preview_url: string | null }> }>
    }
    const uploaded = assets.items.find((item) => item.title === title)
    expect(uploaded).toBeTruthy()
    const previewUrl = uploaded?.versions[0]?.preview_url
    expect(previewUrl).toBeTruthy()

    const previewResponse = await page.request.get(previewUrl!, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(previewResponse.ok()).toBeTruthy()
    expect(await previewResponse.text()).toBe(content)

    const unauthorizedPreview = await page.request.get(previewUrl!)
    expect(unauthorizedPreview.status()).toBe(401)
  })
})
