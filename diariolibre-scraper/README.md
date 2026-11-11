# Diario Libre Scraper

Extract full article text or the newest headlines from Diario Libre (diariolibre.com), one of the leading national newspapers of the Dominican Republic — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, section, keywords, publish/modified dates
- Also fetches the newest headlines straight from the site's own RSS feed, and that feed already carries the **complete article body**, not just a teaser — so `latest` mode alone can be enough for many pipelines
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls the full text and every publicly available detail about the story from the page's structured data (JSON-LD).
3. In latest mode, the actor reads the site's front-page RSS feed and returns the newest stories, including their full text.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.diariolibre.com/actualidad/educacion/2026/08/25/reclaman-finalizar-reconstruccion-de-escuela-en-santiago/3638691"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50 (the feed itself carries roughly 28 items, so fewer may come back). |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.diariolibre.com/actualidad/educacion/2026/08/25/reclaman-finalizar-reconstruccion-de-escuela-en-santiago/3638691",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-25T17:56:15Z",
  "headline": "Denuncian retraso en reconstrucción deja a más de 800 estudiantes fuera de las aulas en Santiago - Diario Libre",
  "alternativeHeadline": "Reclaman finalizar reconstrucción de escuela en Santiago",
  "description": "Protesta en Santiago por avance en reconstrucción de escuela que afecta a 800 estudiantes",
  "articleBody": "Padres, madres, profesores y dirigentes comunitarios se encadenaron este martes frente a la escuela Rafaela Jiminián...",
  "author": "Edward Fernández",
  "publisher": "Diario Libre",
  "articleSection": "actualidad,educacion",
  "keywords": ["Ministerio de Educación", "estudiantes afectados", "reconstrucción escuela", "protesta Santiago", "condiciones aulas"],
  "datePublished": "2026-08-25T10:39:00-04:00",
  "dateModified": "2026-08-25T11:28:31-04:00",
  "image": "https://resources.diariolibre.com/images/2026/08/25/avance-en-reconstruccion-de-escuela-en-santiago-36a51978-focus-0-0-1200-675.jpg",
  "inLanguage": "es",
  "canonicalUrl": "https://www.diariolibre.com/actualidad/educacion/2026/08/25/reclaman-finalizar-reconstruccion-de-escuela-en-santiago/3638691"
}
```

**Latest headlines mode** — one record per headline (also carries the full body):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-25T17:55:42Z",
  "title": "Juez critica la violencia de género en la Suprema Corte",
  "link": "https://www.diariolibre.com/actualidad/justicia/2026/08/25/juez-critica-la-violencia-de-genero-en-la-suprema-corte/3638...",
  "guid": "0d6adbdb-2de9-4362-8e1f-1a96a8c7d5a8",
  "pubDate": "Tue, 25 Ago 2026 13:06:00 GMT",
  "category": "Actualidad",
  "subcategory": "Justicia",
  "author": "Jesús Vásquez",
  "place": "Santo Domingo",
  "topics": ["Violencia de género", "Suprema Corte de Justicia", "Acuerdos judiciales", "justicia penal", "Fran Soto Sánchez"],
  "principalTopic": "Violencia de género",
  "articleBody": "Al reflexionar sobre los criterios judiciales que se han adoptado en la Suprema...",
  "readingTime": 3,
  "image": "https://resources.diariolibre.com/images/2022/03/31/shutterstock1728799840-2786a....jpg",
  "imageCaption": null
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record (`S1-jsonld`, `S1-jsonld+meta-fallback`, `S2-rss`, or `none` on failure). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `alternativeHeadline` | string | Secondary/shorter headline variant (article mode only). |
| `description` | string | Short summary (article mode only). |
| `articleBody` | string | Full plain-text article content — present in **both** modes. |
| `author` | string | Byline name. |
| `publisher` | string | Always `"Diario Libre"` (article mode only). |
| `articleSection` | string | Comma-joined section path, e.g. `"actualidad,educacion"` (article mode only). |
| `keywords` | array | Keyword tags (article mode only). |
| `category` / `subcategory` / `place` / `topics` / `principalTopic` | string/array | Taxonomy fields from the RSS feed's own tagging groups (latest mode only). |
| `datePublished` / `dateModified` | string | ISO-8601 timestamps (article mode only). |
| `pubDate` | string | Publish timestamp as given by the feed — non-standard, Spanish month abbreviation (latest mode only). |
| `readingTime` | integer | Estimated reading time in minutes (latest mode only). |
| `guid` | string | Internal RSS item id, a UUID (latest mode only). |
| `link` | string | Article URL (latest mode only). |
| `image` / `imageCaption` | string | Lead image URL and caption. |
| `canonicalUrl` / `inLanguage` | string | Canonical URL and language code from ld+json (article mode only). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
