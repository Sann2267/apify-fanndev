# Business Standard Scraper

Extract full article text or the newest headlines from Business Standard, one of India's leading business and financial dailies — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included for free articles — headline, author, keywords, section, and publish/update dates
- Paywalled articles are clearly flagged (`isPremium`) in latest-headlines mode, so you can skip them before spending a request
- Also fetches the newest headlines (with lead image and byline) from a single combined feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's headline feed and returns the newest stories, including whether each one sits behind Business Standard's premium paywall.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.business-standard.com/finance/personal-finance/ppf-to-digital-gold-monthly-investments-that-build-long-term-wealth-126081401843_1.html"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.business-standard.com/finance/personal-finance/ppf-to-digital-gold-monthly-investments-that-build-long-term-wealth-126081401843_1.html",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T19:36:50Z",
  "@type": "NewsArticle",
  "inLanguage": "en",
  "headline": "PPF to digital gold: Monthly investments that build long-term wealth",
  "description": "Here are seven low-cost, high-impact investment tools designed to help small monthly contributions grow into a substantial long-term corpus",
  "keywords": "Public Provident Fund, National Pension System, digital gold, investments",
  "articleSection": "Personal Finance",
  "image": "https://bsmedia.business-standard.com/_media/bs/img/article/2026-08/11/full/1786468060-7263.jpg",
  "datePublished": "2026-08-22T08:00:26+05:30",
  "dateModified": "2026-08-22T08:00:26+05:30",
  "articleBody": "In building long-term wealth, the amount of money you save every month is important but not the only component..."
}
```

Paywalled articles return the same shape, but `articleBody` is a short teaser (one paragraph) instead of the full text — Business Standard truncates it server-side before it reaches this actor.

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T19:35:35Z",
  "title": "Airport privatisation: FinMin flags oligopoly in aviation sector",
  "link": "https://www.business-standard.com/industry/aviation/airport-privatisation-finmin-flags-oligopoly-in-aviation-sector-126082300545_1.html",
  "guid": "https://www.business-standard.com/industry/aviation/airport-privatisation-finmin-flags-oligopoly-in-aviation-sector-126082300545_1.html",
  "pubDate": "Sun, 23 Aug 2026 23:54:17 +0530",
  "description": "Together, private operators Adani and GMR account for more than half of India's air passengers",
  "author": "Deepak Patel",
  "isPremium": true,
  "keywords": "airport privatisation, Finance Ministry, Civil Aviation Ministry, PPPAC, Airports Authority of India, Adani Group, aviation sector, airport bundles, AERA, airport concessions",
  "imageUrl": "https://bsmedia.business-standard.com/_media/bs/img/article/2026-08/23/full/1787509242-2898.jpg",
  "thumbnailUrl": "https://bsmedia.business-standard.com/_media/bs/img/article/2026-08/23/thumb/1787509242-2898.jpg"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Article content (article mode only) — full text for free articles, a short teaser for paywalled ones. |
| `description` | string | Article summary/dek. |
| `author` | object (article) / string (latest) | Byline. |
| `isPremium` | boolean | `true` if the article sits behind Business Standard's paywall (latest mode only). |
| `keywords` | array (article) / string (latest) | Topic tags. |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |
| `imageUrl` / `thumbnailUrl` | string | Lead image / thumbnail URL (latest mode only). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
