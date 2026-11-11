# Blibli Store Review & Sentiment Analyzer

Collect buyer reviews from any [Blibli](https://www.blibli.com) store —
your own or a competitor's — as clean text ready to feed straight into an
LLM for sentiment analysis, complaint clustering, or product-strength
mining.

Point it at a store and it returns the written reviews plus a summary of
the store's **entire** review base: rating histogram, negative share, and
Blibli's own topic breakdown (quality, price, shipping, packaging, service,
authenticity).

No login, no API key. HTTP-only — no browser.

## What makes it useful

**It captures the complaints.** Blibli only exposes ~600 reviews per query,
and these stores run ~98% positive — so a naive scrape returns a wall of
5-star praise. This actor sweeps each star rating as its own query, which
on the store used for testing returned **292 of the 294 one-star reviews
that exist**, out of a base of 68,842. Negative feedback is the scarce,
valuable part, and it is what you actually get.

**It only returns reviews with words.** About **half** of Blibli's reviews
are star-only ratings with no text — useless for sentiment work. Those are
filtered out server-side, so your run (and your bill) is spent on reviews
an AI can actually read.

**The summary row alone may answer the question.** One cheap record per
store carries the topic counts across the whole review base — "what do
customers keep bringing up" without spending a single AI token.

## Input

```json
{
  "storeUrls": [
    "https://www.blibli.com/merchant/colgate-palmolive-indonesia-flagship-store/COP-60023",
    "COP-60023",
    "https://www.blibli.com/p/sandisk-ultra-microsdxc-64gb/ps--BLL-70058-00122"
  ],
  "coverage": "deep",
  "sortBy": "LATEST",
  "onlyWithText": true
}
```

`storeUrls` accepts a store URL, a bare store code (`COP-60023`), a product
URL, a bare product SKU, or `brand:<name>` — mixed freely, so your store
and your competitors' go in one run.

| Field | Description |
| --- | --- |
| `coverage` | `standard` (one sweep, ~600), **`deep`** (per-rating sweeps — captures nearly all negatives), `maximum` (adds per-topic sweeps) |
| `sortBy` | `LATEST`, `POPULAR`, `OLDEST`, `HIGHEST`, `LOWEST` |
| `onlyWithText` | Skip star-only ratings. On by default |
| `onlyWithMedia` | Only reviews with buyer photos/videos |
| `minRating` | Keep only reviews at or above N stars (0 = off) |
| `maxReviewsPerTarget` | Cap per store/product (0 = no limit) |
| `includeSummary` | Emit the store summary row. On by default |
| `productBreakdown` | Also sweep each product separately — each has its own ~600-review window |
| `maxProductsPerStore` | Cap for `productBreakdown` |
| `proxyConfiguration` | Apify Residential + country `ID` recommended |

## Output

Two record shapes, discriminated by `recordType`.

**`REVIEW`** — one per review, Blibli's own fields passed through verbatim
plus flattened fields for AI pipelines:

```json
{
  "recordType": "REVIEW",
  "id": "74f5b34c-6db2-41c0-b22e-bcb4de44ab56",
  "rating": 2,
  "reviewText": "Gak dapet kantongan tas IU nya",
  "ratingPolarity": "negative",
  "reviewLength": 32,
  "hasText": true,
  "verifiedBuyer": true,
  "productSku": "COP-60023-01124",
  "merchantName": "Colgate Palmolive Indonesia Flagship Store",
  "createdAtIso": "2026-07-27T14:39:13Z",
  "imageCount": 0,
  "videoCount": 0,
  "matchedTopic": null,
  "matchedRatingFilter": "1"
}
```

**`STORE_SUMMARY`** — one per store, describing the *entire* review base:

```json
{
  "recordType": "STORE_SUMMARY",
  "merchantName": "Colgate Palmolive Indonesia Flagship Store",
  "totalReviews": 68842,
  "commentCount": 32843,
  "averageRating": 4.9,
  "negativeSharePercent": 0.72,
  "positiveSharePercent": 98.48,
  "ratingCounts": { "1": 294, "2": 203, "3": 549, "4": 2817, "5": 64979 },
  "topicCounts": {
    "QUALITY": 1181, "PRICE": 1006, "SHIPMENT": 935,
    "PACKAGING": 627, "SERVICE": 220, "ORIGINALITY": 213, "GENERIC": 776
  }
}
```

`ratingPolarity` is derived directly from the star rating (`negative` for
1–2, `neutral` 3, `positive` 4–5). It is **not** natural-language sentiment
analysis — it is a cheap pre-filter so you can spend LLM tokens only on the
reviews that matter.

`matchedTopic` is set when a review was surfaced by a topic sweep, meaning
Blibli itself classifies it under that topic.

## Feeding it to an AI

Filter to `ratingPolarity == "negative"` and `hasText == true`, then group
by `productSku`, and pass `reviewText` to your model. The `topicCounts` in
the summary row tell you which themes to expect before you start.

## Known limits

- **~600 reviews per query slice.** A store with 68k reviews cannot be
  extracted in full. `deep` and `maximum` coverage widen the sample, and
  `productBreakdown` opens a separate window per product — but the summary
  row is what describes the complete base.
- **Reviews are in Indonesian.** Use a multilingual sentiment model.
- **Reviewer names arrive masked** by Blibli (`M***a`). This actor does not
  attempt to unmask them, and returns only reviews Blibli shows publicly.
- `brand:<name>` targets are accepted but returned no results for every
  brand tried during recon.
- Roughly half of all reviews have no text; with `onlyWithText` on (the
  default) those never reach your dataset.

## Reliability

Blibli sits behind **Cloudflare**. The actor clears it HTTP-only with TLS
impersonation plus the `Referer` header Cloudflare's rule requires — no
browser, no CAPTCHA solver. On a block it retries with exponential backoff
while rotating both the TLS fingerprint and, when a proxy is configured,
the egress IP.

A failing target never sinks the run: it emits an `ERROR` record with
`_error` and `_errorDetail` and the remaining targets continue.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the full endpoint
analysis, including the decoy endpoint that reports zero reviews for
products that have hundreds.
