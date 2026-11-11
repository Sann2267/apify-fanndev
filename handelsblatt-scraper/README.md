# Handelsblatt Scraper

Extract full article text or the newest headlines from Handelsblatt (Germany) — no account or subscription needed.

## Why use this actor

- No account or login required
- Full article text included, not just a summary — headline, byline, keywords, section, and publish/update dates
- Also fetches the newest headlines from a single site-wide feed without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's headline feed and returns the newest stories.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.handelsblatt.com/politik/deutschland/merz-china-dilemma-wie-die-deutsche-blockade-in-der-china-politik-europa-laehmt/100248362.html"
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

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://www.handelsblatt.com/politik/deutschland/merz-china-dilemma-wie-die-deutsche-blockade-in-der-china-politik-europa-laehmt/100248362.html",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T20:11:26Z",
  "@type": "NewsArticle",
  "headline": "Merz-China-Dilemma: Wie die deutsche Blockade in der China-Politik Europa lähmt",
  "articleBody": "Vor etwa eineinhalb Wochen geht in Berlin und Brüssel ein Papier aus Peking ein ...",
  "creator": ["Martin Greive", "Jakob Hanke Vela", "Moritz Koch", "Julian Olk"],
  "articleSection": "Politik",
  "keywords": ["China", "Außenpolitik", "Handelspolitik"],
  "isAccessibleForFree": false,
  "datePublished": "2026-08-23T...",
  "dateModified": "2026-08-23T..."
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T20:11:24Z",
  "title": "AfD-Sommerinterviews: Alice Weidel: „Die CDU wird keine einzige Bundestagswahl mehr gewinnen“",
  "link": "https://www.handelsblatt.com/politik/deutschland/afd-sommerinterviews-die-cdu-wird-keine-einzige-bundestagswahl-mehr-gewinnen/100247776.html",
  "guid": "https://www.handelsblatt.com/politik/deutschland/afd-sommerinterviews-die-cdu-wird-keine-einzige-bundestagswahl-mehr-gewinnen/100247776.html",
  "pubDate": "Sun, 23 Aug 2026 18:45:24 GMT",
  "description": "Vor den Landtagswahlen zeigen sich die AfD-Chefs Weidel und Chrupalla im TV siegessicher – nicht nur für Sachsen-Anhalt."
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline (`headline` in article mode, `title` in latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). Absent — not empty, absent — on short wire-brief/live-ticker items; see the actor's technical notes. |
| `creator` / `author` | array | Byline: `creator` is plain name strings, `author` is richer `{name, url, image}` objects (article mode only). |
| `keywords` | array | Topic tags (article mode only). |
| `articleSection` | string | Section name (article mode only). |
| `isAccessibleForFree` | boolean | Handelsblatt's paywall flag. Full text was returned regardless of this flag in testing — see the actor's technical notes. |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `pubDate` | string | Publication timestamp (latest mode). |
| `link` | string | The article URL (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
