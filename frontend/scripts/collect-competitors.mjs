import { createHash } from 'node:crypto'
import { existsSync } from 'node:fs'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { isIP } from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { extractAmazonProduct, extractProduct } from './research-extractor.mjs'

const options = new Map()
for (let i = 2; i < process.argv.length; i++) {
  const key = process.argv[i]
  if (key === '--headed') options.set(key, true)
  else options.set(key, process.argv[++i])
}
const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const manifest = JSON.parse(
  await readFile(
    options.get('--manifest') ?? path.join(project, 'research/us-storage.example.json'),
    'utf8',
  ),
)
if (
  !/^[a-zA-Z0-9_-]{3,80}$/.test(manifest.collection_id) ||
  !/^[A-Z]{2}$/.test(manifest.country) ||
  typeof manifest.category !== 'string' ||
  !Array.isArray(manifest.urls) ||
  !manifest.urls.length ||
  manifest.urls.length > 50
) {
  throw new Error('采集清单须包含 collection_id、country、category 和1至50个 urls')
}
for (const raw of [...manifest.urls, ...(manifest.ranking_url ? [manifest.ranking_url] : [])]) {
  const url = new URL(raw)
  if (
    !['http:', 'https:'].includes(url.protocol) ||
    url.username ||
    url.password ||
    !url.hostname.includes('.') ||
    url.hostname.endsWith('.local') ||
    url.hostname.endsWith('.localhost') ||
    isIP(url.hostname)
  )
    throw new Error('仅采集公开域名商品页面')
}
const output = path.resolve(
  options.get('--out') ??
    path.join(
      project,
      'backend/data/research',
      manifest.collection_id,
      new Date().toISOString().replace(/[:.]/g, '-'),
    ),
)
await mkdir(output, { recursive: true })
const paths = [
  options.get('--executable-path'),
  process.env.RESEARCH_BROWSER_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].filter(Boolean)
const browser = await chromium.launch({
  executablePath: paths.find((p) => existsSync(p)),
  headless: !options.has('--headed'),
})
const context = await browser.newContext({
  locale: 'en-US',
  viewport: { width: 1440, height: 1000 },
})
const batch = {
  collection_id: manifest.collection_id,
  country: manifest.country,
  category: manifest.category,
  observations: [],
}
const failures = []
const rankings = new Map()
try {
  if (manifest.ranking_url) {
    const rankingPage = await context.newPage()
    try {
      const response = await rankingPage.goto(manifest.ranking_url, {
        waitUntil: 'domcontentloaded',
        timeout: 40000,
      })
      if (!response?.ok()) throw new Error('热销榜未能访问；未据旧排名继续采集')
      await rankingPage
        .locator('[id="gridItemRoot"] .zg-bdg-text')
        .first()
        .waitFor({ timeout: 15000 })
      const cards = rankingPage.locator('[id="gridItemRoot"]')
      for (let i = 0; i < (await cards.count()); i++) {
        const card = cards.nth(i)
        const href = await card.locator('a[href*="/dp/"]').first().getAttribute('href')
        const asin = href?.match(/\/dp\/([A-Z0-9]{10})/)?.[1]
        if (!asin || !manifest.urls.some((url) => url.includes(`/dp/${asin}`))) continue
        const rank = Number((await card.locator('.zg-bdg-text').innerText()).replace('#', ''))
        if (!(rank > 0)) continue
        const filename = `rank-${asin}.png`
        const evidence = await card.screenshot({ path: path.join(output, filename) })
        rankings.set(asin, {
          source_url: rankingPage.url(),
          category: manifest.ranking_category ?? manifest.category,
          rank,
          collected_at: new Date().toISOString(),
          evidence_file: filename,
          evidence_sha256: createHash('sha256').update(evidence).digest('hex'),
        })
      }
    } catch (error) {
      failures.push({ source_url: manifest.ranking_url, error: error.message })
      console.log(`榜单未完成：${error.message}`)
    } finally {
      await writeFile(
        path.join(output, 'rankings.json'),
        JSON.stringify([...rankings.entries()], null, 2),
      )
      await rankingPage.close()
    }
  }
  for (const [index, url] of [...new Set(manifest.urls)].entries()) {
    const page = await context.newPage()
    try {
      const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 40000 })
      if (!response?.ok()) throw new Error(`HTTP ${response?.status() ?? 'unknown'}`)
      await page.locator('h1').first().waitFor({ timeout: 12000 })
      const text = await page.locator('body').innerText()
      const pageTitle = await page.title()
      if (
        /access denied|just a moment|robot check|verify you are human|captcha/i.test(pageTitle) ||
        /verify you are human|enter the characters you see below/i.test(text.slice(0, 1500))
      ) {
        throw new Error('登录/验证码/访问验证：需人工接管，停止采集此页')
      }
      let observation
      if (new URL(page.url()).hostname === 'www.amazon.com' && page.url().includes('/dp/')) {
        const snapshot = await page.evaluate(() => {
          const specs = {}
          for (const row of document.querySelectorAll('#productOverview_feature_div tr')) {
            const cells = row.querySelectorAll('td,th')
            if (cells.length === 2 && Object.keys(specs).length < 25)
              specs[cells[0].innerText.trim().slice(0, 100)] = cells[1].innerText
                .trim()
                .slice(0, 1000)
          }
          // Main selected offer only. Buy-box accordions also contain used/resale prices.
          const prices = [
            ...document.querySelectorAll(
              '#corePriceDisplay_desktop_feature_div .apex-pricetopay-value',
            ),
          ]
            .filter((el) => el.getBoundingClientRect().height > 0)
            .map((el) => {
              const symbol = el.querySelector('.a-price-symbol')?.textContent ?? ''
              const whole = el.querySelector('.a-price-whole')?.textContent ?? ''
              const fraction = el.querySelector('.a-price-fraction')?.textContent ?? ''
              return symbol + whole.replace(/\.$/, '') + '.' + fraction
            })
          return {
            url: location.href,
            title: document.querySelector('#productTitle')?.innerText,
            asin: document.querySelector('#ASIN')?.value,
            prices,
            specifications: specs,
            description: document.querySelector('#feature-bullets')?.innerText ?? '',
            popularity_claim: document.querySelector('#social-proofing-faceout-title-tk_bought')
              ?.innerText,
          }
        })
        observation = extractAmazonProduct(snapshot)
      } else {
        observation = extractProduct({
          jsonld: await page.locator('script[type="application/ld+json"]').allTextContents(),
          text,
          url: page.url(),
        })
      }
      const asin = page.url().match(/\/dp\/([A-Z0-9]{10})/)?.[1]
      if (rankings.has(asin)) observation.ranking = rankings.get(asin)
      else if (manifest.ranking_url)
        observation.missing_fields.push('ranking: not found in observed ranking page')
      const filename = `${String(index + 1).padStart(2, '0')}-${createHash('sha256').update(page.url()).digest('hex').slice(0, 12)}.png`
      const screenshot = await page.screenshot({
        path: path.join(output, filename),
        fullPage: false,
      })
      batch.observations.push({
        ...observation,
        collected_at: new Date().toISOString(),
        evidence_file: filename,
        evidence_sha256: createHash('sha256').update(screenshot).digest('hex'),
      })
      console.log(
        `采集 ${index + 1}: ${observation.title} | ${observation.currency ?? '?'} ${observation.price ?? '缺失'}`,
      )
    } catch (error) {
      failures.push({ source_url: url, error: error.message })
      console.log(`未完成 ${index + 1}: ${error.message}`)
    } finally {
      await page.close()
    }
    if (index < manifest.urls.length - 1) await new Promise((resolve) => setTimeout(resolve, 1500))
  }
} finally {
  await browser.close()
}
await writeFile(path.join(output, 'observations.json'), JSON.stringify(batch, null, 2))
await writeFile(path.join(output, 'failures.json'), JSON.stringify(failures, null, 2))
let analysis
if (options.has('--api') && batch.observations.length) {
  const api = new URL(options.get('--api'))
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(api.hostname))
    throw new Error('--api 只允许本机服务')
  const token = process.env.ECOMOPS_TOKEN
  if (!token) throw new Error('导入需要 ECOMOPS_TOKEN；采集文件已保存')
  async function post(endpoint, body) {
    const response = await fetch(new URL(`/api/v1/ecomops/${endpoint}`, api), {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    })
    if (!response.ok)
      throw new Error(`项目导入/分析失败 HTTP ${response.status()}；证据已保存在 ${output}`)
    return response.json()
  }
  const imported = await post('research/import', batch)
  await writeFile(path.join(output, 'import-result.json'), JSON.stringify(imported, null, 2))
  analysis = await post('research/analyze', {
    collection_id: batch.collection_id,
    country: batch.country,
  })
  await writeFile(path.join(output, 'analysis.json'), JSON.stringify(analysis, null, 2))
  console.log(`已入库：新增 ${imported.inserted}，更新 ${imported.updated}`)
}
const escape = (value) => String(value).replaceAll('|', '\\|').replaceAll('\n', ' ')
const report = [
  `# 公开竞品页面采集：${manifest.category}`,
  '',
  `批次：${batch.collection_id}；目标市场：${batch.country}。成功 ${batch.observations.length} 页，失败 ${failures.length} 页。`,
  '',
  '| 商品 | 页面价格 | 榜单位置 | 规格 | 来源 |',
  '| --- | --- | --- | --- | --- |',
  ...batch.observations.map(
    (o) =>
      `| ${escape(o.title)} | ${o.currency ?? '币种缺失'} ${o.price ?? '价格缺失'} | ${o.ranking ? `${escape(o.ranking.category)} #${o.ranking.rank}` : '未采集'} | ${escape(JSON.stringify(o.specifications))} | ${o.source_url} |`,
  ),
  '',
  '每个页面的截图、SHA256、来源和采集时间见 observations.json。未采集销量、运费、税费、采购报价和完整评论；不把缺失项记成零。',
  '',
  ...(analysis
    ? [
        `成本空间假设：佣金 ${analysis.assumptions.commission_pct}%，广告 ${analysis.assumptions.ad_rate_pct}%，目标毛利 ${analysis.assumptions.target_margin_pct}%。`,
        '',
        ...analysis.candidates.map(
          (c) =>
            `- ${escape(c.title)}：在样本售价下，采购、全程物流、税费、履约、包装及损耗等全部非比例成本合计上限 ${c.currency} ${c.max_fixed_cost_at_target_margin}。`,
        ),
        '',
        ...analysis.limitations,
      ]
    : []),
  ...failures.map((f) => `未完成：${f.source_url} — ${f.error}`),
  '',
].join('\n')
await writeFile(path.join(output, 'report.md'), report)
console.log(`结果：${output}`)
if (
  failures.length ||
  !batch.observations.length ||
  batch.observations.some(
    (o) => o.price === null || !o.currency || (manifest.ranking_url && !o.ranking),
  )
)
  process.exitCode = 2
