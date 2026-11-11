# BILD Scraper

Extract full article details or the newest headlines from BILD, Germany's largest tabloid — no account or subscription needed.

## Why use this actor

- No account or login required
- Rich article detail: headline, description, byline with author job title, publish/update dates, topic keywords, and lead image
- Full article text where publicly available, plus a clear flag on articles behind BILD's paid tier
- Also fetches the newest headlines across all sections without visiting each article individually
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

**Note on paid articles:** A subset of BILD articles ("BILDplus") are limited to subscribers. This actor returns everything that's publicly visible — headline, description, author, dates, keywords, and the free preview text — and flags such records with `_paywalled: true`.

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode.
2. In article mode, the actor opens each URL and pulls out every publicly available detail about the story.
3. In latest mode, the actor reads the site-wide newest-articles feed and returns the freshest stories across all sections.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.bild.de/unterhaltung/tv-fernsehformate/steffen-henssler-diese-wette-kostet-ihn-den-bart-6a8ab2e40e5ea956d6e4f35d"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines site-wide. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (free article, truncated here for readability — the real record includes the full author image/link and complete article text):

```json
{
  "_input": "https://www.bild.de/unterhaltung/tv-fernsehformate/steffen-henssler-diese-wette-kostet-ihn-den-bart-6a8ab2e40e5ea956d6e4f35d",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-24T00:27:37Z",
  "_paywalled": false,
  "headline": "Steffen Henssler: Diese Wette kostet ihn den Bart | Unterhaltung",
  "description": "Steffen Henssler verliert bei „Grill den Henssler“ eine Bart-Wette. Erfahren Sie, warum der Koch im nächsten Sommer-Special nur mit Schnurrbart auftritt.",
  "url": "https://www.bild.de/unterhaltung/tv-fernsehformate/steffen-henssler-diese-wette-kostet-ihn-den-bart-6a8ab2e40e5ea956d6e4f35d",
  "datePublished": "2026-08-23T23:52:24.825Z",
  "dateModified": "2026-08-23T23:52:24.825Z",
  "author": [
    { "@type": "Person", "name": "Nora Henze", "jobTitle": "Freie Redakteurin", "sameAs": ["https://www.linkedin.com/in/norahenze/"] }
  ],
  "keywords": "Henssler Steffen, Grill den Henssler, VOX, TV-Koch, Kochsendung, Team First",
  "isAccessibleForFree": true,
  "publisher": { "@type": "NewsMediaOrganization", "name": "BILD", "url": "https://www.bild.de/" },
  "articleBody": "Magdeburg (Sachsen-Anhalt) – Zum Auftakt der neuen „Grill den Henssler“-Sommer-Specials traten am Sonntag Dr. Carola „Doc Caro“ Holzner (44), Comedian Tony Bauer (30) und Tokio-Hotel-Drummer Gustav Sch...  /* full text, 3017 chars total */"
}
```

A paywalled ("BILDplus") article returns the same shape with `_paywalled: true` and a short `articleBody` (a few hundred characters instead of the full text):

```json
{
  "_input": "https://www.bild.de/sport/fussball/sc-freiburg-schuster-spricht-ueber-atubolu-und-eintracht-6a8b4132c3692834ff6da623",
  "_source": "S1-jsonld",
  "_paywalled": true,
  "headline": "SC Freiburg: Schuster spricht über Atubolu und Eintracht | Sport",
  "isAccessibleForFree": false,
  "articleBody": "Nach dem 5:1-Pokalerfolg... /* teaser only, ~650 chars */"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest:bild.de",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-24T00:26:51Z",
  "title": "Waldbrand in den USA: 90.000 Menschen in Nevada evakuiert",
  "link": "https://www.bild.de/news/ausland/waldbrand-in-den-usa-90-000-menschen-in-nevada-evakuiert-6a8b8875c3692834ff6da7b2",
  "publicationDate": "2026-08-24T02:21:51+02:00",
  "keywords": "Feuerwehr, Waldbrand, Brand, Polizei, Nevada, USA, Team First"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest:bild.de"` in latest mode. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `_paywalled` | boolean | `true` if the article is behind BILD's paid tier (article mode only). |
| `headline` / `title` | string | Article headline. |
| `description` | string | Article summary/dek (article mode). |
| `author` | array | Byline(s), with job title and profile link where available. |
| `datePublished` / `dateModified` / `publicationDate` | string | Publication timestamps. |
| `keywords` | string | Comma-separated topic tags. |
| `articleBody` | string | Full article text, or a short teaser for paywalled articles. |
| `link` / `url` | string | The article URL. |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.
