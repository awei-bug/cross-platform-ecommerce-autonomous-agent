import { expect, test, type Page, type Route } from '@playwright/test'

const now = '2026-09-13T09:40:00+08:00'

async function enterWorkbench(page: Page) {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await page.getByRole('button', { name: '进入工作台' }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
}

async function failUntilRetry(
  route: Route,
  calls: { count: number },
  detail: string,
  recovery: unknown,
) {
  calls.count += 1

  if (calls.count <= 2) {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail }),
    })
    return
  }

  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(recovery),
  })
}

function recoveryProducts() {
  return {
    items: [
      {
        id: 'product-recovery',
        sku: 'SKU-RECOVERY',
        title: '重试恢复商品',
        platform: 'douyin',
        platform_label: '抖音',
        shop_id: 'shop-douyin-main',
        shop_name: '抖音旗舰店',
        status: 'online',
        risk: 'normal',
        risk_labels: [],
        price: 99,
        cost: 40,
        stock: 20,
        sales_7d: 10,
        revenue_7d: 990,
        conversion_rate: 0.12,
        updated_at: now,
      },
    ],
    pagination: { page: 1, page_size: 10, total: 1 },
    summary: { total: 1, critical: 0, warning: 0, offline: 0, low_stock: 0 },
    data_updated_at: now,
    is_demo: true,
  }
}

function recoveryOrders() {
  return {
    items: [
      {
        id: 'order-recovery',
        order_no: 'RECOVERY-ORDER-001',
        platform: 'douyin',
        platform_label: '抖音',
        shop_id: 'shop-douyin-main',
        shop_name: '抖音旗舰店',
        buyer_masked: '测试买家',
        item_title: '重试恢复订单',
        sku: 'SKU-RECOVERY',
        quantity: 1,
        amount: 99,
        order_status: 'pending_shipment',
        after_sale_status: 'none',
        risk: 'normal',
        risk_reasons: [],
        sla_deadline: now,
        remaining_minutes: 120,
        estimated_loss: 0,
        created_at: now,
        updated_at: now,
        sensitive_data_masked: true,
      },
    ],
    pagination: { page: 1, page_size: 10, total: 1 },
    summary: {
      total: 1,
      critical: 0,
      overdue: 0,
      due_within_2h: 0,
      pending_after_sale: 0,
      pending_shipment: 1,
      estimated_loss: 0,
    },
    data_updated_at: now,
    is_demo: true,
  }
}

function emptyProducts() {
  return {
    items: [],
    pagination: { page: 1, page_size: 10, total: 0 },
    summary: { total: 0, critical: 0, warning: 0, offline: 0, low_stock: 0 },
    data_updated_at: now,
    is_demo: true,
  }
}

function emptyOrders() {
  return {
    items: [],
    pagination: { page: 1, page_size: 10, total: 0 },
    summary: {
      total: 0,
      critical: 0,
      overdue: 0,
      due_within_2h: 0,
      pending_after_sale: 0,
      pending_shipment: 0,
      estimated_loss: 0,
    },
    data_updated_at: now,
    is_demo: true,
  }
}

function emptyReviews() {
  return {
    products: [],
    reviews: [],
    tickets: [],
    words: [],
    templates: [],
    summary: {
      total: 0,
      positive: 0,
      neutral: 0,
      negative: 0,
      open_tickets: 0,
      monitored_products: 0,
    },
    data_updated_at: now,
    is_demo: true,
  }
}

test.describe('演示环境异常、空状态与重试验收', () => {
  test('商品列表接口失败后可以通过重试恢复', async ({ page }) => {
    const calls = { count: 0 }
    await enterWorkbench(page)
    await page.route('**/api/v1/products**', (route) =>
      failUntilRetry(route, calls, '商品接口暂时不可用', recoveryProducts()),
    )
    await page.getByRole('link', { name: '商品与库存' }).click()

    await expect(page.getByText('商品数据加载失败，请重试。')).toBeVisible()
    await expect.poll(() => calls.count).toBe(2)
    await page.getByRole('button', { name: '刷新' }).click()
    await expect(page.locator('.el-table__body-wrapper tbody tr').first()).toBeVisible()
    expect(calls.count).toBe(3)
  })

  test('订单列表接口失败后可以通过重试恢复', async ({ page }) => {
    const calls = { count: 0 }
    await enterWorkbench(page)
    await page.route('**/api/v1/orders**', (route) =>
      failUntilRetry(route, calls, '订单接口暂时不可用', recoveryOrders()),
    )
    await page.getByRole('link', { name: '订单与客户服务' }).click()

    await expect(page.getByText('订单列表加载失败，请检查后端服务后重试。')).toBeVisible()
    await expect.poll(() => calls.count).toBe(2)
    await page.getByRole('button', { name: '刷新' }).click()
    await expect(page.getByRole('heading', { name: 'SLA 风险处置台' })).toBeVisible()
    await expect(
      page.locator('.orders-workbench .el-table__body-wrapper tbody tr').first(),
    ).toBeVisible()
    expect(calls.count).toBe(3)
  })

  test('评论和报表数据失败时会展示可操作的错误状态', async ({ page }) => {
    await enterWorkbench(page)
    await page.route('**/api/v1/reviews**', (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '评论接口暂时不可用' }),
      }),
    )
    await page.goto('/reviews')
    await expect(page.getByText('评论数据加载失败，请重试。')).toBeVisible()
    await expect(page.getByRole('button', { name: '重试加载' })).toBeVisible()

    await page.unroute('**/api/v1/reviews**')
    await page.route('**/api/v1/reports**', (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '报表接口暂时不可用' }),
      }),
    )
    await page.getByRole('link', { name: '数据与复盘' }).click()
    await expect(page.getByText('报表数据加载失败，请重试。')).toBeVisible()
    await expect(page.getByRole('button', { name: '重试加载' })).toBeVisible()
  })

  test('无匹配商品和评论时显示空状态，重置筛选后恢复', async ({ page }) => {
    await enterWorkbench(page)
    await page.route('**/api/v1/products**', async (route) => {
      const url = new URL(route.request().url())
      if (url.searchParams.get('q') === '不存在的商品') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(emptyProducts()),
        })
        return
      }
      await route.continue()
    })
    await page.getByRole('link', { name: '商品与库存' }).click()
    const productSearch = page.getByPlaceholder('搜索 SKU / 商品标题')
    await productSearch.fill('不存在的商品')
    await productSearch.press('Enter')
    await expect(page.getByText('没有符合条件的商品')).toBeVisible()
    await page.getByRole('button', { name: '重置筛选' }).click()
    await expect(page.locator('.el-table__body-wrapper tbody tr').first()).toBeVisible()

    await page.goto('/reviews')
    await page.route('**/api/v1/reviews**', async (route) => {
      const url = new URL(route.request().url())
      if (url.searchParams.get('q') === '不存在的评价') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(emptyReviews()),
        })
        return
      }
      await route.continue()
    })
    await page.goto('/reviews')
    const reviewSearch = page.getByPlaceholder('搜索评价、商品或关键词')
    await reviewSearch.fill('不存在的评价')
    await expect(page.getByText('没有匹配评价')).toBeVisible()
    await page.getByRole('button', { name: '重置', exact: true }).click()
    await expect(page.locator('.review-item').first()).toBeVisible()
  })

  test('订单无匹配时显示空状态，重置筛选后恢复', async ({ page }) => {
    await enterWorkbench(page)
    await page.route('**/api/v1/orders**', async (route) => {
      const url = new URL(route.request().url())
      if (url.searchParams.get('q') === '不存在的订单') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(emptyOrders()),
        })
        return
      }
      await route.continue()
    })
    await page.getByRole('link', { name: '订单与客户服务' }).click()
    const orderSearch = page.getByPlaceholder('订单号 / 买家 / 商品 / SKU')
    await orderSearch.fill('不存在的订单')
    await orderSearch.press('Enter')
    await expect(page.getByText('没有匹配的订单')).toBeVisible()
    await page.getByRole('button', { name: '重置', exact: true }).click()
    await expect(
      page.locator('.orders-workbench .el-table__body-wrapper tbody tr').first(),
    ).toBeVisible()
  })

  test('商品批量任务创建失败时会保留页面并提示可恢复', async ({ page }) => {
    await enterWorkbench(page)
    await page.route('**/api/v1/products/batch-actions', (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '批量任务服务暂时不可用' }),
      }),
    )
    await page.getByRole('link', { name: '商品与库存' }).click()
    const rows = page.locator('.el-table__body-wrapper tbody tr')
    await rows
      .first()
      .locator('input[type="checkbox"]')
      .evaluate((checkbox) => (checkbox as HTMLInputElement).click())
    await page.getByRole('button', { name: '同步' }).click()
    await page.getByRole('dialog').getByRole('button', { name: '确认创建任务' }).click()

    await expect(page.getByText('批量任务服务暂时不可用')).toBeVisible()
    await expect(page.getByRole('heading', { name: '跨平台商品运营台账' })).toBeVisible()
  })

  test('商品批量任务部分失败后可以只重试失败项', async ({ page }) => {
    await enterWorkbench(page)
    await page.getByRole('link', { name: '商品与库存' }).click()
    const rows = page.locator('.el-table__body-wrapper tbody tr')
    for (const index of [0, 1, 2, 3]) {
      await rows
        .nth(index)
        .locator('input[type="checkbox"]')
        .evaluate((checkbox) => (checkbox as HTMLInputElement).click())
    }
    await page.getByRole('button', { name: '同步' }).click()
    await page.getByRole('dialog').getByRole('button', { name: '确认创建任务' }).click()

    const job = page.locator('.job-progress')
    await expect(job).toContainText('部分成功')
    await expect(job).toContainText('失败 1')
    await job.getByRole('button', { name: '重试失败项' }).click()
    await expect(page.getByRole('dialog')).toContainText('立即同步确认')
    await page.getByRole('dialog').getByRole('button', { name: '确认创建任务' }).click()
    await expect(job).toContainText('全部成功')
    await expect(job).toContainText('失败 0')
  })

  test('报表导出接口失败时提示错误且不伪装成成功', async ({ page }) => {
    await enterWorkbench(page)
    await page.getByRole('link', { name: '数据与复盘' }).click()
    await page.route('**/api/v1/reports/exports**', (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '导出服务暂时不可用' }),
      }),
    )
    await page.getByRole('button', { name: '导出 PDF' }).click()
    await expect(page.getByText('导出服务暂时不可用')).toBeVisible()
    await expect(page.getByText('PDF 导出任务已完成（演示数据）')).toHaveCount(0)
  })
})
