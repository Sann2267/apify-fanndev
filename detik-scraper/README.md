# Detik News Scraper

Extract full article text or the newest headlines from detikNews (news.detik.com), Indonesia's largest online news portal — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/update dates, lead image
- Ad-slot placeholder text is automatically filtered out of the article body
- Also fetches the newest headlines from the detikNews Google News sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the detikNews sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://news.detik.com/berita/d-8631766/bupati-pelalawan-liburkan-sekolah-yang-terdampak-kabut-asap-karhutla"
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
  "_input": "https://news.detik.com/berita/d-8631766/bupati-pelalawan-liburkan-sekolah-yang-terdampak-kabut-asap-karhutla",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-23T23:35:58Z",
  "headline": "Bupati Pelalawan Liburkan Sekolah yang Terdampak Kabut Asap Karhutla",
  "description": "Bupati Pelalawan, Zukri, meliburkan sekolah di Ukui dan Kerumutan akibat kabut asap dari karhutla...",
  "articleBody": "Bupati Pelalawan, Zukri, meliburkan sekolah yang terdampak kabut asap akibat kebakaran hutan dan lahan (karhutla) di wilayahnya...",
  "datePublished": "2026-08-24T06:15:35+07:00",
  "dateModified": "2026-08-24T06:15:42+07:00",
  "author": "Raja Adil Siregar",
  "image": "https://akcdn.detik.net.id/community/media/visual/2026/08/23/kebakaran-hutan-1787492964521_169.jpeg?w=1200"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-23T23:35:57Z",
  "title": "Bupati Pelalawan Liburkan Sekolah yang Terdampak Kabut Asap Karhutla",
  "link": "https://news.detik.com/berita/d-8631766/bupati-pelalawan-liburkan-sekolah-yang-terdampak-kabut-asap-karhutla",
  "publicationDate": "2026-08-24T06:15:00+00:00",
  "keywords": ["bupati pelalawan", "kabut asap", "karhutla", "ispa", "kebakaran hutan"]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Teaser/summary (article mode only). |
| `articleBody` | string | Full plain-text article content, ad placeholders removed (article mode only). |
| `author` | string | Byline (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` | string | Lead image URL (article mode only). |
| `publicationDate` | string | Publication timestamp (latest mode). |
| `keywords` | array | Tag keywords (latest mode only). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
