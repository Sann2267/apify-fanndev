# Philippine Daily Inquirer Scraper

Extract full article text or the newest headlines from the Philippine Daily Inquirer (inquirer.net), the Philippines' most-read English-language news website — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, ad-supported site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/update dates, lead image
- Works across every Inquirer vertical (news, lifestyle, business, sports, etc. — all share the same underlying template)
- Automatically fixes a site-specific double-encoding quirk in the article body so you get clean, readable text instead of raw markup
- Also fetches the newest headlines from the site-wide feed without visiting each article individually
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
    "https://newsinfo.inquirer.net/2290506/lacson-inducing-perjury-may-bar-officials-from-office"
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
| `url` | string | A single article URL (any inquirer.net subdomain). Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 30. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (truncated here for readability):

```json
{
  "_input": "https://newsinfo.inquirer.net/2290506/lacson-inducing-perjury-may-bar-officials-from-office",
  "_source": "S1-jsonld",
  "_scrapedAt": "2026-08-23T23:44:05Z",
  "headline": "Lacson: Inducing perjury may bar officials from office",
  "description": "Sen. Panfilo Lacson —File photo by Niño Jesus Orbeta/Inquirer\n\n\n\nMANILA, Philippines — Public officials who induce another person to commit perjury...",
  "articleBody": "MANILA, Philippines — Public officials who induce another person to commit perjury may themselves be treated as principals in the crime and face disqualification from public office, Sen. Panfilo “Ping” Lacson said...",
  "datePublished": "2026-08-24T04:30:00+08:00",
  "dateModified": "2026-08-24T04:30:00+08:00",
  "author": "Tina G. Santos",
  "image": "https://newsinfo.inquirer.net/files/2026/07/Panfilo-Lacson-24July2026_2.jpg"
}
```

**Latest headlines mode** — one record per headline:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-23T23:44:04Z",
  "title": "Flood, waste, and a two-way street",
  "link": "https://lifestyle.inquirer.net/579590/flood-waste-and-a-two-way-street/",
  "guid": "https://lifestyle.inquirer.net/579590/flood-waste-and-a-two-way-street/",
  "pubDate": "Mon, 24 Aug 2026 06:30:00 +0800",
  "description": "The recent habagat rains left behind piles of trash clogging our drains and waterways, putting to question our role in the flooding.... Keep on reading: Flood, waste, and a two-way street",
  "imageUrl": "https://lifestyle.inquirer.net/files/2026/08/AFP__20260817__C4TQ9WG__v1__HighRes__PhilippinesWeather-620x413.jpg"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | The site's own meta description (article mode) or feed teaser (latest mode). |
| `articleBody` | string | Full plain-text article content, cleaned of WordPress markup (article mode only). |
| `author` | string | Byline (article mode only). |
| `datePublished` / `dateModified` | string | Publication timestamps (article mode). |
| `image` / `imageUrl` | string | Lead image URL. |
| `pubDate` | string | Publication timestamp (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).
