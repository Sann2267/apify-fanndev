# El País (English Edition) Scraper

Extract full article text or the newest headlines from EL PAÍS's English edition (english.elpais.com), Spain's largest newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — the English edition is fully open-access, with no paywall observed on any sampled article
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, section, keywords
- Also fetches the newest headlines straight from the site's RSS feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's RSS feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://english.elpais.com/usa/2026-08-24/when-the-killer-is-also-a-victim-the-trial-of-lindsay-clancy-fuels-us-culture-war.html"
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
| `maxConcurrency` | integer | How many article pages to fetch in parallel. Default 4, max 16. |
| `proxyConfiguration` | object | Apify Proxy configuration. Residential is on by default. |

## Output

**Article mode** — one record per URL:

```json
{
  "_input": "https://english.elpais.com/usa/2026-08-24/when-the-killer-is-also-a-victim...",
  "_source": "S1-jsonld",
  "_paywalled": false,
  "headline": "When the killer is also a victim: The trial of Lindsay Clancy fuels US culture war",
  "description": "The case against a mentally ill woman who killed her three children...",
  "articleBody": "No one disputes the facts. On January 24, 2023...",
  "author": "...",
  "publisher": "...",
  "datePublished": "...",
  "articleSection": "...",
  "keywords": ["..."],
  "isAccessibleForFree": true
}
```

**Latest mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "title": "MS-13 gang members say they buried 200 people in Bukele's political cradle",
  "link": "https://english.elpais.com/international/2026-08-24/ms-13-gang-members-...",
  "description": "An indictment by Salvadoran prosecutors reveals the discovery...",
  "pubDate": "Mon, 24 Aug 2026 08:24:39 GMT",
  "creator": "Bryan Avelar",
  "categories": ["El Salvador", "Nayib Bukele", "Maras"],
  "image": "https://images.english.elpais.com/..."
}
```

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.

## Notes

- This actor targets the English-language edition (`english.elpais.com`) specifically. The main Spanish site is a different domain with a real-world metered paywall and was not tested.
- Every sampled article was fully open-access — `_paywalled` is still derived from the site's own `isAccessibleForFree` signal, never hardcoded, so a future subscriber-only article is flagged correctly instead of silently treated as free.
