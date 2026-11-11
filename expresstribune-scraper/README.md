# The Express Tribune Scraper

Extract full article text or the newest headlines from The Express Tribune (tribune.com.pk), a major Pakistani English-language daily — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, reconstructed into clean paragraphs (comment-section prompts, copyright notices, and inline "Read More" links automatically filtered)
- Also fetches the newest headlines straight from the site's XML sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://tribune.com.pk/story/2625663/psx-ends-lower-despite-moodys-upgrade"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 100. |
| `maxConcurrency` | integer | How many article pages to fetch in parallel. Default 4, max 16. |
| `proxyConfiguration` | object | Apify Proxy configuration. Residential is on by default. |

## Output

**Article mode** — one record per URL:

```json
{
  "_input": "https://tribune.com.pk/story/2625663/psx-ends-lower-despite-moodys-upgrade",
  "_source": "S1-html[express-parent-div]",
  "headline": "PSX ends lower despite Moody s upgrade",
  "articleBody": "KSE-100 index slips 200 points; profit-taking offsets early gains...",
  "author": "...",
  "publisher": "...",
  "datePublished": "..."
}
```

**Latest mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "title": "Gold Up As Global Rates Hit 3 Month High",
  "link": "https://tribune.com.pk/story/2625664/gold-up-as-global-rates-hit-3-month-high",
  "lastmod": "2026-08-25"
}
```

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.

## Notes

- A removed or nonexistent article URL comes back as `_error: "blocked_or_transient"`, not `"not_found"` — the site's Cloudflare setup challenges nonexistent `/story/<id>/` URLs specifically, so this actor can't tell "deleted article" apart from "anti-scraping block" at the HTTP level. Real articles are unaffected.
- `latest` mode titles are approximated from the URL slug (the sitemap has no title field) — use `article` mode for the exact headline.
- No paywall was found on any sampled article — full text is included for every successfully fetched URL.
