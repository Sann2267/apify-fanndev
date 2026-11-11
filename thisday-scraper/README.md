# This Day Nigeria Scraper

Extract full article text or the newest headlines from This Day (thisdaylive.com), a major
Nigerian national daily — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, byline, publish date, categories,
  tags, and lead image, reconstructed into clean paragraphs
- Latest headlines come back just as rich as single-article lookups — full body text included,
  not just a title and link
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories
   automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly
   available detail about the story.
3. In latest mode, the actor asks the site directly for its newest posts and returns them with the
   same level of detail as article mode.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the
actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.thisdaylive.com/2026/08/26/fgs-diaspora-mortgage-loan-signals-new-era-in-nigerias-housing-market/"
  ],
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Latest headlines mode:**
```json
{
  "mode": "latest",
  "limit": 10,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (`articleBody` truncated here for readability):

```json
{
  "_input": "https://www.thisdaylive.com/2026/08/26/fgs-diaspora-mortgage-loan-signals-new-era-in-nigerias-housing-market/",
  "_source": "S1-wpapi",
  "_scrapedAt": "2026-08-26T03:00:12Z",
  "id": 1240499,
  "slug": "fgs-diaspora-mortgage-loan-signals-new-era-in-nigerias-housing-market",
  "link": "https://www.thisdaylive.com/2026/08/26/fgs-diaspora-mortgage-loan-signals-new-era-in-nigerias-housing-market/",
  "headline": "FG's Diaspora Mortgage Loan Signals New Era in Nigeria's Housing Market",
  "description": "Nigeria's housing sector may be on the cusp of a major transformation as the federal government's Diaspora Mortgage Loan scheme opens a new financing channel for Nigerians living abroad, potentially",
  "articleBody": "Nigeria's housing sector may be on the cusp of a major transformation as the federal government's Diaspora Mortgage Loan scheme opens a new financing channel for Nigerians living abroad, potentially unlocking billions of dollars in remittances for home ownership and injecting fresh capital into the country's housing market, Emmanuel Addeh writes.\n\nThe Federal Mortgage Bank of Nigeria (FMBN) recently opened a new chapter in Nigeria's housing finance story with the successful launch of its Diaspora Mortgage Loan in London, United Kingdom... (4800+ chars total)",
  "date": "2026-08-26T01:35:47",
  "date_gmt": "2026-08-26T00:35:47",
  "modified": "2026-08-26T01:35:50",
  "modified_gmt": "2026-08-26T00:35:50",
  "author": "Adeyinka Salami",
  "authorSlug": "salami",
  "authorLink": "https://www.thisdaylive.com/author/salami/",
  "categories": ["Featured", "Nigeria"],
  "tags": [],
  "featuredImage": {
    "url": "https://global.ariseplay.com/amg/www.thisdaylive.com/uploads/FMBN.jpg",
    "width": 800,
    "height": 622,
    "altText": null
  },
  "guid": "https://www.thisdaylive.com/?p=1240499",
  "contentProtected": false
}
```

**Latest headlines mode** — one record per headline, same rich shape as article mode:

```json
{
  "_input": "latest",
  "_source": "S1-wpapi",
  "_scrapedAt": "2026-08-26T02:59:53Z",
  "id": 1240464,
  "slug": "awoniyi-scores-adds-an-assist-on-full-coventry-debut-in-carabao-cup",
  "link": "https://www.thisdaylive.com/2026/08/26/awoniyi-scores-adds-an-assist-on-full-coventry-debut-in-carabao-cup/",
  "headline": "Awoniyi Scores, Adds An Assist on Full Coventry Debut in Carabao Cup",
  "description": "Super Eagles striker Taiwo Awoniyi yesterday opened his goals account as Coventry defeated Plymouth Argyle 4-2 in the second round of the Carabao Cup...",
  "articleBody": "Super Eagles striker Taiwo Awoniyi yesterday opened his goals account as Coventry defeated Plymouth Argyle 4-2 in the second round of the Carabao Cup.\n\nThe former Nottingham Forest forward who completed his switch to Coventry last week, impressed on his first full debut for the Sky Blues, scoring a goal and also contributing as assist for his new team... (1500+ chars total)",
  "date": "2026-08-26T02:00:33",
  "date_gmt": "2026-08-26T01:00:33",
  "author": "Duro Ikhazuagbe",
  "categories": ["Sport"],
  "tags": [],
  "featuredImage": { "url": "https://global.ariseplay.com/amg/www.thisdaylive.com/uploads/Awoniyi.jpg", "width": 800, "height": 622, "altText": null },
  "guid": "https://www.thisdaylive.com/?p=1240464",
  "contentProtected": false
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record — `S1-wpapi` (normal) or `S2-html` (degraded fallback, missing author/date/description). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `id` | number | Internal numeric post ID. |
| `slug` | string | URL slug of the post. Rarely a bare number for a small number of posts with an unset title (a real, occasional site quirk — see below). |
| `link` | string | Canonical article URL. |
| `headline` | string | Article headline. Can be null for the rare unset-title posts mentioned above. |
| `description` | string | Short summary from the site's own excerpt. Null on the degraded fallback path. |
| `articleBody` | string | Full plain-text article content. |
| `date` / `date_gmt` | string | Publish date/time, site-local (WAT, UTC+1) and UTC. |
| `modified` / `modified_gmt` | string | Last-modified date/time, site-local and UTC. |
| `author` | string | Byline name. Null on the degraded fallback path. |
| `authorSlug` / `authorLink` | string | The author's site archive slug/URL. |
| `categories` / `tags` | array | Section and tag labels attached to the post. |
| `featuredImage` | object | Lead image URL, dimensions, and alt text. |
| `guid` | string | WordPress-internal GUID URL. |
| `contentProtected` | boolean | The site's own paywall flag — always `false` on every article sampled; this site has no paywall. |

A record with `_error` instead of article fields means that URL could not be processed:
`"not_found"` for a deleted/never-existed article, or `"http_<code>"` / `"blocked_or_transient"`
for a transient site/network issue.
