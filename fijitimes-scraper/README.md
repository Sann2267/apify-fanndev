# Fiji Times Scraper

Extract full article text or the newest headlines from The Fiji Times (fijitimes.com.fj), Fiji's leading newspaper — no account or API key needed.

## Why use this actor

- No account or login required — every sampled article was freely accessible, no paywall enforced
- Full article text included, not just a summary — headline, description, author, categories, publish/modified dates, and a lead image, reconstructed into clean paragraphs
- Also fetches the newest headlines straight from the sitemap (the site's `/feed/` RSS redirects to the homepage and is unusable)
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the newest post-sitemap page and returns the newest stories, newest first.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.fijitimes.com.fj/nfp-demands-action-on-crime/"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 100. Sourced from the newest `post-sitemap*.xml` page. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL, captured live on 2026-08-26 (body truncated here for readability):

```json
{
  "_input": "https://www.fijitimes.com.fj/police-hunt-fourth-suspect-in-nadi-taxi-robbery-case/",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-26T11:14:06Z",
  "headline": "Police hunt fourth suspect in Nadi taxi robbery case",
  "articleBody": "The Fiji Police Force is searching for a person of interest wanted in connection with the alleged aggravated robbery of a taxi driver in Nadi yesterday.\n\nPolice have released an image of the person and are calling on him to surrender at the nearest police station.\n\n...",
  "author": "ANISH CHAND",
  "description": "The Fiji Police Force is searching for a person of interest wanted in connection with the alleged aggravated robbery of a taxi driver in Nadi yesterday.",
  "categories": ["Local News", "News"],
  "datePublished": "2026-08-26T06:10:23+00:00",
  "dateModified": "2026-08-26T06:10:23+00:00",
  "image": "https://www.fijitimes.com.fj/wp-content/uploads/2026/08/Screenshot-2026-08-26-100325.png"
}
```

**Latest headlines mode** — one record per headline, captured live on 2026-08-26:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T11:13:41Z",
  "link": "https://www.fijitimes.com.fj/nfp-demands-action-on-crime/",
  "lastmod": "2026-08-26T06:20:13+00:00",
  "image": "https://www.fijitimes.com.fj/wp-content/uploads/2026/08/ChatGPT-Image-Aug-26-2026-10_14_32-AM.png"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-html` for articles, `S2-sitemap` for latest). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` | string | Article headline, from `h1.fijitimes_title` (article mode only). |
| `articleBody` | string | Full plain-text article content, joined from body paragraphs (article mode only). |
| `author` | string | Byline name (article mode only). |
| `description` | string | Short summary/dek (article mode only). |
| `categories` | array | WordPress category names the article is tagged with, e.g. `["Local News", "News"]` (article mode only). |
| `datePublished` | string | ISO-8601 publish timestamp (article mode only). |
| `dateModified` | string | ISO-8601 last-modified timestamp (article mode only). |
| `image` | string | Lead image URL (both modes). |
| `link` | string | Article URL (latest mode). |
| `lastmod` | string | ISO-8601 sitemap last-modified timestamp — not a guaranteed original publish time; fetch the article (`article` mode) for the exact `datePublished` (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or malformed article URL — confirmed live returning a real HTTP 404):

```json
{
  "_input": "https://www.fijitimes.com.fj/this-slug-definitely-does-not-exist-xyz123/",
  "_source": "none",
  "_scrapedAt": "2026-08-26T11:13:55Z",
  "_error": "not_found",
  "_errorDetail": ""
}
```

## Notes

- No paywall — full article text was freely accessible on every article sampled.
- This site's `/feed/` RSS redirects to the homepage and is unusable — `latest` mode reads the newest `post-sitemap*.xml` page instead, which carries no headline text (only `link`/`lastmod`/`image`); fetch the article (`article` mode) for the full title and metadata.
- See `CRAWLING_METHOD.md` for full technical recon notes.
