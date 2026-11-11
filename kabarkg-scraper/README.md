# Kabar.kg Scraper

Extract full article text or the newest headlines from Kabar (en.kabar.kg), the National News Agency of the Kyrgyz Republic, English edition — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, category, publish/modified dates, and clean reconstructed paragraphs
- Latest-headlines mode reads the site's news sitemap directly, so you get the newest stories in real time without polling the homepage
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's news sitemap and returns the newest headlines with their publish times and links.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://en.kabar.kg/news/kyrgyzstan-unveils-official-medals-for-6th-world-nomad-games/"
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

**Article mode** — one record per URL (real output, captured 2026-08-26):

```json
{
  "_input": "https://en.kabar.kg/news/kyrgyzstan-unveils-official-medals-for-6th-world-nomad-games/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T17:18:45Z",
  "headline": "Kyrgyzstan unveils official medals for 6th World Nomad Games",
  "description": "Bishkek, August 26, 2026. /Kabar/. The State Agency for Physical Culture and Sports unveiled the official designs of the gold, silver, and bronze medals that will be awarded to the…",
  "articleBody": "Bishkek, August 26, 2026. /Kabar/. The State Agency for Physical Culture and Sports unveiled the official designs of the gold, silver, and bronze medals that will be awarded to the winners and runners-up of the 6th World Nomad Games.\n\nAccording to the agency, the medal design is based on the traditional philosophy of the Kyrgyz people. The official logo of the Nomad Games is placed in the center of each medal.\n\nThe double-sided medals will be presented with a stand designed for their functional use.\n\nIt is noted that the winners and runners-up of the VI World Nomad Games will receive these medals, inscribing their names in the history of global nomadic sports.",
  "author": "Kabar",
  "publisher": "Kabar",
  "category": "WNG-2026",
  "sourceCredit": "WNG media headquarters",
  "datePublished": "2026-08-26T17:07:57+06:00",
  "dateModified": "2026-08-26T17:07:57+06:00",
  "image": ["https://en.kabar.kg/media/images/5f8a21.2e16d0ba.fill-1200x630.format-jpeg.jpegquality-65.jpg"]
}
```

**Latest headlines mode** — one record per headline (real output, captured 2026-08-26):

```json
{
  "_input": "latest",
  "_source": "S2-sitemap",
  "_scrapedAt": "2026-08-26T17:18:34Z",
  "title": "Kyrgyzstan unveils official medals for 6th World Nomad Games",
  "link": "https://en.kabar.kg/news/kyrgyzstan-unveils-official-medals-for-6th-world-nomad-games/",
  "pubDate": "2026-08-26T17:03:00+06:00"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short lede snippet, from the site's own metadata (article mode). |
| `articleBody` | string | Full plain-text article content (article mode). |
| `author` | string | Byline — always "Kabar" (the agency itself); this is wire-service content, not individually bylined. |
| `publisher` | string | Publisher organization name — "Kabar" (article mode). |
| `category` | string | Section label, e.g. "Central Asia", "Society" (article mode). |
| `sourceCredit` | string | Optional attributed-source line, e.g. "Akorda" (article mode) — absent on agency-original stories. |
| `datePublished` / `dateModified` | string | Publish timestamps (article mode). |
| `image` | array | Article hero image URL(s) (article mode). |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | ISO 8601 publish timestamp from the news sitemap (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed or mistyped article URL).

## Good to know

- This actor covers **Kabar's English edition only**, published at `en.kabar.kg`. The flagship `kabar.kg` domain serves Kyrgyz-language content, and `ru.kabar.kg`/`tr.kabar.kg` serve Russian/Turkish — all separate scopes, each its own subdomain.
- All content is wire-service/agency-attributed (`author` is always "Kabar"), consistent with a state news agency — there are no individual journalist bylines to extract.
- On rare articles, the upstream site itself serves a body that is truncated mid-word — this is passed through exactly as published, not a scraper bug.
