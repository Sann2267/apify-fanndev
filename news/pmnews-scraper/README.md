# P.M. News Nigeria Scraper

Extract full article text or the newest headlines from P.M. News (pmnewsnigeria.com), a Lagos-based Nigerian tabloid — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, this site's own "Quick Read" summary box, byline, publisher, section tags, keywords, publish date, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the site's feed, with real per-article bylines and categories
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
    "https://pmnewsnigeria.com/2026/08/26/u-s-to-execute-single-largest-mass-revocation-of-visas/"
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
  "_input": "https://pmnewsnigeria.com/2026/08/26/u-s-to-execute-single-largest-mass-revocation-of-visas/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T06:39:12Z",
  "headline": "U.S. to execute single largest mass revocation of visas",
  "description": "U.S. is set to revoke 200,000 visas, a move that has been described as the largest single mass revocation of visas by the country",
  "quickSummary": "“We are coordinating with DHS to identify and revoke the non-immigrant visas of foreigners who have come to the U.S. claiming to be short-term visitors but  filed for asylum to stay here permanently,” State Department spokesman Tommy Pigott was quoted as saying.",
  "articleBody": "By Tiamiyu Prudence Arobani\n\nThe U.S. is set to revoke no fewer than 200,000 visas, a move that has been described as the largest single mass revocation of visas by the country and may face legal challenges.\n\nAccording to documents obtained by The Associated Press and two U.S. officials, the action will be taken by the Department of State in coordination with the Department of Homeland Security.\n\n... (2894 chars total)",
  "author": "Ayorinde Oluokun",
  "publisher": "P.M. News",
  "articleSection": ["US"],
  "keywords": ["United States", "Visa Revocation"],
  "datePublished": "2026-08-26T06:09:00+00:00",
  "thumbnailUrl": "https://cdn.pmnewsnigeria.com/wp-content/uploads/2025/07/U.S-visa.jpg",
  "wordCount": 564
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T06:37:38Z",
  "title": "U.S. to execute single largest mass revocation of visas",
  "link": "https://pmnewsnigeria.com/2026/08/26/u-s-to-execute-single-largest-mass-revocation-of-visas/",
  "description": "“We are coordinating with DHS to identify and revoke the non-immigrant visas of foreigners who have come to the U.S. claiming to be short-term visitors but  filed for asylum to stay here permanently,” State Department spokesman Tommy Pigott was quoted as saying.",
  "pubDate": "Wed, 26 Aug 2026 06:09:00 +0000",
  "categories": ["US", "United States", "Visa Revocation"],
  "author": "Ayorinde Oluokun",
  "guid": "https://pmnewsnigeria.com/?p=1124969"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary (article mode: meta description; latest mode: feed teaser). |
| `quickSummary` | string | This site's own lead-in "Quick Read" box — a short desk-written summary preceding the full article (article mode only). |
| `articleBody` | string | Full plain-text article content (article mode only). Often starts with the real reporter's byline as its own line ("By ..."). |
| `author` | string | Byline. This is the WordPress publishing account (often a desk editor) — it can differ from the real reporter named inside `articleBody`'s first line. |
| `publisher` | string | Site name, `"P.M. News"` (article mode only). |
| `articleSection` | array | Section tags, e.g. `["US"]` (article mode only). |
| `keywords` | array | Keyword tags (article mode only). |
| `datePublished` | string | ISO-8601 timestamp (article mode only). |
| `thumbnailUrl` | string | Lead image URL (article mode only). |
| `wordCount` | number | Upstream-computed word count as of scrape time (article mode only). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |
| `categories` | array | Real section/tag values from the feed (latest mode). |
| `guid` | string | RSS item guid, `?p=<id>` format — not the same as `link` (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed: `"not_found"` for a deleted/never-existed article, `"not_article"` for a valid page that isn't a news article (e.g. a static page), or `"http_<code>"` / `"blocked_or_transient"` for a transient site/network issue.
