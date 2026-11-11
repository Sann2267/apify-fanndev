# Punch Nigeria Scraper

Extract full article text or the newest headlines from Punch (punchng.com), Nigeria's most-read newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, publisher, section tags, keywords, publish date, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the site's feed
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's news feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://punchng.com/canada-hits-us-goods-with-retaliatory-tariffs/"
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
  "_input": "https://punchng.com/canada-hits-us-goods-with-retaliatory-tariffs/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T02:10:35Z",
  "headline": "Canada hits US goods with retaliatory tariffs",
  "description": "Canada announces retaliatory tariffs up to 50% on 700 American products, escalating its trade confrontation with the US.",
  "articleBody": "Canada has announced retaliatory tariffs of up to 50 per cent on about 700 American products, escalating its trade confrontation with the United States after negotiations between the two countries collapsed.\n\nThe new duties, which will take effect on September 8, will cover about $20bn worth of annual US imports and range from steel and aluminium t... (4050 chars total)",
  "author": "Ayoola Babalola",
  "publisher": "Punch Newspapers",
  "articleSection": ["Business & Economy"],
  "keywords": ["Canada tariffs", "Canadian economy", "Donald Trump", "... 7 more"],
  "datePublished": "2026-08-26T01:55:50+00:00",
  "dateModified": "2026-08-26T01:55:51+00:00",
  "thumbnailUrl": "https://punchng.com/wp-content/uploads/2026/07/0001283364_resized_canadawavingflag1022_1783455824.webp",
  "wordCount": 598
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T02:10:00Z",
  "title": "Azeez makes PFA Championship Team of the Year",
  "link": "https://punchng.com/azeez-makes-pfa-championship-team-of-the-year/?utm_source=rss.punchng.com&utm_medium=web",
  "description": "Millwall striker Femi Azeez earns a spot in the PFA Championship Team of the Year after a stellar 2025/26 season. Discover his impressive stats and nationa\n\nRead More: https://punchng.com/azeez-makes-pfa-championship-team-of-the-year/",
  "pubDate": "Wed, 26 Aug 2026 03:04:58 +0000",
  "categories": null,
  "author": "Punch Newspapers",
  "guid": "https://punchng.com/azeez-makes-pfa-championship-team-of-the-year/?utm_source=rss.punchng.com&utm_medium=web",
  "enclosureUrl": "https://cdn.punchng.com/wp-content/uploads/2020/08/18131509/punch-logo-500x179-1.png"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary (article mode: meta description; latest mode: feed teaser). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline (article mode: real per-article author; latest mode: always `"Punch Newspapers"`, not a real byline — use article mode against `link` for the real author). |
| `publisher` | string | Site name, `"Punch Newspapers"` (article mode only). |
| `articleSection` | array | Section tags, e.g. `["Business & Economy"]` (article mode only). |
| `keywords` | array | Keyword tags (article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `thumbnailUrl` | string | Lead image URL (article mode only). |
| `wordCount` | number | Upstream-computed word count as of scrape time (article mode only). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |
| `categories` | array | Observed always empty on this feed (latest mode). |
| `guid` | string | Same as `link` on this feed (latest mode). |
| `enclosureUrl` | string | Image URL from the feed item — always the generic site logo on this feed, not a per-article thumbnail (latest mode; use article mode's `thumbnailUrl` for a real lead image). |

A record with `_error` instead of article fields means that URL could not be processed: `"not_found"` for a deleted/never-existed article, `"not_article"` for a valid page that isn't a news article (e.g. a static page), or `"http_<code>"` / `"blocked_or_transient"` for a transient site/network issue.
