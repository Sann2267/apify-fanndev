# The Citizen (Tanzania) Scraper

Extract full article text or the newest headlines from The Citizen (thecitizen.co.tz), Tanzania's leading English-language daily — no account or subscription needed.

## Why use this actor

- No login required — the site's own paywall is enforced client-side only; this actor recovers the full article text even on articles the site marks as subscription-gated
- Full article text included, not just a summary — headline, teaser description, category, publish/modified dates, byline, and a clean reconstructed paragraph body
- Surfaces the site's own paywall signal (`isAccessibleForFree` / `access`) on every record, so you can see which stories the site intends to gate even though extraction succeeds either way
- Also fetches the newest headlines straight from the site's Google News sitemap, including keywords and the paywall flag, without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads The Citizen's Google News sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.thecitizen.co.tz/tanzania/sports/football/yanga-step-up-infrastructure-drive-with-12-storey-building-tender-5571168"
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

**Article mode** — one record per URL, real captured output (truncated here for readability):

```json
{
  "_input": "https://www.thecitizen.co.tz/tanzania/sports/football/yanga-step-up-infrastructure-drive-with-12-storey-building-tender-5571168",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-26T00:56:05Z",
  "articleId": "5571168",
  "headline": "Yanga step up infrastructure drive with 12-storey building tender",
  "description": "<p>The project is important because it demonstrates that Yanga’s infrastructure ambitions go beyond the construction of a football stadium</p><p></p>",
  "articleBody": "Dar es Salaam . Young Africans (Yanga) have widened their infrastructure ambitions by inviting qualified construction companies to bid for the development of a 12-storey building, adding another significant project to the club’s plans to strengthen its commercial base.\n\nIn a tender notice issued on August 25, the club said it was seeking companies with proven experience and capacity in the construction sector...",
  "summary": "The tender also signals a more structured approach to infrastructure development. Rather than relying solely on football success, Yanga appear to be positioning itself as a sports institution with valuable physical assets",
  "category": "Football",
  "categoryPath": ["Sports", "Football"],
  "author": [
    { "@type": "Person", "name": "Majuto Omary", "url": "https://www.thecitizen.co.tz/tanzania/majuto-omary-4469368" }
  ],
  "publisher": { "@type": "Organization", "name": "The Citizen", "logo": { "@type": "ImageObject", "url": "...", "width": 242, "height": 60 } },
  "datePublished": "2026-08-25T21:20:37Z",
  "dateModified": "2026-08-25T21:20:37Z",
  "image": [
    "https://www.thecitizen.co.tz/resource/image/5571170/landscape_ratio16x9/1600/900/.../yanga-investment-building.jpg",
    "... 2 more"
  ],
  "keywords": "yanga,building, storey, jangwani, mafia,nyamwezi,club",
  "isAccessibleForFree": null,
  "hasPart": null
}
```

A subscription-flagged article — note the full text is still recovered in full:

```json
{
  "headline": "Tanzania targets universal health insurance coverage by 2028/29 fiscal year",
  "articleBody": "Dar es Salaam. Tanzania aims to have all households enrolled in the Universal Health Insurance Scheme within the next two years... (full 16-paragraph article recovered, ~3270 characters)",
  "category": "National",
  "categoryPath": ["News", "National"],
  "author": [
    { "@type": "Person", "name": "The Citizen Reporter", "url": "https://www.thecitizen.co.tz/tanzania/the-citizen-reporter-2731634" }
  ],
  "isAccessibleForFree": "False",
  "hasPart": { "@type": "WebPageElement", "isAccessibleForFree": "False", "cssSelector": ".text-block" }
}
```

**Latest headlines mode** — one record per headline, real captured output:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T00:55:46Z",
  "articleId": "5570834",
  "title": "Tanzania targets universal health insurance coverage by 2028/29 fiscal year",
  "link": "https://www.thecitizen.co.tz/tanzania/news/national/tanzania-targets-universal-health-insurance-coverage-by-2028-29-fiscal-year-5570834",
  "section": "tanzania/news/national",
  "publicationDate": "2026-08-25T15:25:35Z",
  "language": "en",
  "keywords": "Khamis Mussa Omar",
  "access": "Subscription",
  "image": "https://www.thecitizen.co.tz/resource/blob/5496884/9fbe971e003038ad554790d9265f7f99/universal-health-pic-data.jpg"
}
```

A free headline (no `access` field) for comparison:

```json
{
  "title": "Tanzania to host EAC military cooperation week, offer free medical services",
  "link": "https://www.thecitizen.co.tz/tanzania/zanzibar/tanzania-to-host-eac-military-cooperation-week-offer-free-medical-services-5570764",
  "section": "tanzania/zanzibar",
  "keywords": null,
  "access": null
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-html` article mode, `S2-sitemap` latest mode). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `articleId` | string | Internal numeric article ID, from the URL's trailing digits. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short HTML-tagged teaser (article mode only, from ld+json, passed through verbatim). |
| `articleBody` | string | Full plain-text article content, paragraph-separated (article mode only). |
| `summary` | string | "What you need to know" bullet, when the article has one (article mode only). |
| `category` / `section` | string | Short category label (article mode) or derived URL path segments (latest mode). |
| `categoryPath` | array | Breadcrumb trail with "Home" dropped, e.g. `["News", "National"]` (article mode only). |
| `author` | array | Person object(s) with name + profile URL, from ld+json (article mode only). |
| `publisher` | object | Publisher name + logo, from ld+json (article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `publicationDate` | string | ISO-8601 publish timestamp from the sitemap (latest mode only). |
| `image` | array/string | Lead image URL(s). |
| `keywords` | string | Comma-separated keyword string. |
| `isAccessibleForFree` | string | `"False"` (a JSON string, not boolean) when the site marks the article premium; `null` when free (article mode). Full text is recovered either way — see CRAWLING_METHOD.md. |
| `hasPart` | object | Paywall-component metadata from ld+json, present alongside `isAccessibleForFree` (article mode only). |
| `access` | string | `"Subscription"` when the sitemap marks the headline premium; `null` when free (latest mode only). Mirrors `isAccessibleForFree`. |
| `link` | string | Article URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article — confirmed via a synthetic bad URL returning a real HTTP 404).
