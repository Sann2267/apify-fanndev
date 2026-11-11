# Korea Times Scraper

Extract full article text or the newest headlines from The Korea Times (koreatimes.co.kr), one of South Korea's oldest English-language newspapers — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/update dates, lead image
- English-language coverage of Korean politics, business, K-pop/entertainment, and sport
- Correctly distinguishes real articles from the site's "soft-404" pages (which return HTTP 200 instead of a real 404) instead of returning garbage data
- Also fetches the newest headlines (with tags and lead image) from the site's rolling news sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's rolling news sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.koreatimes.co.kr/business/companies/20260823/kakao-spin-off-plan-faces-lingering-investor-distrust"
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

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.koreatimes.co.kr/business/companies/20260823/kakao-spin-off-plan-faces-lingering-investor-distrust",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-24T01:51:21Z",
  "headline": "Kakao spin-off plan faces lingering investor distrust",
  "description": "Kakao’s ambitious plan to split its business into two entities handling its mobile messenger and investment businesses, respectively, is facing lingering investor distrust...",
  "articleBody": "Kakao office in Seongnam, Gyeonggi Province, June 9. Yonhap Kakao’s ambitious plan to split its business into two entities...",
  "datePublished": "2026-08-22T18:11:00+09:00",
  "dateModified": "2026-08-23T09:03:00+09:00",
  "author": "Nam Hyun-woo",
  "image": "https://newsimg.koreatimes.co.kr/..."
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-24T01:51:16Z",
  "title": "30 people killed in a landslide in the capital of Guinea, officials say - The Korea Times",
  "link": "https://www.koreatimes.co.kr/world/20260824/30-people-killed-in-a-landslide-in-the-capital-of-guinea-officials-say",
  "publicationDate": "2026-08-24T10:49+09:00",
  "keywords": ["Guinea"],
  "imageUrl": "https://newsimg.koreatimes.co.kr/2026/08/24/4b1fb0d4-0227-4036-999f-d363a53401a0.jpg"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Teaser/summary (article mode only). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline(s), comma-joined when multiple contributors are credited (article mode only). |
| `keywords` | array | Tag keywords (latest mode). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` / `imageUrl` | string | Lead image URL. |
| `link` | string | Article URL (latest mode). |
| `publicationDate` | string | Publication timestamp (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
