# Clarin Scraper

Extract full article text or the newest headlines from Clarín (clarin.com), Argentina's largest-circulation newspaper — no account or login needed.

## Why use this actor

- No account or login required — HTTP-only, no browser automation
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, section, keywords, image, reconstructed into clean paragraphs
- Honest paywall reporting — a genuine `isAccessibleForFree` / `_paywalled` flag straight from the site's own metadata, sampled on both free and subscriber-only articles (Clarín server-renders the full article text either way; the paywall is a client-side overlay that an HTTP-only scraper never sees, so `articleBody` is always complete)
- Also fetches the newest headlines straight from the site's Google News sitemap without visiting each article individually
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
    "https://www.clarin.com/informacion-general/empleadas-domesticas-cobraran-hora-septiembre-monto-suma-nuevo-salario_0_FxNuO6jbE8.html"
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
  "_input": "https://www.clarin.com/informacion-general/empleadas-domesticas-cobraran-hora-septiembre-monto-suma-nuevo-salario_0_FxNuO6jbE8.html",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-25T10:00:00Z",
  "headline": "Empleadas domésticas: cuánto cobrarán por hora desde septiembre y qué monto se suma al nuevo salario",
  "description": "Los salarios de las trabajadoras de casas particulares volverán a subir en septiembre...",
  "articleBody": "Las empleadas domésticas tendrán una nueva actualización salarial en septiembre de 2026...",
  "author": "Redacción Clarín",
  "publisher": "Clarín",
  "datePublished": "2026-08-24T17:02:56.000Z",
  "dateModified": "2026-08-24T17:02:56.000Z",
  "articleSection": ["Información General"],
  "keywords": ["sueldos y paritarias", "servicio doméstico", "paritarias"],
  "image": "https://www.clarin.com/img/2021/05/03/W3fI6lekj_1256x620__1.jpg",
  "isAccessibleForFree": true,
  "_paywalled": false
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-25T10:00:05Z",
  "title": "Empleadas domésticas: cuánto cobrarán por hora desde septiembre y qué monto se suma al nuevo salario",
  "link": "https://www.clarin.com/informacion-general/empleadas-domesticas-cobraran-hora-septiembre-monto-suma-nuevo-salario_0_FxNuO6jbE8.html",
  "publicationDate": "2026-08-24T17:02:56Z",
  "imageUrl": "https://www.clarin.com/img/2021/05/03/W3fI6lekj_1200x630__1.jpg",
  "imageCaption": "Las empleadas domésticas tendrán un nuevo aumento salarial en septiembre de 2026..."
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content, always complete regardless of paywall status (article mode only). |
| `author` | string | Byline — an individual name for opinion/analysis pieces, `"Redacción Clarín"` for wire-style news (article mode only). |
| `publisher` | string | Always `"Clarín"` (article mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `articleSection` | array | Section name(s), e.g. `["Opinión"]` (article mode only). |
| `keywords` | array | Editorial tags (article mode only). |
| `image` | string | Lead image URL (article mode only). |
| `isAccessibleForFree` | boolean | The site's own paywall metadata flag (article mode only). |
| `_paywalled` | boolean | `true` when `isAccessibleForFree` is `false`. Text is still complete — see note above (article mode only). |
| `link` | string | Article URL (latest mode). |
| `publicationDate` | string | ISO-8601 publish timestamp from the sitemap (latest mode). |
| `imageUrl` / `imageCaption` | string | Lead image and caption from the sitemap (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).

## Paywall note

Clarín gates some content (mostly long-form `/opinion/` pieces) behind a "Solo suscriptores" client-side overlay. This actor never fabricates or truncates text: recon confirmed the server sends the **full** article HTML regardless of subscription status (the gate is JS/CSS applied in the browser, invisible to an HTTP-only fetch). `_paywalled` is a transparent pass-through of the site's own `isAccessibleForFree` flag so downstream consumers know which rows come from subscriber-only sections — it never means the text is cut short.
