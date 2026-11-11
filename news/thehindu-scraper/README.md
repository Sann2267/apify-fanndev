# The Hindu Scraper

Extract full article text or the newest headlines from The Hindu (thehindu.com), one of India's most respected English-language newspapers — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, byline, section, publish/update dates
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
    "https://www.thehindu.com/news/national/jammu-and-kashmir/two-inmates-arrested-under-pocso-act-escape-from-srinagar-central-jail-search-launched/article71382241.ece"
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
  "_input": "https://www.thehindu.com/sport/football/maresca-makes-winning-start-with-man-city-after-dramatic-fightback/article71382232.ece",
  "_source": "S1-microdata",
  "_scrapedAt": "2026-08-23T23:14:31Z",
  "headline": "Maresca makes winning start with Man City after dramatic fightback",
  "description": "Enzo Maresca secures a thrilling 2-1 victory for Manchester City against Bournemouth in his Premier League debut.",
  "articleBody": "Manchester City made a winning start to life without Pep Guardiola as late goals from Marc Guehi and Josko Gvardiol snatched a dramatic 2-1 victory ...",
  "articleSection": "Football",
  "datePublished": "2026-08-24T03:28:00.000+05:30",
  "author": "AFP"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T23:14:30Z",
  "title": "Two inmates arrested under POCSO Act escape from Srinagar Central Jail; search launched",
  "link": "https://www.thehindu.com/news/national/jammu-and-kashmir/two-inmates-arrested-under-pocso-act-escape-from-srinagar-central-jail-search-launched/article71382241.ece",
  "guid": "article-71382241",
  "pubDate": "Mon, 24 Aug 2026 03:02:10 +0530",
  "description": "The police urged the public to share any information that could help trace or apprehend the two men by contacting the nearest police station or dialling 112",
  "categories": ["Jammu and Kashmir"]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline (article mode only) — wire-service name (e.g. "AFP") for syndicated content, or reporter name. |
| `articleSection` | string | Section name (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `categories` | array | Section tag (latest mode only). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
