# Guardian Nigeria Scraper

Extract full article text or the newest headlines from The Guardian Nigeria (guardian.ng), a major Nigerian daily newspaper — no account or subscription needed.

> Not related to the UK's The Guardian (theguardian.com) — this is a separate, independent Nigerian publisher.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, publisher, section tags, keywords, publish date, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the site's news sitemap
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's news sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://guardian.ng/news/tinubu-backs-3-1bn-afcfta-trade-facilitation-project/"
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
  "_input": "https://guardian.ng/news/tinubu-backs-3-1bn-afcfta-trade-facilitation-project/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T02:58:38Z",
  "headline": "Tinubu backs $3.1bn AfCFTA trade facilitation project",
  "description": "Tinubu... companies behind the $3.1 billion customs modernisation project of the African Continental Free Trade Area (AfCFTA)",
  "articleBody": "President Bola Ahmed Tinubu has expressed support for the companies behind the $3.1 billion customs modernisation project of the African Continental Free Trade Area (AfCFTA), describing the initiative as transformative and capable of accelerating economic progress across the continent.\n\nThe President gave the endorsement during a recent courtesy visit by Alhaji Saleh Ahmadu, a trade, revenue and security strategist, whose company, Bergmans Security Consultants and Supplies Limited, entered into a 20-year concession agreement with the AfCFTA Secretariat for the project.\n\nThe agreement, implemen... (2958 chars total)",
  "author": "Sodiq Omolaoye",
  "publisher": "Guardian Nigeria",
  "articleSection": ["Featured", "News"],
  "keywords": ["AfCFTA", "Tinubu"],
  "datePublished": "2026-08-25T20:07:17+00:00",
  "dateModified": "2026-08-25T20:13:48+00:00",
  "thumbnailUrl": "https://cdn.guardian.ng/wp-content/uploads/2026/08/fast3375.webp",
  "wordCount": 424
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T02:58:05Z",
  "title": "Tinubu backs $3.1bn AfCFTA trade facilitation project",
  "link": "https://guardian.ng/news/tinubu-backs-3-1bn-afcfta-trade-facilitation-project/",
  "pubDate": "2026-08-25T20:07:17+00:00"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary, from the page's meta description (article mode only). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline, comma-joined if multiple authors (article mode only). |
| `publisher` | string | Site name, `"Guardian Nigeria"` (article mode only). |
| `articleSection` | array | Section tags, e.g. `["Featured", "News"]` (article mode only). |
| `keywords` | array | Keyword tags (article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `thumbnailUrl` | string | Lead image URL (article mode only). |
| `wordCount` | number | Upstream-computed word count as of scrape time (article mode only). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | ISO-8601 publish timestamp from the news sitemap (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed: `"not_found"` for a deleted/never-existed article, `"not_article"` for a valid page that isn't a news article (e.g. a static page), or `"http_<code>"` / `"blocked_or_transient"` for a transient site/network issue.
