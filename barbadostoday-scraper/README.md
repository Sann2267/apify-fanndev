# Barbados Today Scraper

Extract full article text or the newest headlines from Barbados Today (barbadostoday.bb),
Barbados' leading digital-native news outlet — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, byline, publish date, categories,
  tags, and lead image, reconstructed into clean paragraphs
- Latest headlines come back just as rich as single-article lookups — full body text included,
  not just a title and link
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories
   automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly
   available detail about the story.
3. In latest mode, the actor asks the site directly for its newest posts and returns them with the
   same level of detail as article mode.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the
actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://barbadostoday.bb/2026/08/25/us175m-health-facilities-targeted-for-2029-opening/"
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

**Article mode** — one record per URL (`articleBody` truncated here for readability), captured
live from a real run:

```json
{
  "_input": "https://barbadostoday.bb/2026/08/25/us175m-health-facilities-targeted-for-2029-opening/",
  "_source": "S1-wpapi",
  "_scrapedAt": "2026-08-26T06:40:40Z",
  "id": 472458,
  "slug": "us175m-health-facilities-targeted-for-2029-opening",
  "link": "https://barbadostoday.bb/2026/08/25/us175m-health-facilities-targeted-for-2029-opening/",
  "headline": "US$175m health facilities targeted for 2029 opening",
  "description": "Four major health facilities being developed under Barbados’ US$175 million Health Services Resilience Programme are expected to be up and running by 2029. The programme covers the new Geriatric Hospital…",
  "articleBody": "Four major health facilities being developed under Barbados’ US$175 million Health Services Resilience Programme are expected to be up and running by 2029.\n\nThe programme covers the new Geriatric Hospital in Waterford, St Michael; Roseville Halfway House in St Peter; an expansion at the Queen Elizabeth Hospital and Odle’s Glenn Senior Village in St George.\n\nThe plan also expands digital health services, adding a new health information system to improve access to medical records and connect all levels of healthcare facilities... (5023 chars total)",
  "date": "2026-08-25T22:26:18",
  "date_gmt": "2026-08-26T02:26:18",
  "modified": "2026-08-25T23:06:11",
  "modified_gmt": "2026-08-26T03:06:11",
  "author": "Shanna Moore",
  "authorSlug": "shanna-moore",
  "authorLink": "https://barbadostoday.bb/author/shanna-moore/",
  "categories": ["Health", "Local News"],
  "tags": ["Headline", "Headlines"],
  "featuredImage": {
    "url": "https://barbadostoday.bb/wp-content/uploads/2026/08/Blackman-Philips-Perch-2.png",
    "width": 800,
    "height": 416,
    "altText": null
  },
  "guid": "https://barbadostoday.bb/?p=472458",
  "contentProtected": false
}
```

**Latest headlines mode** — one record per headline, same rich shape as article mode:

```json
{
  "_input": "latest",
  "_source": "S1-wpapi",
  "_scrapedAt": "2026-08-26T06:40:42Z",
  "id": 472480,
  "slug": "st-lucy-water-relief-extended-as-filtration-project-delayed",
  "link": "https://barbadostoday.bb/2026/08/25/st-lucy-water-relief-extended-as-filtration-project-delayed/",
  "headline": "St Lucy water relief extended as filtration project delayed",
  "description": "Prime Minister Mia Mottley has announced that basic water rate relief for affected St Lucy residents will continue until a new filtration system is installed, after production and supply chain…",
  "articleBody": "Prime Minister Mia Mottley has announced that basic water rate relief for affected St Lucy residents will continue until a new filtration system is installed, after production and supply chain delays pushed back the project.\n\nThe relief had been due to end in September, but Mottley said Government would continue to honour its commitment while work at the Barbados Water Authority’s (BWA) Alleynedale facility is completed... (4624 chars total)",
  "date": "2026-08-25T21:59:31",
  "date_gmt": "2026-08-26T01:59:31",
  "modified": "2026-08-25T21:59:31",
  "modified_gmt": "2026-08-26T01:59:31",
  "author": "Ricardo Roberts",
  "authorSlug": "ricardo-roberts",
  "authorLink": "https://barbadostoday.bb/author/ricardo-roberts/",
  "categories": ["Community", "Local News"],
  "tags": ["Headline", "Headlines"],
  "featuredImage": {
    "url": "https://barbadostoday.bb/wp-content/uploads/2026/08/Prime-Minister-Mia-Mottley-addresses-the-media-at-the-BWA-Alleynedale-Pumping-Station-in-St.-Lucy-scaled-e1787709536713.jpg",
    "width": 1441,
    "height": 917,
    "altText": null
  },
  "guid": "https://barbadostoday.bb/?p=472480",
  "contentProtected": false
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record — `S1-wpapi` (normal) or `S2-jsonld+html` (fallback, used only if the site's REST API call fails). |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `id` | number | Internal numeric post ID. |
| `slug` | string | URL slug of the post. |
| `link` | string | Canonical article URL. |
| `headline` | string | Article headline. |
| `description` | string | Short summary from the site's own excerpt. |
| `articleBody` | string | Full plain-text article content. |
| `date` / `date_gmt` | string | Publish date/time, site-local (AST, UTC-4) and UTC. |
| `modified` / `modified_gmt` | string | Last-modified date/time, site-local and UTC. |
| `author` | string | Byline name. |
| `authorSlug` / `authorLink` | string | The author's site archive slug/URL. |
| `categories` / `tags` | array | Section and tag labels attached to the post. |
| `featuredImage` | object | Lead image URL, dimensions, and alt text. |
| `guid` | string | WordPress-internal GUID URL. |
| `contentProtected` | boolean | The site's own paywall flag — always `false` on every article sampled; this site has no paywall. |

A record with `_error` instead of article fields means that URL could not be processed:
`"not_found"` for a deleted/never-existed article, `"not_article"` for a page that isn't an
article, or `"http_<code>"` / `"blocked_or_transient"` for a transient site/network issue.
