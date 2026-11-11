# Crawling Method — Kabar.kg (English edition)

**Last verified:** 2026-08-26

Kabar is the National News Agency of the Kyrgyz Republic, Kyrgyzstan's
state news agency. This is the second Central Asia outlet added to this
portfolio (after `kazinform-scraper` for Kazakhstan) and the first from
Kyrgyzstan.

## Domain scoping — English edition lives on a separate subdomain

The flagship domain `kabar.kg` serves Kyrgyz-language content
(`<html lang="ky">`). A language switcher in the page header
(`div.language-select-block`) links to three other editions, each its
own subdomain, not a path prefix:

```html
<div class="language-select-block">
    <button class="language-select">Кыр</button>
    <ul class="language-select-list">
        <li><a href="https://ru.kabar.kg">Рус</a></li>
        <li><a href="https://en.kabar.kg">Eng</a></li>
        <li><a href="https://tr.kabar.kg">Tur</a></li>
    </ul>
</div>
```

Confirmed `kabar.kg/en/`, `/eng/`, `/ru/`, `/ky/`, `/kg/` all 404 — there
is no path-prefix scheme. `en.kabar.kg` is the dedicated English-edition
site (`<html lang="en">`, own article content, e.g. "Kyrgyzstan unveils
official medals for 6th World Nomad Games"). This actor is scoped
**entirely to `en.kabar.kg`** — the same pattern as `qazinform.com` for
`kazinform-scraper`. `kabar.kg` (Kyrgyz), `ru.kabar.kg` (Russian), and
`tr.kabar.kg` (Turkish) are out of scope.

## robots.txt / Claude screening

Checked on both the flagship domain and the English-edition subdomain,
independently re-verified during this build with a fresh `curl` fetch of
each:

- `https://kabar.kg/robots.txt` -> HTTP 200:
  ```
  User-agent: *
  Allow: /
  Disallow: /search/
  Disallow: /documents/
  Clean-param: utm_source&utm_medium&utm_campaign&utm_content&utm_term&fbclid&ysclid&from
  Sitemap: https://kabar.kg/sitemap.xml
  Sitemap: https://kabar.kg/news-sitemap.xml
  ```
- `https://en.kabar.kg/robots.txt` -> HTTP 200, identical shape:
  ```
  User-agent: *
  Allow: /
  Disallow: /search/
  Disallow: /documents/
  Clean-param: utm_source&utm_medium&utm_campaign&utm_content&utm_term&fbclid&ysclid&from
  Sitemap: https://en.kabar.kg/sitemap.xml
  Sitemap: https://en.kabar.kg/news-sitemap.xml
  ```

Both are a single `User-agent: *` group with a blanket `Allow: /` and
only 2 narrow functional-path disallows (`/search/`, `/documents/`). No
`Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`,
or `anthropic-ai` token anywhere, no blanket `Disallow: /`. No comments
at all in either file, so no natural-language AI/LLM-training
prohibition either (the Babak-17 screening layer). Conclusion:
crawlable, no machine-readable or natural-language AI scraping
prohibition found on either host.

## WAF

**None found.** `en.kabar.kg` is served directly by nginx (`Server:
nginx`, no `cf-ray` header, no Cloudflare/challenge markers on any
path). Confirmed both ways, on robots.txt, the homepage, the news
sitemap, and article pages, all returning identical 200 responses:
- plain `curl` (no TLS impersonation)
- `curl_cffi` `impersonate="chrome124"` (the same stack the actor ships
  with, verified via a throwaway `AsyncSession` recon script before
  writing `client.py`/`extractor.py`)

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (retry/warmup scaffolding kept per convention even though
nothing observed requires it).

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://en.kabar.kg/news/<slug>/`

The page emits exactly **one** `<script type="application/ld+json">`
block — a flat `NewsArticle` dict (not a `@graph`), e.g.:

```json
{
  "@context": "https://schema.org",
  "@type": "NewsArticle",
  "headline": "Kyrgyzstan unveils official medals for 6th World Nomad Games",
  "description": "Bishkek, August 26, 2026. /Kabar/. The State Agency for Physical Culture and Sports unveiled the official designs of the gold, silver, and bronze medals that will be awarded to the…",
  "image": ["https://en.kabar.kg/media/images/5f8a21.2e16d0ba.fill-1200x630.format-jpeg.jpegquality-65.jpg"],
  "datePublished": "2026-08-26T17:07:57+06:00",
  "dateModified": "2026-08-26T17:07:57+06:00",
  "author": {"@type": "Organization", "name": "Kabar"},
  "publisher": {"@type": "Organization", "name": "Kabar", "logo": {"@type": "ImageObject", "url": "https://en.kabar.kg/static/images/logo.png", "height": 60}},
  "mainEntityOfPage": {"@type": "WebPage", "@id": "https://en.kabar.kg/news/kyrgyzstan-unveils-official-medals-for-6th-world-nomad-games/"},
  "inLanguage": "en"
}
```

Quirks observed (consistent across 4 sampled articles):
- **No `articleBody` at all** in the ld+json — comes from HTML.
- `author` and `publisher` are always `{"@type": "Organization", "name":
  "Kabar"}` on every sample — wire-service content, agency-attributed
  rather than a named journalist byline (matches the `tass-scraper`/
  `rt-scraper` pattern of Organization-only author on state agencies).
- `image` is already a **list** of URL strings on every sample seen
  (unlike `qazinform.com`, which emits a single dict) — passed through
  raw as `image` (the ld+json's own key), no normalization needed.
- `datePublished`/`dateModified` use full ISO 8601 with a `+06:00`
  offset (Bishkek time) — kept as-is, raw passthrough.

Full text comes from `div.page-article-text-block > p` — Draft.js-style
rich-text export, plain `<p data-block-key="...">` tags with the
occasional `<img class="richtext-image ...">` as a **direct sibling**,
not nested inside a `<p>`, so `find_all("p")` skips embedded images
automatically without extra scoping.

**Known CMS quirk — a body can be truncated mid-word server-side.** One
of the 4 sampled articles
(`kazakhstan-approves-digital-qazaqstan-action-plan-through-2029`) has
an `articleBody` that ends abruptly mid-sentence: `"...allowing citizens
to exercise greater control over the use of their personal informa"` —
no closing punctuation, cut off inside the word "information". Verified
this is genuinely upstream, not a fetch/proxy artifact: re-fetched
twice, both times the response's `Content-Length` header and byte count
matched exactly (82,659 bytes), and the rest of the page after that
`<p>` (share buttons, related-articles sidebar, footer) is complete and
well-formed HTML — only the last paragraph's text itself is cut short.
The `<meta name="description">`/ld+json `description` field shows the
same style of raw, un-ellipsized truncation on *every* sampled article
(e.g. `"...the Kazakh government reports.The"`, run together with no
space) — that field is always a lede snippet, expected to be partial;
the body truncation is the actual quirk. Passed through as-is, not
treated as an extraction failure.

**Category and optional source-credit line.** The page carries two
`div.page-article-data` blocks sharing the identical class name:
1. The first, immediately after `<h1 class="page-article-title">`, holds
   the category link (e.g. `<a href="/cat/vik/">WNG-2026</a>`,
   `<a href="/cat/central-asia/">Central Asia</a>`, `<a
   href="/cat/society/">Society</a>`) plus a view counter — only the
   category link text is captured as `category`.
2. The second, immediately before `div.page-article-text-block`, holds
   an optional attributed-source line: a copyright-icon `<span>` (no
   text) followed by a plain-text `<span>` naming the source (e.g.
   `"Akorda"` — Kazakhstan's presidential administration, `"WNG media
   headquarters"`). **This second block is absent entirely** (no
   second `div.page-article-data` at all, confirmed via a raw `grep -c`
   count: 1 vs 2 occurrences) on agency-original stories with no
   external attributed source (e.g. the CKU railway tunnel story).
   Captured as `sourceCredit`, `null` when the block is missing.

### 2. Latest headlines — `S2-sitemap`

`GET https://en.kabar.kg/news-sitemap.xml`

A standard Google News sitemap (referenced from robots.txt). **No
working RSS/Atom feed exists** — `/feed` and `/feed/` both 301-redirect
to `/feed/`, which itself 404s. 50 `<url>` entries observed in one
fetch, each carrying `loc`, `news:publication` (`news:name: "Kabar"`,
`news:language: "en"`), `news:publication_date` (real per-article ISO
8601 timestamp with `+06:00` offset), and `news:title`. Confirmed
already newest-first in file order (top entry matched the freshest
homepage story at fetch time) — `extract_sitemap_items()` still sorts
descending by `news:publication_date` defensively, in case that
ordering isn't guaranteed on every fetch. Only `title`/`link`/`pubDate`
are carried — no full body, so `latest` mode returns headlines only
(unlike `kazinform-scraper`'s `/feed.xml`, which embeds full article
HTML).

## Paywall behavior

None observed. State news agency, fully open-access — no
"subscribe"/paywall markers found on any of the 4 sampled articles.

## Known limits

- 404s for non-existent article slugs are **real HTTP 404s** (confirmed
  on a deliberately-invented slug) — no soft-404 quirk observed.
- Article bodies can be genuinely truncated mid-word by the upstream
  CMS itself (see quirk above, observed on 1 of 4 samples) — passed
  through as-is, not flagged as `_error`.
- Only 4 articles sampled in depth (World Nomad Games sports news,
  Kazakhstan digital-policy news, a China-Kyrgyzstan-Uzbekistan
  railway/infrastructure story, plus one invented-slug 404 probe), all
  sharing the exact same template. A structurally different article
  type (opinion/interview, live-blog, photo gallery) was not sampled.
- `/news-sitemap.xml` returns a fixed 50 items with no observed
  pagination parameter; `limit` in `latest` mode is capped at 50 to
  match.
- `sourceCredit` is `None`/absent on agency-original stories — this is
  the normal, expected case, not a shape-drift signal.

## Diff cadence

Quarterly smoke test recommended.
