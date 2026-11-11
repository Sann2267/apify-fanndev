# New York Post Scraper

Extract full article text or the newest headlines from the New York Post — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, byline, section, keywords, and publish date
- Also fetches the newest headlines from a single site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's headline feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://nypost.com/2026/08/23/us-news/fresno-mulls-letting-prosecutors-carry-concealed-firearms-after-stabbing-rocks-california/"
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
  "_input": "https://nypost.com/2026/08/23/us-news/fresno-mulls-letting-prosecutors-carry-concealed-firearms-after-stabbing-rocks-california/",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-23T22:44:16Z",
  "@type": "NewsArticle",
  "headline": "Fresno mulls letting prosecutors carry concealed firearms after stabbing rocks California",
  "articleBody": "Fresno County officials are pushing to let prosecutors carry concealed firearms after a shocking daylight stabbing of a senior deputy district attorney last week ...",
  "articleSection": "us-news",
  "datePublished": "2026-08-23T22:37:43Z",
  "author": [
    { "@type": "Person", "name": "Nina Joudeh", "URL": "https://nypost.com/author/nina-joudeh/" }
  ],
  "publisher": { "@type": "NewsMediaOrganization", "name": "California Post" },
  "keywords": "... 3 more"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T22:44:51Z",
  "title": "Randi Weingarten pushes Target boycott over ICE and sparks fresh fury",
  "link": "https://nypost.com/2026/08/23/us-news/american-federation-of-teachers-launches-boycott-against-target-claims-retailer-remained-silent-on-ice/",
  "guid": "https://nypost.com/?post_type=article&p=40476458",
  "pubDate": "Sun, 23 Aug 2026 18:43:00 -0400",
  "description": "The AFT president directed families to alternative shopping sites after Target failed to respond to union letters",
  "creator": "Fox News"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | array | Byline (article mode only) — name and author-page URL per writer. |
| `articleSection` | string | Section name (article mode only). |
| `datePublished` | string | Publication timestamp (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |
| `creator` | string | Byline (latest mode only). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.

## Notes

Some articles carry `publisher.name: "California Post"` instead of `"New York Post"` — this is a regional sub-brand the publisher runs on the same domain, passed through verbatim. See `CRAWLING_METHOD.md` for details.
