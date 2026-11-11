# El Universal (Mexico) Scraper

Extract full article text or the newest headlines from El Universal (eluniversal.com.mx), one of Mexico's largest national newspapers — no account or subscription needed.

## Why use this actor

- No account or login required — free articles extracted in full, with a paywall flag included for premium content
- Full article text included, not just a summary — headline, description, byline(s), keywords, publish/update dates, lead image
- Ad placeholders and WhatsApp-channel promo text are automatically filtered out of the article body
- Strong Mexican national, state, and political coverage
- Also fetches the newest headlines (with keywords and lead image) from the site's rolling news sitemap without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's rolling news sitemap and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.eluniversal.com.mx/nacion/se-va-rocha-otra-vez-le-duro-el-gusto-un-dia/"
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
  "_input": "https://www.eluniversal.com.mx/nacion/se-va-rocha-otra-vez-le-duro-el-gusto-un-dia/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-24T01:56:24Z",
  "headline": "Se va Rocha otra vez; le duró el gusto un día",
  "description": "Antes de las 19:00 horas de ayer, el sinaloense publicó un mensaje en redes sociales con el documento que entregó en el Congreso local",
  "articleBody": "Culiacán.— A sólo 33 horas de haber retomado el cargo de gobernador, Rubén Rocha Moya pidió de nuevo licencia indefinida al Congreso del estado...",
  "datePublished": "2026-08-23T20:00:00-06:00",
  "dateModified": "2026-08-23T23:23:04-06:00",
  "author": "Antonio Hernández",
  "isAccessibleForFree": true,
  "keywords": ["rocha moya", "sinaloa", "sheinbaum", "morena"],
  "image": "https://www.eluniversal.com.mx/resizer/v2/..."
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-24T01:56:21Z",
  "title": "Ataque armado deja un muerto cerca del centro de Mazatlán, Sinaloa; dos personas resultan heridas",
  "link": "https://www.eluniversal.com.mx/estados/ataque-armado-deja-un-muerto-cerca-del-centro-de-mazatlan-sinaloa-dos-personas-resultan-heridas/",
  "publicationDate": "2026-08-24T01:53:15.862Z",
  "keywords": ["culiacan", "sinaloa", "mazatlan", "ataque a balazos"],
  "imageUrl": "https://www.eluniversal.com.mx/resizer/v2/6AVUCMEVO5BVFFIYOUNLQFUZ7I.jpg?auth=...&smart=true&width=1200&height=740"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Teaser/summary (article mode only). |
| `articleBody` | string | Full plain-text article content, ads and promo CTAs filtered out (article mode only). |
| `author` | string | Byline(s), comma-joined when multiple contributors are credited (article mode only). |
| `isAccessibleForFree` | boolean | Whether the site marks this article as free vs. premium (article mode only). |
| `keywords` | array | Tag keywords. |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` / `imageUrl` | string | Lead image URL. |
| `link` | string | Article URL (latest mode). |
| `publicationDate` | string | Publication timestamp (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
