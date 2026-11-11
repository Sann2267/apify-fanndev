# Blibli Homepage Recommendation & Ad Placement Tracker

See what [Blibli](https://www.blibli.com)'s own algorithm is placing on its
homepage right now — not what a search or category browse returns, but the
actual "Untukmu" (For You), "Zona affiliate", and auto-generated category
tabs a real visitor sees, with rank order and paid ad slots included.

Built for brand/seller **homepage visibility monitoring** ("is my product
being surfaced, and where"), **affiliate product discovery** (the
"Zona affiliate" tab is a curated affiliate-marketing feed), and
**homepage-ad competitive intelligence** (which brands are buying banner
placement, and when their campaign runs).

No login, no API key, no cookies. HTTP-only — no browser.

## One event, no `mode`

Every other actor in this developer's Blibli portfolio uses a `mode` input
when a target needs genuinely different endpoints with different output
shapes (see `blibli-promo-extractor`'s three modes). This one doesn't,
deliberately: every tab hits the *same* endpoint and returns the *same*
tile shapes. Tabs are a filter dimension of one event — "what's on the
homepage feed right now" — not separate events, so they're a `tabs` array
input instead of a `mode` enum.

```json
{ "tabs": ["TAB_1", "TAB_4"], "maxPagesPerTab": 15 }
```

Leave `tabs` empty to auto-discover and sweep every tab Blibli currently
exposes (8 at the time of writing — this list itself changes as Blibli adds
seasonal tabs, so the actor always re-fetches it rather than hardcoding
names).

## Output — three tile types in one feed

Blibli's feed interleaves three unrelated tile shapes; `_recordType` tells
them apart. Blibli's own fields are passed through **verbatim**; fields
this actor adds are prefixed with `_`.

**`product`** — a real recommendation:

```json
{
  "_recordType": "product",
  "_tabName": "TAB_1",
  "_tabTitle": "Untukmu",
  "_rankInFeed": 2,
  "name": "Hanasui Collagen Water Sunscreen SPF30 30gr",
  "sku": "HAO-70179-00023",
  "merchantName": "Hanasui Flagship Store",
  "_offerPrice": 30600,
  "_discountPercent": 15,
  "_productUrl": "https://www.blibli.com/p/...",
  "_personalizationSource": "brs",
  "_personalizationLogic": ";;DEFAULT_RERANK"
}
```

**`ad_banner`** — a paid brand placement, no product at all:

```json
{
  "_recordType": "ad_banner",
  "_tabName": "TAB_1",
  "_brandAdId": "BA00002377_homePage",
  "_adBrandNames": ["KGA - New Launch"],
  "_adRedirectUrl": "https://www.blibli.com/promosi/kga-advan-laptop",
  "_adStartTime": "2026-08-27T17:00:00Z",
  "_adEndTime": "2026-09-09T16:59:59Z"
}
```

**`category_card`** — a curated "trending now" collection tile, not a
single SKU:

```json
{
  "_recordType": "category_card",
  "name": "Sepatu Sneakers Pria",
  "_cardLabel": "Lagi laris",
  "_cardDescription": "1,7 rb terjual bulan ini",
  "_productUrl": "https://www.blibli.com/top-selling-page/..."
}
```

`_personalizationSource` / `_personalizationLogic` / `_strategyId` are
Blibli's own algorithm-internals fields, passed through — a rare public
window into which recommendation strategy served a given placement.

## Input reference

| Field | Description |
| --- | --- |
| `tabs` | Tab short-codes to sweep (e.g. `["TAB_1","TAB_4"]`). Empty = every tab Blibli currently exposes. |
| `maxPagesPerTab` | Hard cap on pages per tab (default 15, ~20 items/page). This is a personalized, re-ranked feed with no reliable "end" — see Known limits. |
| `maxItemsPerTab` | Stop emitting for a tab after this many records. `0` = no limit beyond `maxPagesPerTab`. |
| `includeAdBanners` | Keep paid ad-banner tiles (default `true`). Turn off for product recommendations only. |
| `proxyConfiguration` | Apify Residential + country `ID` recommended for long runs. |

## Known limits

- **No absolute "all recommendations."** This is a live, re-ranked feed
  (Blibli's own field literally says `personalizationLogic:
  "DEFAULT_RERANK"`), not a fixed catalogue — `maxPagesPerTab` is what
  actually bounds a run for personalized tabs, not an end-of-list signal.
  Auto-generated category tabs (`AUTOMATIC` source) do terminate cleanly on
  an empty page; personalized tabs (`MANUAL` source, e.g. "Untukmu") may
  not, by design of what a recommendation feed is.
- **Blibli's own `paging.total_page` is unreliable on this endpoint** —
  observed oscillating between requests to the same tab. This actor never
  uses it as a stop condition; see CRAWLING_METHOD.md for the measurement.
- **Anonymous/default ranking only.** No session or cookies are sent, so
  this reflects Blibli's no-login ranking, not any specific shopper's
  personalized feed.

## Pricing

**$1.00 per 1,000 results** — pay-per-event, one event
(`apify-default-dataset-item`), charged per record in the dataset. No
subscription, no minimum.

Store category: **ECOMMERCE** — the actor's output is marketplace
product/placement data.

<details>
<summary>How this price was set</summary>

This developer's other Blibli actor (`blibli-promo-extractor`) priced at
$1.00/1k against a researched competitor band of $0.50-$4.99/1k for
Indonesian-marketplace scrapers, with measured operating cost of
$0.009/1k. This actor shares the identical stack (same HTTP client, same
Cloudflare bypass, same 1024 MB memory footprint, no browser) so its
operating cost is expected to be in the same range; a fresh Store search
specifically for homepage-recommendation/ad-placement scrapers (a much
narrower niche than general product scraping) found no directly comparable
actor at the time of writing, so this price matches the sibling actor's
proven point in the same niche/stack/portfolio rather than a fabricated
competitor figure.

</details>

## Reliability

Blibli sits behind **Cloudflare**. The actor clears it HTTP-only with TLS
impersonation plus the `Referer` header Cloudflare's rule requires — no
browser, no CAPTCHA solver. On a block it retries with exponential backoff
while rotating both the TLS fingerprint and (when a proxy is configured)
the egress IP.

Runs never fail silently: a blocked run, an upstream schema change, bad
input, or a genuinely empty result each emit a diagnostic row carrying
`_error` and `_errorDetail`.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the full WAF analysis,
endpoint discovery (including the `id`-vs-`name` trap and the tile shapes
found during local testing), and why `paging.total_page` can't be trusted.
