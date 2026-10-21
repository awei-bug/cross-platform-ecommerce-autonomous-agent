import { expect, test } from '@playwright/test'
import type { EcomOverview, EcomRun } from '../src/api/ecomops'

test('跨境中枢：导入、初始化、选品分支与审批恢复', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/login')
  await page.getByRole('button', { name: '进入工作台' }).click()
  await page.getByRole('link', { name: '跨境智能体中枢' }).click()
  await expect(page.getByRole('heading', { name: '跨境多智能体运营中枢' })).toBeVisible()
  await expect(page.getByText('当前为本地沙盒流程，跨境平台尚未接入')).toBeVisible()
  await page.getByRole('tab', { name: '数据中台' }).click()
  await page.getByRole('button', { name: '填入演示样例' }).click()
  await page.getByRole('button', { name: '校验并导入' }).click()
  await expect(page.getByText('共享数据已入库')).toBeVisible()
  await page.getByRole('tab', { name: '任务协同' }).click()
  await page.getByRole('button', { name: '新建任务', exact: true }).first().click()
  await page.getByRole('button', { name: '下一步：填写参数' }).click()
  await page.getByRole('button', { name: '创建并执行任务' }).click()
  const drawer = page.getByRole('dialog', { name: '任务协同与人工处置' })
  await expect(drawer.getByText('已完成', { exact: true }).first()).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(drawer).not.toBeVisible()
  await page.getByRole('button', { name: '新建任务', exact: true }).click()
  await page
    .locator('.el-select__wrapper')
    .filter({
      has: page.getByRole('combobox', { name: '业务流程' }),
    })
    .click()
  await page.getByRole('option', { name: '市场调研与选品', exact: true }).click()
  await page.getByPlaceholder('可选，默认使用流程名称').fill('E2E 高价值选品')
  await page.getByRole('button', { name: '下一步：填写参数' }).click()
  await page.getByPlaceholder('例如 DEMO-SKU-01').fill('DEMO-SKU-01')
  await page.getByRole('spinbutton', { name: '备货 / 订单数量' }).fill('2000')
  const createPanel = page.getByRole('dialog', { name: '新建运营任务' })
  await createPanel.locator('.el-drawer__body').evaluate((node) => {
    node.scrollTop = 0
  })
  await page.screenshot({ path: 'test-results/ecomops-create-desktop.png', animations: 'disabled' })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(createPanel.getByRole('button', { name: '创建并执行任务' })).toBeInViewport()
  await page.screenshot({ path: 'test-results/ecomops-create-mobile.png', animations: 'disabled' })
  await page.setViewportSize({ width: 1280, height: 720 })
  await page.getByRole('button', { name: '创建并执行任务' }).click()
  await expect(drawer.getByText('待人工审核', { exact: true }).first()).toBeVisible()
  await drawer
    .getByPlaceholder('说明核验依据、驳回原因或人工接管计划')
    .fill('已核验样例采购报价与供应链，不执行真实采购')
  await expect(drawer.getByText('审批金额与权限依据')).toBeVisible()
  await expect(drawer.getByText('备货金额 USD', { exact: true })).toBeVisible()
  await expect(page.locator('.el-message')).toHaveCount(0, { timeout: 8000 })
  await page.screenshot({ path: 'test-results/ecomops-review-desktop.png', animations: 'disabled' })
  await page.setViewportSize({ width: 390, height: 844 })
  await drawer.getByText('审批金额与权限依据').scrollIntoViewIfNeeded()
  const approve = drawer.getByRole('button', { name: '通过审核并继续' })
  await expect(approve).toBeInViewport()
  await expect(
    drawer.getByRole('textbox', { name: '审核依据（必填） · 五维评分与利润测算' }),
  ).toBeVisible()
  await page.screenshot({ path: 'test-results/ecomops-review-mobile.png', animations: 'disabled' })
  await page.setViewportSize({ width: 1280, height: 720 })
  await drawer.getByRole('button', { name: '通过审核并继续' }).click()
  await expect(drawer.getByPlaceholder('说明核验依据、驳回原因或人工接管计划')).toHaveCount(0)
  await expect(drawer.getByText('已完成', { exact: true }).first()).toBeVisible()
  await expect(drawer.getByText('汇总三个分支与质量标准', { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('tab', { name: '风控与授权' }).click()
  await page.getByRole('button', { name: '编辑当前规则' }).click()
  await page.getByRole('button', { name: '保存为新版本' }).click()
  await expect(page.getByText('规则已保存为新版本，后续执行会重新校验审批')).toBeVisible()
  await page.getByRole('tab', { name: '任务协同' }).click()
  await page.getByRole('textbox', { name: '搜索运营任务' }).fill('E2E 高价值选品')
  await expect(page.locator('.desktop-runs .task-link')).toHaveCount(1)
  await page.getByRole('textbox', { name: '搜索运营任务' }).fill('')
  await expect(page.locator('.el-message')).toHaveCount(0, { timeout: 8000 })
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: 'test-results/ecomops-desktop.png',
    fullPage: true,
    animations: 'disabled',
  })
  await expect(page.getByRole('button', { name: '新建任务', exact: true })).toBeInViewport()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({
    path: 'test-results/ecomops-mobile.png',
    fullPage: true,
    animations: 'disabled',
  })
  await expect
    .poll(async () => page.locator('.mobile-runs .run-card').count(), { timeout: 10_000 })
    .toBeGreaterThanOrEqual(2)
  expect(await page.locator('.app-main').evaluate((node) => node.getBoundingClientRect().x)).toBe(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: '切换导航' }).click()
  const navigation = page.getByRole('dialog', { name: '运营中枢导航' })
  await navigation.locator('summary').filter({ hasText: '系统' }).click()
  await navigation.getByRole('link', { name: '系统设置' }).click()
  await expect(navigation).not.toBeVisible()
  await expect(page.locator('.workspace-bar')).toHaveCount(0)
  await page.setViewportSize({ width: 1280, height: 720 })
  await expect(page.getByRole('link', { name: 'AI 模型配置' })).toBeVisible()
  await expect(page.getByRole('link', { name: '平台连接' }).last()).toBeVisible()
  await expect(page.getByText('建设中', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('link', { name: '风控与授权' })).toBeVisible()
  await page.screenshot({
    path: 'test-results/settings-desktop.png',
    fullPage: true,
    animations: 'disabled',
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({
    path: 'test-results/settings-mobile.png',
    fullPage: true,
    animations: 'disabled',
  })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('link', { name: '风控与授权' }).click()
  await expect(page.getByRole('tab', { name: '风控与授权' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await page.goto('/assets')
  await expect(page.getByRole('heading', { name: '素材 AI 中心' })).toBeVisible()
  await expect(page.getByText('数据更新时间 09:40')).toHaveCount(0)
  await page.locator('.stage-switch').getByText('预览与质检', { exact: true }).click()
  await expect(page.getByRole('radio', { name: '预览与质检' })).toBeChecked()
  await expect(page.getByRole('heading', { name: '版本预览' })).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: 'test-results/assets-mobile.png',
    fullPage: true,
    animations: 'disabled',
  })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.locator('.stage-switch').getByText('生成编辑', { exact: true }).click()
  await expect(page.getByRole('textbox', { name: '生成目标' })).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: 'test-results/assets-medium.png',
    fullPage: true,
    animations: 'disabled',
  })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
})

test('按业务填写预算、退款并复制修订，保留审批与审计', async ({ page }) => {
  await page.goto('/login')
  await page.getByRole('button', { name: '进入工作台' }).click()
  const token = await page.evaluate(() => localStorage.getItem('ops-command-center.token'))
  const headers = { Authorization: `Bearer ${token}` }
  const imported = await page.request.post('/api/v1/ecomops/data/import', {
    headers,
    data: {
      records: [
        {
          kind: 'product',
          key: 'LAYOUT-SKU',
          data: { title: '布局验收收纳盒', currency: 'USD' },
          source: '浏览器布局验收',
          is_demo: true,
        },
        {
          kind: 'supplier',
          key: 'LAYOUT-SUPPLIER',
          data: { name: '验收供应商' },
          source: '浏览器布局验收',
          is_demo: true,
        },
      ],
    },
  })
  expect(imported.ok()).toBe(true)
  const initialized = await page.request.post('/api/v1/ecomops/runs', {
    headers,
    data: {
      workflow: 'initialization',
      title: '布局验收初始化',
      idempotency_key: `layout-init-${Date.now()}`,
      input: {},
    },
  })
  expect(initialized.ok()).toBe(true)
  await page.goto('/ecomops')
  const detail = page.getByRole('dialog', { name: '任务协同与人工处置' })
  const create = page.getByRole('dialog', { name: '新建运营任务' })
  for (const item of [
    {
      workflow: '营销方案与预算检查',
      title: '布局验收预算',
      field: '调整后日预算（USD）',
      amount: '150',
      fact: '变动幅度 %',
    },
    {
      workflow: '客服草稿与售后审核',
      title: '布局验收退款',
      field: '退款金额（USD）',
      amount: '100',
      fact: '退款金额 USD',
    },
  ]) {
    await page.getByRole('button', { name: '新建任务', exact: true }).first().click()
    await create
      .locator('.el-select__wrapper')
      .filter({ has: page.getByRole('combobox', { name: '业务流程' }) })
      .click()
    await page.getByRole('option', { name: item.workflow, exact: true }).click()
    await create.getByPlaceholder('可选，默认使用流程名称').fill(item.title)
    await create.getByRole('button', { name: '下一步：填写参数' }).click()
    await expect(create.getByRole('spinbutton', { name: '采购单价（USD）' })).toHaveCount(0)
    if (item.field === '退款金额（USD）') {
      await create
        .locator('.el-select__wrapper')
        .filter({ has: page.getByRole('combobox', { name: '咨询 / 售后类型' }) })
        .click()
      await page.getByRole('option', { name: '退款申请', exact: true }).click()
    }
    await create.getByRole('spinbutton', { name: item.field }).fill(item.amount)
    await create.getByRole('button', { name: '创建并执行任务' }).click()
    await expect(detail.locator('.review-focus')).toContainText(item.fact)
    await detail.locator('.management-section > summary').filter({ hasText: '任务管理' }).click()
    await detail.getByRole('button', { name: '修订输入并新建任务' }).click()
    await expect(create.getByPlaceholder('可选，默认使用流程名称')).toHaveValue(
      `${item.title}（修订）`,
    )
    await create.getByRole('button', { name: '下一步：填写参数' }).click()
    await expect(create.getByRole('spinbutton', { name: item.field })).toHaveValue(
      Number(item.amount).toFixed(2),
    )
    await create.getByRole('button', { name: '取消', exact: true }).click()
    await page.getByRole('textbox', { name: '搜索运营任务' }).fill(item.title)
    await page.locator('.desktop-runs .task-link').click()
    await detail
      .getByPlaceholder('说明核验依据、驳回原因或人工接管计划')
      .fill('布局验收驳回，保留本地审核与审计记录')
    await detail.getByRole('button', { name: '驳回任务', exact: true }).click()
    await expect(detail.locator('.detail-heading')).toContainText('已驳回')
    await page.keyboard.press('Escape')
    await page.getByRole('textbox', { name: '搜索运营任务' }).fill('')
  }
  const response = await page.request.get('/api/v1/ecomops/overview', { headers })
  const overview = (await response.json()) as EcomOverview
  const run = overview.runs.find((item) => item.title === '布局验收退款')!
  const runResponse = await page.request.get(`/api/v1/ecomops/runs/${run.id}`, { headers })
  const saved = (await runResponse.json()) as EcomRun
  expect(saved.input?.refund_amount).toBe(100)
  expect(
    saved.audits?.some((audit) => audit.action === 'reject' && audit.note.includes('布局验收驳回')),
  ).toBe(true)
})
