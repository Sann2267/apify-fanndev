# Bangkok Post Scraper

Extract full article text or the newest headlines from the Bangkok Post (Thailand) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, byline, source attribution, and publish/update dates
- Also fetches the newest headlines from the top-stories feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's top-stories feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.bangkokpost.com/thailand/general/3306575/amnesty-law-takes-effect-monday-excludes-lese-majeste-offences"
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
  "_input": "https://www.bangkokpost.com/thailand/general/3306575/amnesty-law-takes-effect-monday-excludes-lese-majeste-offences",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T20:00:06Z",
  "@type": "NewsArticle",
  "headline": "Amnesty law takes effect Monday, excludes lese majeste offences",
  "description": "The Peaceful Society Promotion Act has been published in the Royal Gazette and will take effect on Monday, granting amnesty for a wide range of political offences committed over the past two decades, but excluding lese majeste cases.",
  "articleBody": "The law covers pe ...",
  "author": [{ "@type": "Person", "name": "Online Reporters" }],
  "isAccessibleForFree": "True",
  "datePublished": "2026-08-23T17:38:00+07:00",
  "dateModified": "2026-08-23T17:58:44+07:00"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T20:00:03Z",
  "title": "Amnesty law takes effect Monday, excludes lese majeste offences",
  "link": "https://www.bangkokpost.com/thailand/general/3306575/amnesty-law-takes-effect-monday-excludes-lese-majeste-offences",
  "guid": null,
  "pubDate": "Sun, 23 Aug 2026 17:38:00 +0700",
  "description": "The Peaceful Society Promotion Act has been published in the Royal Gazette and will take effect on Monday, granting amnesty for a wide range of political offences committed over the past two decades, but excluding lese majeste cases."
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `description` | string | Article summary/dek. |
| `author` | array | Byline (article mode only) — often a shared desk credit like "Online Reporters" rather than an individual reporter. |
| `isAccessibleForFree` | string | `"True"` or `"False"` (note: a string, not a boolean, as published by the site). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
