# Rzeczpospolita Scraper

Extract full article text or the newest headlines from Rzeczpospolita (rp.pl), one of Poland's leading daily broadsheets — no account or subscription needed for open-access articles.

## Why use this actor

- Full article text included, not just a summary — headline, description, byline(s), publish/modified dates, keywords, reconstructed into clean paragraphs
- Automatically filters out "Czytaj więcej" (read-more) related-article widgets embedded inline in the article body
- Reports each article's paywall status (`isAccessibleForFree` + subscription tier) so you can separate free from premium content downstream
- Also fetches the newest headlines from the site's Google News sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's Google News sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.rp.pl/rynek-zdrowia/art45043351-opoznione-wyplaty-dla-medykow-na-kontraktach-te-szpitale-maja-problem"
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
  "_input": "https://www.rp.pl/rynek-zdrowia/art45043351-opoznione-wyplaty-dla-medykow-na-kontraktach-te-szpitale-maja-problem",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-24T16:39:22Z",
  "headline": "Opóźnione wypłaty dla medyków na kontraktach. Te szpitale mają problem",
  "description": "W niektórych szpitalach wynagrodzenia personelu kontraktowego są wypłacane z opóźnieniem...",
  "articleBody": "Dyrektorzy placówek w rozmowach z serwisem przyznali, że sytuacja jest efektem problemów...",
  "authors": ["Joanna Kamińska"],
  "publisher": "Rzeczpospolita",
  "datePublished": "2026-08-24T18:01:00+02:00",
  "dateModified": "2026-08-24T18:01:00+02:00",
  "keywords": "Rynek zdrowia",
  "articleSection": "Rynek zdrowia",
  "isAccessibleForFree": true,
  "_paywalled": false,
  "subscriptionTier": "Rzeczpospolita - dostęp podstawowy",
  "image": "https://i.gremicdn.pl/image/free/b53ff5bfb07cb8ee6a9dce1a41b946be/..."
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-24T16:39:29Z",
  "title": "Opóźnione wypłaty dla medyków na kontraktach. Te szpitale mają problem",
  "link": "https://www.rp.pl/rynek-zdrowia/art45043351-opoznione-wyplaty-dla-medykow-na-kontraktach-te-szpitale-maja-problem",
  "publicationDate": "2026-08-24T18:01:00+02:00"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `authors` | array | Byline names (article mode only). |
| `isAccessibleForFree` | boolean | Raw upstream paywall-metering flag (article mode only). |
| `_paywalled` | boolean | Convenience flag, `true` when `isAccessibleForFree` is `false` (article mode only). |
| `subscriptionTier` | string | Which rp.pl subscription product the article belongs to (article mode only). |
| `link` | string | Article URL (latest mode). |
| `publicationDate` | string | ISO-8601 publish timestamp with timezone (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.

## A note on the paywall

Rzeczpospolita runs a metered paywall (`isAccessibleForFree` in the article data). Samples used to build this actor were all free-tier ("dostęp podstawowy"); the actor surfaces the flag and subscription-tier name rather than guessing, so downstream consumers can filter premium content themselves. Whatever text is present in the page HTML is returned as-is (raw passthrough) — no attempt is made to bypass or detect truncated premium bodies beyond reporting the flag.
