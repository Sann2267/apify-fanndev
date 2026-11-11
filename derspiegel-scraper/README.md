# Der Spiegel Scraper

Extract full article text or the newest headlines from Der Spiegel (spiegel.de), Germany's leading news magazine — no account or subscription needed for free articles.

## Why use this actor

- No account or login required
- Full article text for free articles — headline, byline, section, keywords, and publish/update dates
- Honest paywall handling — premium "SPIEGEL+" articles are clearly flagged with `_paywalled: true` instead of returning empty or fabricated text
- Also fetches the newest headlines from a single site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL, checks whether it's free or paywalled, and pulls out the full text (or a clear paywall flag) plus every publicly available detail about the story.
3. In latest mode, the actor reads the site's headline feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.spiegel.de/ausland/frankreich-raphael-glucksmann-kuendigt-kandidatur-fuer-praesidentschaftswahl-2027-an-a-03ca9099-36fe-4b99-96c2-1f4f390ae551"
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
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode, free article** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.spiegel.de/ausland/frankreich-raphael-glucksmann-kuendigt-kandidatur-fuer-praesidentschaftswahl-2027-an-a-03ca9099-36fe-4b99-96c2-1f4f390ae551",
  "_source": "S1-html",
  "_scrapedAt": "2026-08-23T22:59:39Z",
  "@type": "NewsArticle",
  "headline": "Macron-Nachfolge: Raphaël Glucksmann will französischer Präsident werden",
  "articleBody": "Der französische EU-Abgeordnete Raphaël Glucksmann möchte bei der Präsidentschaftswahl im kommenden Jahr antreten ...",
  "articleSection": "Ausland",
  "isAccessibleForFree": true,
  "_paywalled": false,
  "author": { "@type": "Organization", "name": "DER SPIEGEL" },
  "datePublished": "2026-08-23T22:49:00+02:00",
  "keywords": ["Frankreich"]
}
```

**Article mode, premium ("SPIEGEL+") article:**

```json
{
  "_input": "https://www.spiegel.de/wirtschaft/unternehmen/deutschlands-wirtschaft-korrigierte-zahlen-relativieren-wachstumssorgen-kolumne-a-45a81b6b-83dd-4e57-8728-44f39abdeadc",
  "_source": "S1-html",
  "headline": "Wachstum? Welches Wachstum?: Wir sind (ein bisschen) besser als wir glauben",
  "articleBody": null,
  "isAccessibleForFree": false,
  "_paywalled": true,
  "author": { "@type": "Person", "name": "Henrik Müller" }
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T22:59:28Z",
  "title": "Frankreich: Raphaël Glucksmann kündigt Kandidatur für Präsidentschaftswahl 2027 an",
  "link": "https://www.spiegel.de/ausland/frankreich-raphael-glucksmann-kuendigt-kandidatur-fuer-praesidentschaftswahl-2027-an-a-03ca9099-36fe-4b99-96c2-1f4f390ae551",
  "guid": "03ca9099-36fe-4b99-96c2-1f4f390ae551",
  "pubDate": "Sun, 23 Aug 2026 22:49:00 +0200",
  "description": "Der französische EU-Abgeordnete Raphaël Glucksmann hat seine Kandidatur für die Präsidentschaftswahl im April 2027 angekündigt.",
  "categories": ["Ausland"]
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `_paywalled` | boolean | `true` if this is a premium SPIEGEL+ article with no body text available (article mode only). |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string or null | Full plain-text article content, or `null` for paywalled articles (article mode only). |
| `isAccessibleForFree` | boolean | Publisher's own free/premium flag, passed through raw. |
| `author` | object | Byline (article mode only) — `Person` or `Organization` (e.g. wire-brief items are bylined to "DER SPIEGEL" directly). |
| `articleSection` | string | Section name (article mode only). |
| `categories` | array | Section tag (latest mode only). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article). This is distinct from `_paywalled: true`, which means the request succeeded but the content is behind SPIEGEL+.
