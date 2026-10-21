import { expect, test, type Page } from '@playwright/test'

import { navigateTo } from './navigation'

async function enterWorkbench(page: Page) {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
}

test.describe('演示业务模块验收矩阵', () => {
  test('商品中心支持详情查看和批量任务闭环', async ({ page }) => {
    await enterWorkbench(page)
    await navigateTo(page, '商品与库存')

    await expect(page).toHaveURL(/\/products$/)
    await expect(page.getByRole('heading', { name: '跨平台商品运营台账' })).toBeVisible()
    await expect(page.getByPlaceholder('搜索 SKU / 商品标题')).toBeVisible()
    const rows = page.locator('.el-table__body-wrapper tbody tr')
    await expect(rows.first()).toBeVisible()

    await page.getByRole('button', { name: '查看商品详情' }).first().click()
    const productDrawer = page.locator('.product-drawer')
    await expect(productDrawer).toBeVisible()
    await expect(productDrawer.getByText('基础规格')).toBeVisible()
    await expect(productDrawer.getByText('AI 优化建议')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(productDrawer).toBeHidden()

    await rows
      .first()
      .locator('input[type="checkbox"]')
      .evaluate((checkbox) => (checkbox as HTMLInputElement).click())
    await expect(page.getByText('已选择 1 个商品')).toBeVisible()
    await page.getByRole('button', { name: '同步' }).click()
    await expect(page.getByRole('dialog')).toContainText('同步确认')
    await page.getByRole('dialog').getByRole('button', { name: '确认创建任务' }).click()

    await expect(page.getByText('演示批量任务已创建')).toBeVisible()
    await expect(page.getByText('批量任务 · 演示数据')).toBeVisible()
  })

  test('订单售后支持脱敏详情和可审计处置任务', async ({ page }) => {
    await enterWorkbench(page)
    await navigateTo(page, '订单与客户服务')

    await expect(page).toHaveURL(/\/orders$/)
    await expect(page.getByRole('heading', { name: 'SLA 风险处置台' })).toBeVisible()
    await expect(page.getByText(/敏感信息已脱敏/)).toBeVisible()
    await page.locator('.order-link').first().click()

    const orderDrawer = page.locator('.order-drawer')
    await expect(orderDrawer).toBeVisible()
    await expect(orderDrawer.getByText('单订单操作')).toBeVisible()
    await expect(orderDrawer.getByText('AI 回复建议')).toBeVisible()
    await expect(orderDrawer.getByText(/买家姓名.*已脱敏/)).toBeVisible()

    const followUpButton = orderDrawer.getByRole('button', { name: '标记跟进' })
    await expect(followUpButton).toBeVisible()
    if (await followUpButton.isEnabled()) {
      await followUpButton.click()
      await expect(page.getByRole('dialog')).toContainText('确认对 1 个订单执行')
      await page.getByRole('dialog').getByRole('button', { name: '创建任务' }).click()
      await expect(page.getByText('任务已进入演示队列，可在页面查看执行进度。')).toBeVisible()
    }
  })

  test('店铺与平台切换会更新统一工作区范围并支持保存分组', async ({ page }) => {
    await enterWorkbench(page)

    const platformSelect = page.locator('.workspace-bar .platform-select .el-select__wrapper')
    await platformSelect.click()
    await page.getByRole('option', { name: '淘宝' }).click()
    await expect(page.locator('.workspace-bar__scope')).toContainText('淘宝')
    await expect(page.locator('.workspace-bar__scope')).toContainText('柔肤旗舰店')

    await page.getByRole('button', { name: '保存当前范围' }).click()
    const groupDialog = page.getByRole('dialog', { name: '保存常用店铺分组' })
    await expect(groupDialog).toBeVisible()
    await groupDialog.getByPlaceholder('例如：双 11 主推店铺').fill('淘宝主推店铺')
    await groupDialog.getByRole('button', { name: '保存' }).click()
    await expect(page.getByRole('button', { name: '常用分组' })).toBeVisible()

    await navigateTo(page, '商品与库存')
    await expect(page).toHaveURL(/\/products$/)
    await expect(page.getByRole('heading', { name: '跨平台商品运营台账' })).toBeVisible()
    await expect(page.getByText('柔肤旗舰店').first()).toBeVisible()
  })

  test('评论舆情支持差评工单保存草稿而不自动发送', async ({ page }) => {
    await enterWorkbench(page)
    await page.goto('/reviews')

    await expect(page).toHaveURL(/\/reviews$/)
    await expect(page.getByRole('heading', { name: '评论风险监控台' })).toBeVisible()
    await expect(page.getByRole('heading', { name: '评价明细' })).toBeVisible()
    await expect(page.getByRole('heading', { name: '舆情词云' })).toBeVisible()

    const negativeItem = page.locator('.review-item--negative').first()
    await expect(negativeItem).toBeVisible()
    await negativeItem.getByRole('button', { name: /创建工单|处理工单/ }).click()

    const ticketDrawer = page.getByRole('dialog', { name: '差评工单处置' })
    await expect(ticketDrawer).toBeVisible()
    await expect(
      ticketDrawer.getByText('回复内容只保存为草稿，不会自动发送到任何平台。'),
    ).toBeVisible()
    await ticketDrawer
      .getByPlaceholder('输入或套用模板生成待确认回复')
      .fill('您好，我们已记录问题并安排专人跟进。')
    await ticketDrawer
      .getByPlaceholder('记录联系结果、补发或退款处理')
      .fill('已联系仓配团队核查发货时效。')
    await ticketDrawer.getByRole('button', { name: '保存工单' }).click()

    await expect(page.getByText('差评工单已更新（演示数据）')).toBeVisible()
  })
})
