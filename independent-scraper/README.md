# The Independent (UK) Scraper

Extract full article text or the newest headlines from The Independent (independent.co.uk), one of the UK's largest national newspapers — no account or subscription needed.

## Why use this actor

- No account or login required — free articles extracted in full, with a paywall flag included for premium content
- Full article text included, not just a summary — headline, description, byline, section, publish/update dates, lead image
- Strong UK, world, and sport coverage from a major national outlet
- Also fetches the newest headlines (with tags and lead image) from the Google News sitemap without visiting each article individually
- Automatically filters out login prompts, newsletter signup boilerplate, and comment-CTA text that would otherwise pollute the article body
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
    "https://www.independent.co.uk/sport/football/ipswich-sunderland-result-score-premier-league-highlights-jack-clarke-b3037578.html"
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
  "_input": "https://www.independent.co.uk/sport/football/ipswich-sunderland-result-score-premier-league-highlights-jack-clarke-b3037578.html",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-24T01:39:00Z",
  "headline": "Jack Clarke fires Ipswich to late victory over Sunderland",
  "description": "Ipswich 2-1 Sunderland: The last-minute strike ensured a perfect start to the Tractor Boys’ top-flight return",
  "articleBody": "Ipswich 2-1 Sunderland: The last-minute strike ensured a perfect start to the Tractor Boys’ top-flight return\n\nJack Clarke fired newly-promoted Ipswich to an opening-day victory with a 90th-minute winner...",
  "articleSection": null,
  "datePublished": "2026-08-23T11:13:46.000Z",
  "dateModified": "2026-08-23T11:13:46.000Z",
  "author": "George Sessions",
  "isAccessibleForFree": true,
  "image": "https://static.independent.co.uk/2026/08/22/17/2d12d990bc0e834cf73303f1380c6848....jpg?width=1200"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-24T01:38:58Z",
  "title": "Clearest sign yet that Trump believes House will go Democrat? Son-in-law Jared Kushner meets with Minority Leader Hakeem Jeffries",
  "link": "https://www.independent.co.uk/news/world/americas/us-politics/trump-midterms-jared-kushner-b3037802.html",
  "publicationDate": "2026-08-24T01:20:07Z",
  "keywords": ["Hakeem Jeffries", "Republicans", "White House", "Jared Kushner", "Donald Trump", "midterms", "Democrats", "GOP", "Senate"],
  "imageUrl": "https://static.independent.co.uk/2026/08/17/15/K5QFEQoP4fytH8Uf2Zx8FlpZrq84EQhhYWh47vYx8EE25cXMQrcJuyei4h1qGmCTHJZXn6rsmGkkPjmn6VvfiVjL_BgZOMMdtkQe..?width=1200&auto=webp&trim=0%2C0%2C0%2C0"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Teaser/summary (article mode only). |
| `articleBody` | string | Full plain-text article content, boilerplate UI text filtered out (article mode only). |
| `author` | string | Byline (article mode only). |
| `isAccessibleForFree` | boolean | Whether the site marks this article as free vs. premium (article mode only). |
| `keywords` | array | Tag keywords (latest mode). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` / `imageUrl` | string | Lead image URL. |
| `link` | string | Article URL (latest mode). |
| `publicationDate` | string | Publication timestamp (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
