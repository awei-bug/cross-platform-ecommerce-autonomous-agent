import { expect, test } from '@playwright/test'

import { navigateTo, openNavigationGroup } from './navigation'

test.describe('演示工作台关键路径', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.evaluate(() => localStorage.clear())
    await page.reload()
  })

  test('可以登录并进入运营总览', async ({ page }) => {
    await expect(page.getByRole('heading', { name: '登录运营中枢' })).toBeVisible()
    await page.getByRole('button', { name: '进入工作台' }).click()

    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByRole('heading', { name: '今日经营作战面板' })).toBeVisible()
    await expect(page.getByText('当前工作区')).toBeVisible()
    await expect(page.getByText('演示数据').first()).toBeVisible()
  })

  test('可以从总览进入报表并完成导出和复盘笔记流程', async ({ page }) => {
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page).toHaveURL(/\/dashboard$/)
    await navigateTo(page, '数据与复盘')

    await expect(page).toHaveURL(/\/reports$/)
    await expect(page.getByRole('heading', { name: '经营复盘工作台' })).toBeVisible()
    await expect(page.getByRole('button', { name: /运营周报/ })).toBeVisible()
    await expect(
      page.getByText('当前为演示数据，导出任务会记录流程但不会生成真实 Excel/PDF 文件。'),
    ).toBeVisible()
    await expect(page.getByRole('heading', { name: '主体明细' })).toBeVisible()

    await page.getByRole('button', { name: '广告报表' }).click()
    await expect(page.getByRole('heading', { name: '广告报表 · 趋势概览' })).toBeVisible()
    await expect(page.getByText('广告消耗').first()).toBeVisible()

    const download = page.waitForEvent('download')
    await page.getByRole('button', { name: '导出 PDF' }).click()
    expect((await download).suggestedFilename()).toMatch(/\.pdf$/)
    await expect(page.getByText('PDF 报表已生成并下载')).toBeVisible()

    await page.getByRole('button', { name: '添加复盘笔记' }).first().click()
    await expect(page.getByRole('dialog', { name: '添加复盘笔记' })).toBeVisible()
    await page.getByLabel('笔记标题').fill('广告投放复盘')
    await page.getByLabel('复盘结论').fill('广告报表已完成关键指标核对')
    await page.getByLabel('后续行动计划').fill('继续观察高 ROI 计划')
    await page
      .getByRole('dialog', { name: '添加复盘笔记' })
      .getByRole('button', { name: '保存笔记' })
      .click()

    await expect(page.getByText('复盘笔记已保存（演示数据）')).toBeVisible()
    await expect(page.getByText('广告投放复盘').last()).toBeVisible()
  })

  test('导航包含六个已完成业务页面', async ({ page }) => {
    await page.getByRole('button', { name: '进入工作台' }).click()
    await expect(page).toHaveURL(/\/dashboard$/)

    for (const label of [
      '运营总览',
      '自动化中心',
      '商品与库存',
      '订单与客户服务',
      '营销与广告',
      '内容与素材',
      '数据与复盘',
      '系统设置',
    ]) {
      await openNavigationGroup(page, label)
      await expect(page.getByRole('link', { name: label })).toBeVisible()
    }
  })
})
