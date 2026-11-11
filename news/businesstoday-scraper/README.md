# Business Today Scraper

Extract full article text or the newest headlines from Business Today (India) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, keywords, section, byline, and publish/update dates
- Also fetches the newest headlines from Business Today's site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads Business Today's site-wide "latest" feed and returns the newest headlines across economy, markets, technology, and more.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.businesstoday.in/india/story/snow-rock-landslide-near-china-blocked-river-debris-lake-formed-then-burst-what-may-have-caused-nepals-deadly-flood-551627-2026-08-26"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `maxConcurrency` | integer | How many pages to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.businesstoday.in/india/story/snow-rock-landslide-near-china-blocked-river-debris-lake-formed-then-burst-what-may-have-caused-nepals-deadly-flood-551627-2026-08-26",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-26T17:12:29Z",
  "@type": "NewsArticle",
  "headline": "Snow-rock landslide near China blocked river, debris lake formed, then burst: What may have caused Nepal&amp;#039;s deadly flood",
  "articleSection": "India",
  "url": "https://www.businesstoday.in/india/story/snow-rock-landslide-near-china-blocked-river-debris-lake-formed-then-burst-what-may-have-caused-nepals-deadly-flood-551627-2026-08-26",
  "description": "The deadly flash flood originated near the Nepal-Tibet border after an avalanche or landslide caused a sudden surge in the Lhende Khola",
  "keywords": "Nepal flood, Rasuwa flood, Nepal Tibet border flood, Lhende River flood, Bhote Koshi flood, Nepal landslide, Nepal flash flood 2026, glacial lake outburst Nepal, Rasuwagadhi flood, Nepal China border flood",
  "datePublished": "2026-08-26T22:01:48+05:30",
  "dateModified": "2026-08-26T22:11:09+05:30",
  "articleBody": "Nepal&amp;#039;s disaster management authority on Wednesday said a snow-rock landslide near the Nepal ... [full article text, ~3000 characters]",
  "publisher": { "@type": "Organization", "name": "Business Today", "sameAs": "https://www.businesstoday.in/", "logo": { "url": "https://akm-img-a-in.tosshub.com/businesstoday/resource/img/bt-schema-logo.png" } },
  "author": { "@type": "Person", "name": "Business Today Desk", "url": "https://www.businesstoday.in/author/business-today-desk" },
  "image": { "@type": "ImageObject", "contentUrl": "https://akm-img-a-in.tosshub.com/businesstoday/images/story/202608/6a8f1471ac187-nepal-flood-landslide-may-have-triggered-glacier-inclusive-flood-near-china-border-262931884-16x9.jpeg?size=1280:720", "width": "1280", "height": "720" }
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T17:12:06Z",
  "title": "Govt starts buffer onion releases as festive demand nears",
  "link": "https://www.businesstoday.in/latest/economy/story/govt-starts-buffer-onion-releases-as-festive-demand-nears-551618-2026-08-26?utm_source=rssfeed",
  "pubDate": "2026-08-26T20:10:41+05:30",
  "description": "As of August 26, the all-India average retail price of onion stood at ₹37.87 per kg, while tomato was ₹38.33 and potato ₹22.63 per kg.",
  "guid": "https://www.businesstoday.in/latest/economy/story/govt-starts-buffer-onion-releases-as-festive-demand-nears-551618-2026-08-26?utm_source=rssfeed"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld` or `S2-rss`). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). May contain double-HTML-escaped entities (e.g. `&amp;#039;` instead of an apostrophe) — passed through as received from the source. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `description` | string | Article summary/dek (article mode) or RSS item summary (latest mode). |
| `keywords` | string | Comma-separated topic tags (article mode only). |
| `author` | object | Byline — usually a desk credit (e.g. "Business Today Desk") rather than a named reporter. |
| `articleSection` | string | Section/vertical name (article mode only), e.g. "India", "Economy". |
| `datePublished` / `dateModified` | string | Publication timestamps with `+05:30` IST offset (article mode). |
| `pubDate` | string | Publication timestamp with `+05:30` IST offset (latest mode). Occasionally empty for magazine/cover-story items, matching the source feed. |
| `link` / `guid` | string | The article URL, with a trailing `?utm_source=rssfeed` tracking parameter (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
