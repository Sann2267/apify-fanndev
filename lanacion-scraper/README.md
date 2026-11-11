# La Nación Scraper

Extract full article text or the newest headlines from La Nación (lanacion.com.ar), one of Argentina's two largest newspapers — no account or subscription needed.

## Why use this actor

- No account or login required — extracts the full server-rendered article, including opinion columns from named columnists
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, keywords, images, and section
- Honest paywall signal — every record carries the site's own `isAccessibleForFree` flag and a derived `_paywalled` boolean, so you can filter confidently instead of guessing
- Also fetches the newest headlines straight from the site's RSS feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story from the page's structured data (JSON-LD).
3. In latest mode, the actor reads the site's RSS feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.lanacion.com.ar/politica/milei-recrudece-su-ataque-al-periodismo-mas-de-300-mensajes-con-insultos-acusaciones-sin-pruebas-y-nid24082026/"
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
  "_input": "https://www.lanacion.com.ar/politica/milei-recrudece-su-ataque-al-periodismo-mas-de-300-mensajes-con-insultos-acusaciones-sin-pruebas-y-nid24082026/",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-24T17:13:26Z",
  "headline": "Milei recrudece su ataque al periodismo: más de 300 mensajes con insultos, acusaciones sin pruebas y llamados al odio",
  "description": "La última semana apuntó contra decenas de medios y cronistas a los que acusó de conspirar, mentir y extorsionar; a quiénes señaló con nombre y apellido",
  "articleBody": "El presidente Javier Milei intensificó la última semana su ataque contra el periodismo...",
  "datePublished": "2026-08-24T17:04:55.369Z",
  "dateModified": "2026-08-24T17:04:55.573Z",
  "author": "LA NACION",
  "articleSection": "Política",
  "isAccessibleForFree": true,
  "_paywalled": false,
  "isPartOf": null,
  "keywords": ["Javier Milei", "Periodismo"],
  "image": [{"@type": "ImageObject", "url": "https://www.lanacion.com.ar/resizer/v2/..."}],
  "publisher": {"@id": "https://www.lanacion.com.ar/#organization"}
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-24T17:14:32Z",
  "title": "Milei recrudece su ataque al periodismo: más de 300 mensajes con insultos, acusaciones sin pruebas y llamados al odio",
  "link": "https://www.lanacion.com.ar/politica/milei-recrudece-su-ataque-al-periodismo-mas-de-300-mensajes-con-insultos-acusaciones-sin-pruebas-y-nid24082026/",
  "description": "La última semana apuntó contra decenas de medios y cronistas a los que acusó de conspirar, mentir y extorsionar; a quiénes señaló con nombre y apellido",
  "pubDate": "Mon, 24 Aug 2026 17:04:55 +0000",
  "category": "Política"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline — `"LA NACION"` for staff/wire content, or the columnist's name for opinion pieces (article mode only). |
| `articleSection` | string | Section name, e.g. `"Política"`, `"Opinión"` (article mode only). |
| `isAccessibleForFree` | boolean | The site's own paywall flag, passed through as-is (article mode only). |
| `_paywalled` | boolean | `true` only when `isAccessibleForFree` is explicitly `false`. In recon sampling this was never observed — see `CRAWLING_METHOD.md` for the honest breakdown (article mode only). |
| `isPartOf` | object/null | Subscription-product metadata when present, e.g. `"Acceso Digital Monthly Test"` (article mode only). |
| `keywords` | array | Tag list (article mode only). |
| `image` | array | Raw list of `ImageObject` entries as given by the source (article mode only). |
| `publisher` | object | Raw JSON-LD `@id` reference to the publisher, not resolved to a name (article mode only). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |
| `category` | string | Section name (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).

## Paywall note

Every sampled article during development — including opinion columns, normally the most tightly paywalled content at most outlets — came back with `isAccessibleForFree: true` and a full, non-truncated body. The site's subscription infrastructure is visible in the data (`isPartOf.productID`), so this actor never assumes free access: it reads and passes through the real flag from every response rather than hard-coding a verdict. See `CRAWLING_METHOD.md` for the full recon writeup.
