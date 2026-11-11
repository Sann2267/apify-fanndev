# Gazeta.uz Scraper

Extract full article text or the newest headlines from Gazeta.uz, Uzbekistan's major independent news portal, English edition — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, dek, byline, section, tags, publish date, reconstructed into clean paragraphs
- Latest-headlines mode gives you the newest stories with a teaser, lead image and byline in one call — pull individual article URLs afterwards for the full text
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's RSS feed and returns the newest stories with title, teaser, image and byline.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://www.gazeta.uz/en/2026/08/26/usd-sum/"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the RSS feed. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50 (the feed itself only carries 20 items). |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

This actor covers **Gazeta.uz's English edition only** (`gazeta.uz/en/`) — see "Good to know" below.

## Output

**Article mode** — one record per URL (real output, captured 2026-08-26):

```json
{
  "_input": "https://www.gazeta.uz/en/2026/08/26/usd-sum/",
  "_source": "S1-microdata+html",
  "_scrapedAt": "2026-08-26T17:14:58Z",
  "headline": "US dollar exchange rate in Uzbekistan falls to lowest level since August 2023",
  "dek": "The official US dollar exchange rate fell to 11,778.52 soums, its lowest level since the August 2023 devaluation. The soum has strengthened by approximately 1.9% against the dollar in August, in line with the global trend of a weaker US currency, economist Mirkomil Kholboev said.",
  "description": "The official US dollar exchange rate fell to 11,778.52 soums, its lowest level since the August 2023 devaluation. The soum has strengthened by approximately 1.9% against the dollar in August, in line with the global trend of a weaker US currency, economist Mirkomil Kholboev said.",
  "articleBody": "The official US dollar exchange rate in Uzbekistan fell to 11,778.52 soums on 26 August, reaching its lowest level since the sharp depreciation of the soum in August 2023.\n\nAccording to the Central Bank, the dollar fell by 39.55 soums following Tuesday's trading session. This was the fourth new low for the dollar in the past month .\n\nDynamics of the US dollar exchange rate against the soum since the beginning of 2026. Source: Central Bank / Gazeta\n\nAt commercial banks, the dollar is mostly being sold for 11,840−11,875 soums.\n\n... 8 more paragraphs ...\n\nThe IMF previously reclassified Uzbekistan's de facto exchange-rate system from \"crawl-like\" to \"floating\".",
  "author": "Gazeta",
  "section": "Economy",
  "tags": ["central bank", "dollar", "dollar exchange rate", "exchange rate", "mirkomil kholboev", "soum"],
  "datePublished": "2026-08-26T09:24:44+05:00",
  "image": "https://www.gazeta.uz/media/img/2026/04/u0fbectcaf3te4ZXNkt17769274800809_205119_og.webp?r=1787718284"
}
```

**Latest headlines mode** — one record per headline (real output, captured 2026-08-26):

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T17:14:43Z",
  "title": "External shocks have yet to directly affect Uzbekistan — Central Bank chief",
  "link": "https://www.gazeta.uz/en/2026/08/26/cbu/",
  "description": "Global oil and food price increases have yet to directly affect Uzbekistan, Central Bank chief Timur Ishmetov said. The regulator is monitoring possible second-round effects and is ready to act if inflation continues to decline or if upside risks materialize, he noted.",
  "author": "Gazeta",
  "image": "https://www.gazeta.uz/media/img/2026/08/l3ujvqoopqes2YJHhuR17876473885890_b.webp",
  "pubDate": "Wed, 26 Aug 2026 06:42:00 GMT"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `dek` | string | Sub-headline / lede sentence (article mode only). |
| `description` | string | Short summary from meta tags (article mode) or RSS teaser (latest mode). |
| `articleBody` | string | Full plain-text article content (article mode only). |
| `author` | string | Byline — always institutional ("Gazeta" / "Gazeta.uz"), even on guest op-eds (see below). |
| `section` | string | Site section, e.g. "Economy", "Politics" (article mode only). |
| `tags` | array | Article topic tags (article mode only). |
| `datePublished` | string | ISO 8601 publish date with UTC+5 offset (article mode only). |
| `image` | string | Lead image URL. |
| `link` | string | Article URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).

## Good to know

- This actor covers **Gazeta.uz's English edition only**, published under `gazeta.uz/en/`. The site also publishes Russian (`/ru/`), Uzbek Cyrillic (`/uz/`) and Uzbek Latin (`/oz/`) editions on the same domain — out of scope for this actor.
- The byline is **always the institutional name** ("Gazeta" or "Gazeta.uz"), never the actual writer — confirmed even on a piece explicitly headlined as an op-ed by a named guest author. This is a site metadata limitation, not a bug in this actor: the real author's name (when there is a named guest author) is only findable in the headline/body text, not structured data.
- A small subset of longform "Stories" pieces (under the site's Stories section) use a different visual page-builder template that this actor does not support — these return an error rather than a partial record.
- `latest` mode returns a teaser, not the full article body — pass the returned `link` values back into `article` mode to get full text.
