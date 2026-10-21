// Pure extraction: never interpret an aggregate/variant price as a single offer.
export function extractProduct({ jsonld, text, url }) {
  const products = []
  function visit(value) {
    if (Array.isArray(value)) return value.forEach(visit)
    if (!value || typeof value !== 'object') return
    const types = [value['@type']].flat()
    if (types.includes('Product')) products.push(value)
    if (value['@graph']) visit(value['@graph'])
  }
  for (const script of jsonld) {
    try {
      visit(JSON.parse(script))
    } catch {
      /* Invalid metadata is not evidence. */
    }
  }
  if (products.length !== 1) throw new Error('需要唯一 Product 结构，页面或商品变体需人工确认')
  const product = products[0]
  if (!product.name || !text.includes(String(product.name).split(' ')[0])) {
    throw new Error('商品结构与可见页面不匹配')
  }
  if (product.url && new URL(product.url, url).pathname !== new URL(url).pathname) {
    throw new Error('商品结构指向其他页面')
  }
  const offers = [product.offers].flat().filter(Boolean)
  const offer = offers.length === 1 && offers[0]['@type'] === 'Offer' ? offers[0] : null
  const rawPrice = offer?.price ?? offer?.priceSpecification?.price
  const numeric =
    typeof rawPrice === 'number' || (typeof rawPrice === 'string' && /^\d+(\.\d+)?$/.test(rawPrice))
      ? Number(rawPrice)
      : NaN
  const currency = offer?.priceCurrency ?? offer?.priceSpecification?.priceCurrency
  const normalizedText = text.replace(/[\s,]/g, '')
  const fixed = Number.isFinite(numeric) ? numeric.toFixed(2) : ''
  // Avoid substring matches (4.99 inside 14.99); require an actual numeric token.
  const amounts = normalizedText.match(/\d+(?:\.\d+)?/g) ?? []
  const visible = amounts.some((value) => Number(value) === numeric)
  const validPrice = numeric > 0 && Number.isFinite(numeric) && visible
  const specs = {}
  for (const key of ['sku', 'mpn', 'material', 'color', 'width', 'height', 'depth', 'size']) {
    const value = product[key]
    if (typeof value === 'string' || typeof value === 'number')
      specs[key] = String(value).slice(0, 1000)
    else if (value?.value !== undefined)
      specs[key] = `${value.value} ${value.unitText ?? value.unitCode ?? ''}`.trim().slice(0, 1000)
  }
  for (const item of [product.additionalProperty].flat().filter(Boolean)) {
    if (item.name && item.value !== undefined && Object.keys(specs).length < 30) {
      specs[String(item.name).slice(0, 100)] = String(item.value).slice(0, 1000)
    }
  }
  return {
    source_url: url,
    title: String(product.name).slice(0, 500),
    description: String(product.description ?? '').slice(0, 5000),
    price: validPrice ? numeric : null,
    currency: /^[A-Z]{3}$/.test(currency ?? '') ? currency : null,
    specifications: specs,
    price_evidence: validPrice
      ? `schema.org Product.offers.price=${fixed}; rendered page contains ${fixed}`
      : '',
    missing_fields: [
      ...(!validPrice ? ['price: missing, ambiguous or not visible'] : []),
      ...(!/^[A-Z]{3}$/.test(currency ?? '') ? ['currency'] : []),
      'sales',
      'supplier_quote',
      'shipping_and_tax',
      'verified_availability',
      'review_pain_points',
    ],
  }
}

export function extractAmazonProduct(snapshot) {
  const { url, title, asin, prices, specifications, description, popularity_claim } = snapshot
  const host = new URL(url).hostname
  const urlAsin = new URL(url).pathname.match(/\/dp\/([A-Z0-9]{10})/)?.[1]
  if (
    !['www.amazon.com', 'amazon.com'].includes(host) ||
    !title?.trim() ||
    !asin ||
    asin !== urlAsin
  ) {
    throw new Error('Amazon 商品身份不明确，需人工确认')
  }
  const distinct = [
    ...new Set(
      prices.map((p) => p.replaceAll(',', '').trim()).filter((p) => /^\$\d+\.\d{2}$/.test(p)),
    ),
  ]
  const price = distinct.length === 1 ? Number(distinct[0].slice(1)) : null
  return {
    source_url: url,
    title: title.trim().slice(0, 500),
    price: price > 0 ? price : null,
    currency: price > 0 ? 'USD' : null,
    specifications,
    description: description.slice(0, 5000),
    price_evidence:
      price > 0 ? `Amazon.com selected ASIN ${asin}; visible priceToPay ${distinct[0]}` : '',
    capture_method: 'browser_amazon_dom',
    popularity_claim: popularity_claim?.trim().slice(0, 300) || null,
    missing_fields: [
      ...(!(price > 0) ? ['price', 'currency'] : []),
      'exact_sales',
      'supplier_quote',
      'shipping_and_tax',
      'verified_availability',
      'review_pain_points',
    ],
  }
}
