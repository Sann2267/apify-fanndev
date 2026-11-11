# 24.kg Scraper

Extract full article text or the newest headlines from 24.kg, Kyrgyzstan's leading news agency — no account or subscription needed.

## Why use this actor

- No account or login required — fully free, open-access site with no paywall
- Full article text included, not just a summary — headline, description, byline (when published), publish/modified dates, section, and image, reconstructed into clean paragraphs
- Covers **both languages the site publishes in** — Russian (most sections) and Kyrgyz (the `/kyrgyzcha/` section) — each record is tagged with its actual language
- Stable JSON output suitable for pipelines, spreadsheets, or databases
- Automatic retries on temporary network hiccups

## How it works

1. Give the actor one or more article URLs, or switch to `"latest"` mode to get the newest stories automatically.
2. In article mode, the actor opens each URL and pulls out the full text and every publicly available detail about the story.
3. In latest mode, the actor reads the site's RSS feed and returns the newest headlines with a short teaser.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

You don't need to manage retries, rate limits, or figure out the site's internal data format — the actor handles all of that.

## Input

**Article mode** (default):
```json
{
  "mode": "article",
  "urls": [
    "https://24.kg/proisshestvija/386730_vgorodeosh_zaderjali_inostrantsa_pyitavshegosya_dat_vzyatku_militsioneru/"
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
| `mode` | string | `"article"` (default) — extract one or more article URLs. `"latest"` — fetch the newest headlines from the site's RSS feed. |
| `url` | string | A single article URL. Used in article mode. |
| `urls` | array | Multiple article URLs to extract in one run. Used in article mode. |
| `limit` | integer | Max headlines returned in latest mode. Default 10, max 50 (the feed itself carries about 50 items). |
| `maxConcurrency` | integer | How many articles to fetch in parallel in article mode. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Article mode** — one record per URL (real captured output):

```json
{
  "_input": "https://24.kg/proisshestvija/386730_vgorodeosh_zaderjali_inostrantsa_pyitavshegosya_dat_vzyatku_militsioneru/",
  "_source": "S1-jsonld+html",
  "_scrapedAt": "2026-08-26T17:19:43Z",
  "headline": "В городе Ош задержали иностранца, пытавшегося дать взятку милиционеру",
  "description": "В Оше задержан гражданин соседнего государства при даче взятки сотруднику милиции.",
  "articleBody": "В Оше задержан гражданин соседнего государства при даче взятки сотруднику милиции.\n\nКак сообщили в УВД города, ранее был выявлен иностранный гражданин, 1980 года рождения, который находился и работал на территории города без регистрации и разрешительных документов.\n\n... 3 more paragraphs ...",
  "author": "Айжан КЕРИМОВА",
  "datePublished": "2026-08-26T22:51:00+06:00",
  "dateModified": "2026-08-26T22:43:48+06:00",
  "section": "Происшествия",
  "image": "https://24.kg/files/media/466/466523.jpg",
  "keywords": "новости, новости Кыргызстана, новости Киргизии, Кыргызстан, Бишкек, новости Бишкека, Киргизия, важное, новости сегодня",
  "_lang": "ru"
}
```

A Kyrgyz-language article (`/kyrgyzcha/` section) comes back the same shape, just with `"_lang": "ky"` and, on some pieces, `"author": null` — not every Kyrgyz-language article carries a byline.

**Latest headlines mode** — one record per headline, real captured output:

```json
{
  "_input": "latest",
  "_source": "S2-rss",
  "_scrapedAt": "2026-08-26T17:19:43Z",
  "title": "Владимир Путин намерен усилить удары по Киеву — Bloomberg",
  "link": "https://24.kg/obschestvo/386731_vladimir_putin_nameren_usilit_udaryi_pokievu_Bloomberg/",
  "teaser": "Власти РФ планируют новую эскалацию войны против Украины, пишет Bloomberg со ссылкой на близкие к Кремлю анонимные источники.",
  "category": "Общество",
  "pubDate": "Wed, 26 Aug 2026 23:18:00 +0600",
  "guid": "https://24.kg/obschestvo/386731_vladimir_putin_nameren_usilit_udaryi_pokievu_Bloomberg/"
}
```

Latest mode returns a short teaser only — call article mode on the `link` if you need the full text.

| Field | Type | Description |
|---|---|---|
| `_input` | string | The URL you requested, or `"latest"`, for traceability. |
| `_source` | string | Which strategy produced this record. |
| `_scrapedAt` | string | UTC timestamp of when the record was captured. |
| `headline` / `title` | string | Article headline. |
| `description` | string | Short article description/dek (article mode). |
| `articleBody` | string | Full plain-text article content (article mode). |
| `author` | string | Byline name (article mode) — legitimately `null` when the article carries no byline. |
| `datePublished` / `dateModified` | string | ISO 8601 publish/modified timestamps with timezone offset (article mode). |
| `section` | string | Site section name (article mode). |
| `image` | string | Lead image URL (article mode). |
| `keywords` | string | Raw comma-separated keywords string as published (article mode). |
| `_lang` | string | Article language — `"ru"` or `"ky"` (article mode). |
| `link` | string | Article URL (latest mode). |
| `teaser` | string | Short feed teaser (latest mode). |
| `category` | string | Feed category (latest mode). |
| `pubDate` | string | RFC 822 publish timestamp as given by the feed (latest mode). |
| `guid` | string | Feed item GUID — same as `link` on this site (latest mode). |

URLs that could not be processed are **not** written to the dataset — a dataset row is a billable result, and a failure is not a result. They are listed instead in the `ERRORS` record of the run's key-value store (Storage → Key-value store → `ERRORS`), one entry per URL with the reason (`not_found`, `blocked_or_transient`, `http_<code>`), and they are repeated as warnings in the run log.

## Good to know

- The site is bilingual — most sections publish in Russian, the `/kyrgyzcha/` section publishes in Kyrgyz. Both are returned exactly as published, not translated; use `_lang` to tell them apart.
- No English edition exists on this site.
- `latest` mode is capped by the site's own RSS feed size (about 50 items per fetch).
