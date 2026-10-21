import assert from 'node:assert/strict'
import test from 'node:test'
import { extractAmazonProduct, extractProduct } from './research-extractor.mjs'

const product = {
  '@type': 'Product',
  name: 'Storage box',
  color: 'white',
  offers: { '@type': 'Offer', price: '4.99', priceCurrency: 'USD' },
  review: [{ author: { name: 'Private Person' } }],
}
const run = (p = product, text = 'Storage box $4.99') =>
  extractProduct({
    jsonld: [JSON.stringify({ '@graph': [p] })],
    text,
    url: 'https://example.com/product',
  })
test('extracts a visible single offer, specifications; does not retain personal review data', () => {
  const result = run()
  assert.equal(result.price, 4.99)
  assert.equal(result.currency, 'USD')
  assert.equal(result.specifications.color, 'white')
  assert.ok(!JSON.stringify(result).includes('Private Person'))
  assert.ok(result.missing_fields.includes('sales'))
})
test('does not confuse aggregate prices, ambiguous variants, and recommendation products', () => {
  assert.equal(
    run({ ...product, offers: { '@type': 'AggregateOffer', lowPrice: 4.99 } }).price,
    null,
  )
  assert.equal(run({ ...product, offers: [product.offers, product.offers] }).price, null)
  assert.throws(() => run({ ...product, url: 'https://example.com/other' }))
})
test('does not mistake 14.99 for 4.99 or accept unrendered prices', () => {
  assert.equal(run(product, 'Storage box $14.99').price, null)
  assert.equal(run(product, 'Storage box sold out').price, null)
  assert.equal(run({ ...product, offers: { ...product.offers, price: '' } }).price, null)
})
test('rejects missing/duplicate Product metadata and title mismatch', () => {
  assert.throws(() =>
    extractProduct({ jsonld: ['not json'], text: '', url: 'https://example.com' }),
  )
  assert.throws(() => run(product, 'Another product $4.99'))
})
test('Amazon selected ASIN and visible offer are required, without parsing alternative prices', () => {
  const data = {
    url: 'https://www.amazon.com/dp/B08QRFZ6TH/',
    asin: 'B08QRFZ6TH',
    title: 'Curtain',
    prices: ['$8.95', '$8.95'],
    specifications: { size: '72x72' },
    description: '',
    popularity_claim: '90K+ bought in past month',
  }
  assert.equal(extractAmazonProduct(data).price, 8.95)
  assert.equal(extractAmazonProduct(data).popularity_claim, '90K+ bought in past month')
  assert.equal(extractAmazonProduct({ ...data, prices: ['$8.95', '$9.99'] }).price, null)
  assert.throws(() => extractAmazonProduct({ ...data, asin: 'OTHERASIN0' }))
})
