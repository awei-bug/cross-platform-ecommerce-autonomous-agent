import { chromium } from '../frontend/node_modules/@playwright/test/index.mjs'
import fs from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const browser = await chromium.launch({
  headless: true,
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
})
try {
  const results = {}
  for (const [name, viewport] of Object.entries({
    desktop: { width: 1920, height: 1080 },
    mobile: { width: 390, height: 844 },
  })) {
    const page = await browser.newPage({ viewport })
    await page.goto('http://127.0.0.1:5173/login', { waitUntil: 'networkidle' })
    await page.evaluate(() => localStorage.clear())
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('button', { name: '进入工作台' }).click()
    await page.waitForURL(/\/dashboard$/)
    await page.getByRole('heading', { name: '今日经营作战面板' }).waitFor()
    await page.waitForTimeout(1200)
    const screenshotPath = fileURLToPath(new URL(`./typography-${name}.png`, import.meta.url))
    await page.screenshot({ path: screenshotPath, fullPage: true })
    results[name] = {
      screenshot: screenshotPath,
      viewport,
      bodyScrollWidth: await page.evaluate(() => document.body.scrollWidth),
      bodyClientWidth: await page.evaluate(() => document.body.clientWidth),
      samples: await page.evaluate(() => {
        const selectors = [
          'body',
          '.context-copy span',
          '.context-copy strong',
          '.page-heading h1',
          '.page-heading p',
          '.metric-card__label',
          '.risk-list__copy small',
          '.risk-list__copy em',
        ]
        return Object.fromEntries(
          selectors.map((selector) => {
            const el = document.querySelector(selector)
            if (!el) return [selector, null]
            const css = getComputedStyle(el)
            return [
              selector,
              { fontSize: css.fontSize, lineHeight: css.lineHeight, color: css.color },
            ]
          }),
        )
      }),
    }
    await page.close()
  }
  await fs.writeFile(
    new URL('./typography-check.json', import.meta.url),
    JSON.stringify(results, null, 2),
  )
  console.log(JSON.stringify(results, null, 2))
} finally {
  await browser.close()
}
