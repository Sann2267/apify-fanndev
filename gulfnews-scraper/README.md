# Gulf News Scraper

Extract full article text or the newest headlines from Gulf News (gulfnews.com), the UAE's largest English-language news portal — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, description, byline(s), section, keywords, publish/update dates, lead image
- Handles both regular articles and live-updating world-news stories
- Automatically cleans up stray HTML entities the site embeds directly in its data
- Also fetches the newest headlines from the Google News sitemap without visiting each article individually
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
    "https://gulfnews.com/world/americas/trump-takes-starring-role-at-washingtons-indycar-debut-1.500649812"
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
  "_input": "https://gulfnews.com/world/americas/trump-takes-starring-role-at-washingtons-indycar-debut-1.500649812",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T23:59:07Z",
  "headline": "Trump takes starring role at Washington's IndyCar debut",
  "description": "Trump set for starring role at Washington's debut IndyCar race",
  "articleBody": "US President Donald Trump rode a ceremonial lap in his armored limousine and waved the green flag to start Sunday's IndyCar race...",
  "datePublished": "2026-08-24T02:51:55+04:00",
  "dateModified": "2026-08-24T02:51:55+04:00",
  "author": "Reuters",
  "keywords": null,
  "image": "https://media.assettype.com/gulfnews/..."
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-23T23:59:05Z",
  "title": "US sanctions pressure Iran as Hormuz tensions persist; Iran president admits country facing 'many problems'",
  "link": "https://gulfnews.com/world/us-sanctions-pressure-iran-as-hormuz-tensions-persist-1.500649350",
  "publicationDate": "2026-08-24T03:50:51.928+04:00",
  "keywords": ["World", "Mena", "US-Israel-Iran war"],
  "imageUrl": "https://media.assettype.com/gulfnews/2026-08-20/s40byxbt/hormuz.jpg"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Teaser/summary, when the site provides one (article mode only). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline(s), comma-joined when multiple contributors are credited (article mode only). |
| `keywords` | string or array | Tag keyword(s). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` / `imageUrl` | string | Lead image URL. |
| `publicationDate` | string | Publication timestamp (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
