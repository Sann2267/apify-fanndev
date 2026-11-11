# Kun.uz Scraper

Extract full article text or the newest headlines from Kun.uz (kun.uz), Uzbekistan's most-visited news portal, English edition — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, reconstructed into clean paragraphs
- Handles both of the site's article templates automatically (standard news template and a separate long-read/listicle template), so extraction doesn't silently fail on feature articles
- Latest-headlines mode reads the site's own "Latest news" page, always up to date, with precise publish timestamps
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's own "Latest news" listing page and returns the newest headlines with precise timestamps.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://kun.uz/en/news/2026/08/26/saida-mirziyoyeva-meets-chinese-foreign-minister-wang-yi"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 20. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (real output, captured 2026-08-26):

```json
{
  "_input": "https://kun.uz/en/news/2026/08/26/saida-mirziyoyeva-meets-chinese-foreign-minister-wang-yi",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T17:21:22Z",
  "headline": "Saida Mirziyoyeva meets Chinese Foreign Minister Wang Yi",
  "description": "Head of Uzbekistan's Presidential Administration Saida Mirziyoyeva met with Chinese Foreign Minister Wang Yi to discuss measures to further strengthen ties between the two countries.",
  "articleBody": "The talks focused on the development of the Uzbekistan–China strategic partnership, which Mirziyoyeva said had entered a new stage and was creating broader opportunities for cooperation.\n\n\"Against this backdrop, it was particularly important to discuss the development of our relations in priority areas such as trade, the economy, investment and cultural ties,\" Mirziyoyeva wrote on her Telegram channel.\n\nThe two sides also discussed efforts to develop common positions on international issues, she said.\n\nMirziyoyeva thanked Wang Yi for what she described as a warm and substantive discussion.",
  "author": "Дониёр Тухсинов",
  "publisher": "Kun.uz",
  "datePublished": "2026-08-26T20:18:00+05:00",
  "dateModified": "2026-08-26T20:18:00+05:00",
  "images": ["https://storage.kun.uz/source/1/LR9Y7gjbrY6ne-q1Q4kI8klaYDgx3a5L.jpg"]
}
```

**Latest headlines mode** — one record per headline (real output, captured 2026-08-26):

```json
{
  "_input": "latest",
  "_source": "S2-listing",
  "_scrapedAt": "2026-08-26T17:21:25Z",
  "title": "Saida Mirziyoyeva meets Chinese Foreign Minister Wang Yi",
  "link": "https://kun.uz/en/news/2026/08/26/saida-mirziyoyeva-meets-chinese-foreign-minister-wang-yi",
  "publishedAt": "2026-08-26T20:18:00+05:00",
  "publishedDate": "2026-08-26"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which extraction strategy produced this record (`S1-jsonld+html`, `S1b-custom-page` for feature/listicle articles, or `S2-listing` for latest mode). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short article description/dek (article mode). |
| `articleBody` | string | Full plain-text article content (article mode). |
| `author` | string | Byline name (article mode) — often written in Cyrillic script even on the English edition (see below). |
| `publisher` | string | Publisher organization name (article mode only). |
| `datePublished` / `dateModified` | string | Publish timestamps (article mode only). |
| `images` | array | Article hero image URL(s) (article mode only). |
| `link` | string | Article URL (latest mode). |
| `publishedAt` | string | Precise ISO 8601 publish timestamp (latest mode). |
| `publishedDate` | string | Calendar date only, as a fallback (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).

## Good to know

- This actor covers **Kun.uz's English edition only**, published under the `/en/` path at `kun.uz` — the site also publishes independent Uzbek (Latin and Cyrillic script) and Russian editions on the same domain, which are out of scope.
- Byline names sometimes appear in Cyrillic script even on English-language articles (e.g. `"Дониёр Тухсинов"`) — this is passed through exactly as published, not translated or transliterated.
- A small number of feature/listicle articles (e.g. travel guides) use a different page layout than standard news stories; the actor detects this automatically and still returns the full text (tagged `_source: "S1b-custom-page"`).
- Latest-headlines mode is capped at 20 results per run, matching the site's own "Latest news" page.
