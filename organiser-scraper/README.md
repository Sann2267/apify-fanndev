# Organiser Scraper

Extract full article text or the newest headlines from Organiser (India) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, section, byline, and publish date
- Also fetches the newest headlines (with full body text) from the site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's `/feed/` and returns the newest stories, already including full body text.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://organiser.org/2026/08/26/377070/bharat/home-minister-priyank-kharge-tells-no-case-registered-against-rss-in-karnataka/"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the site-wide feed. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 10 (the feed's natural page size — see Known limits). |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://organiser.org/2026/08/26/377070/bharat/home-minister-priyank-kharge-tells-no-case-registered-against-rss-in-karnataka/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T06:37:00Z",
  "headline": "Home minister Priyank Kharge tells no case registered against RSS in Karnataka",
  "description": "Karnataka Home Minister Priyank Kharge has told the Legislative Council that no cases have been registered against the RSS in the state over communal violence, shakhas or path sanchalans.",
  "articleBody": "Bengaluru: The political debate over the Rashtriya Swayamsevak Sangh (RSS) in Karnataka intensified on Tuesday (August 25) after Home Minister Priyank Kharge told the Legislative Council that no cases had been registered against the organisation in the state in connection with communal violence, RSS shakhas or path sanchalans. ... (full plain-text article, ~4,500 characters on this sample)",
  "author": "Indresh",
  "publisher": "Organiser",
  "articleSection": ["Politics", "Bharat", "RSS News", "RSS in News", "Karnataka"],
  "keywords": { "2": "RSS", "3": "BJP Leader CT Ravi", "4": "Home Minister Priyank Kharge on RSS", "5": "No Cases against RSS" },
  "datePublished": "2026-08-26T06:10:13+00:00",
  "dateModified": null,
  "thumbnailUrl": "https://organiser.org/wp-content/uploads/2026/08/rss.webp",
  "image": "https://organiser.org/wp-content/uploads/2026/08/rss.webp",
  "wordCount": 759,
  "inLanguage": "en"
}
```

**Latest headlines mode** — one record per headline (truncated here for readability):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T06:37:10Z",
  "title": "Home minister Priyank Kharge tells no case registered against RSS in Karnataka",
  "link": "https://organiser.org/2026/08/26/377070/bharat/home-minister-priyank-kharge-tells-no-case-registered-against-rss-in-karnataka/",
  "guid": "https://organiser.org/?p=377070",
  "pubDate": "Wed, 26 Aug 2026 06:10:13 +0000",
  "description": "<img width=\"1280\" height=\"720\" src=\"https://organiser.org/wp-content/uploads/2026/08/rss.webp\" ... />Bengaluru: The political debate over the Rashtriya Swayamsevak Sangh (RSS) in Karnataka intensified on ... (teaser HTML, ~1,300 characters on this sample)",
  "category": ["Bharat", "Politics", "RSS News", "RSS in News", "Karnataka"],
  "author": "Indresh",
  "contentEncoded": "<img width=\"1280\" ... />Bengaluru: The political debate over the Rashtriya Swayamsevak Sangh (RSS) in Karnataka intensified on Tuesday ... (full article body as HTML, ~4,600 characters on this sample)"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld+html` or `S2-rss`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content, parsed from the page HTML (article mode only). |
| `contentEncoded` | string | Full article body as HTML markup (latest mode only — this feed carries full text, not just headlines). |
| `description` | string | Article summary/dek (article mode — plain text). Teaser HTML with a lead image (latest mode). |
| `keywords` | object | Article-mode only. A JSON object with sparse numeric keys, e.g. `{"2": "RSS", "3": "..."}` — a quirk of this site's SEO plugin, not a plain list. |
| `author` | string | Byline name, resolved from the page's structured data (article mode) or the feed's creator field (latest mode). |
| `publisher` | string | Always `"Organiser"` (article mode). |
| `articleSection` / `category` | array | Section/category tags, e.g. `["Politics", "Bharat", "RSS News"]`. |
| `datePublished` | string | Publication timestamp (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |
| `image` / `thumbnailUrl` | string | Lead image URL (article mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article slug).

## Known limits

- `latest` mode returns at most 10 headlines per run — the underlying feed does not support pagination on this site (confirmed during testing: requesting page 2 returns the same 10 items as page 1). For more than 10 recent articles, run `mode: "article"` with a list of URLs instead.
- `keywords` (article mode) is not always a clean list — see the field table above.
