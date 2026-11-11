# Mail & Guardian (South Africa) Scraper

Extract full article text or the newest headlines from the Mail & Guardian (mg.co.za), a leading South African investigative newspaper — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, description, byline(s), keywords, word count, publish/update dates, lead image
- Strong South African and pan-African political, business, and investigative coverage
- Also fetches the newest headlines (with teaser text and lead image) from the site's RSS feed without visiting each article individually
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
    "https://mg.co.za/politics/2026-08-21-mk-party-takes-aim-at-anc-stronghold/"
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
  "_input": "https://mg.co.za/politics/2026-08-21-mk-party-takes-aim-at-anc-stronghold/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-24T02:01:10Z",
  "headline": "MK Party takes aim at ANC stronghold",
  "description": "The uMkhonto weSizwe Party (MK Party) is strategically targeting the Eastern Cape, a traditional ANC stronghold, to weaken the governing party...",
  "articleBody": "A leadership dispute in the party has created an opening for the MK Party in the Eastern Cape\n\nThe uMkhonto weSizwe Party (MK Party) is targeting the Eastern Cape...",
  "datePublished": "2026-08-21T05:00:00.000Z",
  "dateModified": "2026-08-21T05:00:00.000Z",
  "author": "Lunga Mzangwe",
  "keywords": ["mk party", "umkhonto wesizwe party", "anc", "eastern cape", "jacob zuma"],
  "wordCount": "812",
  "image": "https://images.newsteam.io/image/400/..."
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-24T02:01:09Z",
  "title": "SA's captive lion industry remains legal despite years of promises to phase it out, say animal welfare groups",
  "link": "https://mg.co.za/the-green-guardian/2026-08-23-sa-s-captive-lion-industry-remains-legal-despite-years-of-promises-to-phase-it-out-say-animal-welfare-groups/",
  "guid": "https://mg.co.za/the-green-guardian/2026-08-23-sa-s-captive-lion-industry-remains-legal-despite-years-of-promises-to-phase-it-out-say-animal-welfare-groups/",
  "pubDate": "Sun, 23 Aug 2026 21:00:28 GMT",
  "description": "Despite years of government commitments, parliamentary reviews and expert panels, South Africa's commercial captive lion breeding industry remains operational...",
  "imageUrl": "https://images.newsteam.io/image/1600/..."
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Teaser/summary. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline(s), comma-joined when multiple contributors are credited (article mode only). |
| `keywords` | array | Tag keywords (article mode only). |
| `wordCount` | string | Article word count reported by the site (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` / `imageUrl` | string | Lead image URL. |
| `link` / `guid` | string | Article URL (latest mode). |
| `pubDate` | string | Publication timestamp (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
