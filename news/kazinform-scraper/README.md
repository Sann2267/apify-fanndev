# Kazinform Scraper

Extract full article text or the newest headlines from Kazinform (qazinform.com), Kazakhstan's state news agency, English edition — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline, publish/modified dates, reconstructed into clean paragraphs
- Latest-headlines mode returns **full article text and byline for every item**, not just titles — the site feed embeds the complete body, so you often don't need to fetch individual article pages at all
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's feed, which already embeds full article HTML, and returns the newest stories with full text.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://qazinform.com/news/mountain-goats-spotted-in-kolsay-lakes-national-park-e625e0"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines with full text. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50. |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (real output, truncated here for readability):

```json
{
  "_input": "https://qazinform.com/news/mountain-goats-spotted-in-kolsay-lakes-national-park-e625e0",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T06:40:36Z",
  "headline": "Mountain goats spotted in Kolsay Lakes National Park",
  "description": "Rangers spotted a group of mountain goats during a routine patrol in Kolsay Lakes National Park, Qazinform News Agency reports, citing Kazakhstan's Ministry of Ecology and Natural Resources.",
  "articleBody": "The footage shows several mountain goats roaming freely along the slopes as park staff watched them for a while before they moved on.\n\nMountain goats naturally inhabit high-altitude, rocky terrain, and sightings like this offer a rare glimpse of them in their natural environment.\n\nAs Qazinform previously reported, a female Amur tiger was released into the wild at the Ile-Balkhash State Nature Reserve on July 31, marking the first return of a tiger to Kazakhstan's natural habitat in more than 70 years.",
  "author": "Nariman Mergalym",
  "authorPosition": "Автор",
  "publisher": "«Inform»",
  "datePublished": "2026-08-26 11:25:00+00:00",
  "dateModified": "2026-08-26 11:25:00+00:00",
  "images": ["https://img.inform.kz/kazinform-photobank/media/2026-08-26/7db376f9-ad2f-487c-a0ad-65aad448df55.jpeg"]
}
```

**Latest headlines mode** — one record per headline, with full text and byline already included:

```json
{
  "_input": "latest",
  "_source": "S2-feed",
  "_scrapedAt": "2026-08-26T06:40:26Z",
  "title": "Nearly 390,000 obtain jobs in Kazakhstan since Jan",
  "link": "https://qazinform.com/news/nearly-390000-obtain-jobs-in-kazakhstan-since-jan-10ec12",
  "teaser": "As of August 1, 2026, 388,512 people have been employed in Kazakhstan, Qazinform News Agency reports.",
  "articleBody": "As of August 1, 2026, 388,512 people have been employed in Kazakhstan, Qazinform News Agency reports.\n\nAccording to the Labor and Social Protection Ministry, since the beginning of the year, 293,241 people secured stable positions, making up the majority of new hires.\n\nPermanent employment ensures a steady income and access to labor and social guarantees under the law.\n\nDevelopment of digital employment services, including e-Labor Exchange and cooperation with employers, has improved job matching between candidates and vacancies.\n\nBesides, ongoing professional education and employment support programs help citizens gain in-demand skills and increase competitiveness in the labor market.\n\nEarlier Qazinform reported, formal employment in Kazakhstan grows by nearly 150,000.",
  "author": "Zhanna Nurgaliyeva",
  "thumbnail": "https://img.inform.kz/kazinform-photobank/media/2026-08-25/... (truncated)",
  "pubDate": "Wed, 26 Aug 2026 11:08:00 +0500"
}
```

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `articleBody` | string | Full plain-text article content, present in both modes. |
| `author` | string | Byline name, present in both modes. |
| `authorPosition` | string | Byline role/title (article mode only) — often untranslated Russian text on this site (see below). |
| `publisher` | string | Publisher organization name (article mode only) — the agency's own legal name, `«Inform»`. |
| `datePublished` / `dateModified` | string | Publish timestamps (article mode only). |
| `images` | array | Article hero image URL(s) (article mode only). |
| `link` | string | Article URL (latest mode). |
| `teaser` | string | Short feed teaser (latest mode). |
| `thumbnail` | string | Lead image URL (latest mode). |
| `pubDate` | string | RFC-822 publish timestamp as given by the feed (latest mode). |

A record with `_error` instead of article fields means that URL could not be processed (for example, `"_error": "not_found"` for a removed article).

## Good to know

- This actor covers **Kazinform's English edition only**, published at `qazinform.com` — the flagship `inform.kz` domain serves Russian/Kazakh content and is a separate scope.
- The site's own metadata sometimes carries untranslated Russian text even on English-language pages (e.g. the byline's role label reads `"Автор"`, meaning "Author") — this is passed through exactly as published, not translated.
