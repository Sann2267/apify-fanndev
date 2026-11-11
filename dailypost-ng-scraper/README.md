# Daily Post Nigeria Scraper

Extract full article text or the newest headlines from Daily Post Nigeria (dailypost.ng), a major Nigerian online newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, editor, publisher, section, keywords, publish date, word count, and estimated reading time
- Also fetches the newest headlines straight from the site's RSS feed, including real per-article author and category tags
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story from the page's structured data.
3. In latest mode, the actor reads the site's RSS feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://dailypost.ng/2026/08/26/nasarawa-gov-sule-orders-probe-arrest-over-missing-hospital-equipment/"
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
  "_input": "https://dailypost.ng/2026/08/26/nasarawa-gov-sule-orders-probe-arrest-over-missing-hospital-equipment/",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T17:17:15Z",
  "headline": "Nasarawa Gov Sule orders probe, arrest over missing hospital equipment",
  "description": "Governor Abdullahi Sule of Nasarawa State has ordered the arrest and prosecution of health workers accused of selling hospital equipment donated to a healthcare facility in Umaisha Development Area. Sule described the alleged sale as a serious act of misconduct and corruption, saying such behaviour showed a lack of concern for patients and the healthcare",
  "articleBody": "Governor Abdullahi Sule of Nasarawa State has ordered the arrest and prosecution of health workers accused of selling hospital equipment donated to a healthcare facility in Umaisha Development Area. Sule described the alleged sale as a serious act of misconduct and corruption, saying such behaviour showed a lack of concern for patients and the healthcare needs of residents. The governor gave the directive on Wednesday while inaugurating eight commissioners, special advisers, permanent secretaries and board members at the Government House in Lafia... (2,150 chars total)",
  "author": "Nana Ismail",
  "editor": "Nana Ismail",
  "publisher": "Daily Post Nigeria",
  "articleSection": "News",
  "keywords": ["nasarawa", " sule", " "],
  "datePublished": "2026-08-26T18:08:31+01:00",
  "dateModified": "2026-08-26T18:08:38+01:00",
  "thumbnailUrl": "https://dailypost.ng/wp-content/uploads/2025/07/Abdullahi-Sule-150x150.jpeg",
  "image": [
    { "@type": "ImageObject", "url": "https://dailypost.ng/wp-content/uploads/2025/07/Abdullahi-Sule-1200x687.jpeg", "width": "1200", "height": "687" }
  ],
  "wordCount": "368",
  "timeRequired": "PT1M38S"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T17:17:38Z",
  "title": "Nasarawa Gov Sule orders probe, arrest over missing hospital equipment",
  "link": "https://dailypost.ng/2026/08/26/nasarawa-gov-sule-orders-probe-arrest-over-missing-hospital-equipment/",
  "description": "<img width=\"700\" height=\"401\" src=\"https://dailypost.ng/wp-content/uploads/2025/07/Abdullahi-Sule.jpeg\" .../><p>Governor Abdullahi Sule of Nasarawa State has ordered the arrest and prosecution of health workers... [&hellip;]</p>",
  "pubDate": "Wed, 26 Aug 2026 17:08:31 +0000",
  "categories": ["News", "nasarawa", "sule"],
  "author": "Nana Ismail",
  "guid": "https://dailypost.ng/?p=1417606"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary (article mode); raw teaser HTML including a featured image and truncated text (latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline (article mode: from the article page; latest mode: from the RSS feed's `dc:creator`). |
| `editor` | string | Editor byline, often the same as `author` on this site (article mode only). |
| `publisher` | string | Site name, `"Daily Post Nigeria"` (article mode only). |
| `articleSection` | string | Section, e.g. `"News"`, `"Sport"` (article mode only). |
| `keywords` | array | Keyword tags (article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `thumbnailUrl` | string | Lead image URL (article mode only). |
| `image` | array | Lead image details (url/width/height) (article mode only). |
| `wordCount` | string | Upstream-computed word count as of scrape time, e.g. `"368"` (article mode only; passed through as-is, upstream emits it as a numeric string, not a number). |
| `timeRequired` | string | Upstream-computed estimated reading time, ISO 8601 duration (article mode only). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | Publish timestamp from the RSS feed (latest mode). |
| `categories` | array | Section/tag categories from the RSS feed (latest mode only). |
| `guid` | string | WordPress post GUID (latest mode only). |

A record with `_error` instead of article fields means that URL could not be processed: `"not_found"` for a deleted/never-existed article, `"not_article"` for a valid page that isn't a news article (e.g. a static page), or `"http_<code>"` / `"blocked_or_transient"` for a transient site/network issue.
