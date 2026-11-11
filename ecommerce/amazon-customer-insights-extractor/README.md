# Amazon Customer Insights & Aspect Sentiment

Give it ASINs, get back **what customers actually talk about** — every aspect
Amazon publishes, with its positive/negative mention split and Amazon's
one-sentence verdict on that aspect, plus the product-level AI review
summary.

The negative and mixed aspects are the useful part: they are the questions a
listing has failed to answer. That is your FAQ section and your SEO copy,
taken straight from a competitor's own review base.

No login, no API key. HTTP-only — no browser.

## Note on Amazon Q&A

If you came looking for a **Customer Questions & Answers** scraper: that
feature no longer exists on Amazon. `/ask/questions/…` now redirects to the
sign-in page, and product pages carry zero Q&A content — verified across
several ASINs, the mobile site and every alternate endpoint.

Amazon replaced it with the "Customers say" insight widget, which is what
this actor reads. For gap analysis it is arguably better: the opinions
arrive already clustered by topic, with sentiment and volume attached.

## What you get

One row per aspect:

```json
{
  "recordType": "ASPECT",
  "asin": "B087F16GKW",
  "title": "Gaiam Yoga Mat - Premium 5mm Solid Thick Non Slip",
  "aspect": "grip",
  "sentiment": "MIXED",
  "mentions": 204,
  "positive": 112,
  "negative": 92,
  "aspectSummary": "Customers have mixed experiences with the grip of the yoga mat, with some praising its excellent stickiness and great traction, while others find it too slippery.",
  "mentionRank": 2,
  "mentionSharePercent": 20.69,
  "isContentGap": true
}
```

`positive` and `negative` always add up to `mentions` — Amazon publishes no
neutral bucket. They are what makes `MIXED` usable: on the same mat, grip is
112/92 and flatness is 18/36. Both are labelled MIXED; only one is a real
problem.

Plus one summary row per product, with Amazon's generated paragraph and the
gap shortlist:

```
NAKED Whey Protein          8 aspects, 3 gaps   [mixability, digestibility, texture]
Gaiam Yoga Mat              8 aspects, 4 gaps   [grip, thickness, durability, flatness]
Apple iPhone 11 Renewed     8 aspects, 2 gaps   [battery life, condition]
```

Read that yoga-mat row as a brief: customers are **split on grip, thickness,
durability and flatness**. Those four headings answer themselves.

## How to use it for copy

| Goal | Setting |
| --- | --- |
| Full picture of one catalogue | defaults |
| Just the complaints, ranked | `contentGapsOnly: true` |
| Ignore long-tail noise | `minMentions: 50` |
| Feed a spreadsheet | `emitAspectRows: true` (default) — one row per aspect sorts and pivots directly |

## Input

```json
{
  "asins": ["B00XIKPUK4", "B087F16GKW", "https://www.amazon.com/dp/B07ZPKN6YR"],
  "marketplace": "com",
  "contentGapsOnly": false,
  "minMentions": 0
}
```

| Field | Description |
| --- | --- |
| `asins` | ASINs to analyse. Product URLs work too |
| `marketplace` | com and ca verified; others see the caveat below |
| `emitAspectRows` | One row per aspect alongside the product row (default on) |
| `contentGapsOnly` | Only negative and mixed aspects |
| `minMentions` | Drop thinly-mentioned aspects |
| `emptyInsightRetries` | Exit-IP rotations when a well-reviewed product returns no widget (default 2, 0 disables) |
| `delaySeconds` | Pacing between products |
| `proxyConfiguration` | Residential **strongly recommended** |

## Coverage

Measured over 10 ASINs spanning supplements, electronics, books and
sporting goods:

| | Coverage |
| --- | --- |
| Aspect list (with sentiment + mentions) | **10/10** |
| Positive/negative split per aspect | **10/10** |
| Per-aspect summary sentence | **10/10** |
| AI review summary | **10/10** |
| Aspects per product | 8 in every case |

That is markedly more reliable than Amazon's Buy Box data, which is withheld
from roughly half of anonymous requests. The insight widget was served every
time.

## Things worth knowing

**Products with few reviews carry no insight widget**, and that is a real
answer rather than a failure. `hasInsights: false` marks them.

**A missing widget on a heavily reviewed product is the proxy, not the
product.** Amazon serves some exit IPs a reduced product page: full size,
title and rating and review count all present, insight widget simply gone.
Measured on `0061120081` — 149,157 ratings and zero aspects on one
residential exit, all 8 aspects on the next. When a product with at least
100 ratings comes back empty, the actor rotates to a fresh exit IP and looks
again (`emptyInsightRetries`, default 2). Products with few ratings are
never retried, because for them the empty answer is the true one.

**Amazon caps the widget at 8 aspects.** Every product tested returned
exactly 8, so treat this as the top 8 by volume, not an exhaustive list.

**The summaries are Amazon's text, not ours.** `aiSummary` (whole product)
and `aspectSummary` (one aspect) are Amazon's own generated sentences,
extracted verbatim. This actor does not write or paraphrase them. A product
with 8 aspects therefore carries 9 pieces of generated text.

**`aspectSummary` is never visible without clicking.** On the page it only
appears once a chip is selected, which is why a plain HTML read misses it
unless you decode the widget's payload. This actor decodes the payload, so
all 8 arrive from the single product-page request — no extra fetches, no
browser.

**Only amazon.com and amazon.ca were verified.** The development IP was
bot-walled on `co.uk` and `de` across all 10 TLS fingerprints tried, so
their behaviour is genuinely unknown rather than known-bad. Those
marketplaces are offered, but use a residential proxy in the matching
country, and expect aspect names and summary sentences to be localized.
Mention counts survive localization — they come from the widget's JSON
payload, not from the English page text.

**Blocked ASINs are reported, never silently dropped.** They emit a
`CAPTCHA_ESCALATION` row so a short run is never mistaken for a set of
products nobody has opinions about. CAPTCHAs are never solved.

## Known limits

- **8 aspects per product**, Amazon's cap.
- **No full review text.** `/product-reviews/` is behind the sign-in wall
  for anonymous clients. (The widget payload does carry ~4 short review
  excerpts per aspect with their review ids; this actor does not emit them
  yet.)
- Sentiment is **Amazon's classification**, not an independent model.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the Q&A retirement
evidence, the base64 fragment format, and the fingerprint matrix.
