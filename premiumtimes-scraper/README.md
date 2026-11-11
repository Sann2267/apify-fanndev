# Premium Times Nigeria Scraper

Extract full article text or the newest headlines from Premium Times (premiumtimesng.com), Nigeria's leading independent English-language newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, section tags, keywords, publish date, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the site's RSS feed, automatically paginating to get up to 50 at once
- Byline and publisher names resolved from Premium Times' cross-referenced Yoast SEO metadata, not left as opaque IDs
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups, including a site-specific fix for an occasional stale-cache glitch on individual article pages

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's RSS feed (paginating automatically for larger limits) and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.premiumtimesng.com/opinion/905169-sultan-saad-abubakar-iii-at-70-the-authority-of-restraint-by-samuel-aruwan.html"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50 (auto-paginates the RSS feed). |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.premiumtimesng.com/news/top-news/905196-university-suspends-professor-stripped-over-attempted-sexual-assault.html",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T09:12:03Z",
  "headline": "University suspends professor stripped over attempted sexual assault",
  "description": "PREMIUM TIMES reported that the professor was physically assaulted and stripped on 15 August by some angry students over an alleged attempt to molest a female student sexually.",
  "articleBody": "The management of Nnamdi Azikiwe University (NAU), Awka, in Anambra State, has suspended a lecturer in the institution's Department of Chinese Studies, Ifeanyi Odinye, for violating the university's General and Academic Regulations...",
  "author": "Chinagorom Ugwu",
  "publisher": "Premium Times",
  "articleSection": ["Headline Stories", "South East", "Top News"],
  "keywords": ["Anambra state", "assault", "Awka", "investigation", "NAU", "News", "Nigeria", "Nnamdi Azikiwe University", "PREMIUM TIMES", "Sexual molestation", "suspends"],
  "datePublished": "2026-08-24T22:43:18+00:00",
  "thumbnailUrl": "https://i0.wp.com/media.premiumtimesng.com/wp-content/files/2024/09/UNIZIK-gate.jpg?fit=640%2C397&ssl=1",
  "wordCount": 616,
  "commentCount": 0
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T09:12:10Z",
  "title": "Nigeria to modernise border management using technology, intelligence – Officials",
  "link": "https://www.premiumtimesng.com/news/more-news/905326-nigeria-to-modernise-border-management-using-technology-intelligence-officials.html",
  "description": "The Nigerian government has called for stronger collaboration among security agencies, universities, regional institutions, border communities and development partners as it moves to modernise the country's border management system. The post Nigeria to modernise border management using technology, intelligence – Officials appeared first on Premium Times Nigeria.",
  "pubDate": "Tue, 25 Aug 2026 17:35:12 +0000",
  "categories": ["More News", "ABORNE", "Fraud", "Lagos State University", "Ministry of Interior"],
  "author": "Yakubu Mohammed",
  "guid": "https://www.premiumtimesng.com/?p=905326",
  "image": "https://i0.wp.com/media.premiumtimesng.com/wp-content/files/2025/04/486719373_1464727397996429_8248740703085538238_n-e1781191628101.jpg?fit=2048%2C1280&ssl=1"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short summary (article mode: meta description, best-effort — occasionally absent upstream; latest mode: RSS teaser). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline — resolved from the site's ld+json metadata (article mode) or the RSS `dc:creator` (latest mode). |
| `publisher` | string | Always `"Premium Times"` (article mode only). |
| `articleSection` | array | Section tags, e.g. `["Top News"]`, `["Contributors", "Opinion"]` (article mode only). |
| `keywords` | array | Keyword tags (article mode only). |
| `datePublished` | string | ISO-8601 publish timestamp. Note: this site has no `dateModified` field anywhere. |
| `thumbnailUrl` / `image` | string | Lead image URL. |
| `wordCount` / `commentCount` | number | Upstream-computed counts, as of scrape time (article mode only). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |
| `categories` | array | Section + freeform tags mixed together, as the feed provides them (latest mode). |
| `guid` | string | Internal article ID URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed. This site returns a **soft-404** (HTTP 200 with the homepage's own content) for deleted/never-existed article IDs rather than a real 404 — the actor detects this and reports it as `"_error": "not_found"` just like a real 404 would be.
