# Crawling Method — Kun.uz (English edition)

**Last verified:** 2026-08-26

Kun.uz is Uzbekistan's most-visited news portal. This is one of the
first Uzbekistan outlets added to this portfolio (alongside sibling
`gazetauz-scraper` and `uzdaily-scraper` built in the same wave).
Previously noted in market research as having **zero** competing Apify
actors.

## Domain / language scoping — one domain, four URL-prefix editions

Unlike Kazinform (separate domain per language), Kun.uz publishes 4
language tracks on **one domain** (`kun.uz`), split by URL path prefix:

- default path (no prefix) — Latin-script Uzbek
- `/kr/` — Cyrillic-script Uzbek
- `/ru/` — Russian
- `/en/` — English

This actor is scoped **entirely to the `/en/` prefix**. Confirmed via
the daily sitemap (`site-map-news_day_25_year_2026_month_8.xml`): of
120 URLs for one day, 15 were `/en/`, 17 `/ru/`, and 88 were the
unprefixed/`/kr/` Uzbek tracks — all four editions are populated
independently from the same underlying story pool, not auto-translated
mirrors of each other (article counts differ per language).

## robots.txt / Claude screening

```
User-agent: *
Allow: /

User-agent: Yandex
Allow: /
Clean-param: next&q&utm_source&utm_medium&utm_campaign&utm_term&utm_content

Sitemap: https://kun.uz/sitemap.xml
Host: kun.uz
```

Fetched fresh via `curl -s https://kun.uz/robots.txt` during this
build (178 bytes total, printed in full above — nothing truncated).
Two user-agent groups, **both** blanket `Allow: /`, **no `Disallow`
anywhere in the file at all**. No `Claude`, `ClaudeBot`, `Claude-Web`,
`Claude-User`, `Claude-SearchBot`, `anthropic-ai`, `GPTBot`, `CCBot`, or
any other AI-crawler token present in either group (checked every
`User-agent:` line individually, not just the last one in each group —
see the Babak-14 multi-user-agent parser-bug lesson). Zero comments in
the file, so there is no natural-language AI/LLM-training prohibition
either (a comment-based prohibition requires a comment to exist).
Fully open, cleanest possible case.

**Path quirk found during independent re-verification:**
`https://kun.uz/en/robots.txt` does **not** serve the robots.txt file —
it returns HTTP 200 with the Next.js SPA shell HTML (the app's
catch-all route), not `text/plain`. This is expected and harmless:
`robots.txt` is a site-wide, domain-root-only convention per the
robots exclusion standard — it is not supposed to exist per
language-prefix, and a crawler must always check the domain root
(`https://kun.uz/robots.txt`), never a path-prefixed variant. The root
fetch above is the authoritative one and applies to the entire domain
including every `/en/` URL used by this actor.

## WAF

`kun.uz` is Cloudflare-fronted (`server: cloudflare`, `CF-RAY` present
on every response, including `robots.txt`) but **no active challenge**
was encountered anywhere during recon. `curl_cffi` `chrome124` gets a
clean HTTP 200 on the homepage, article pages (both content templates),
the `/en/news/list` listing page, the sitemap index, and even
deliberately-invented-slug 404 pages — every single request, no
warmup-then-retry dance needed, no challenge/captcha body markers ever
observed.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. Retry/backoff scaffolding is kept anyway per convention.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://kun.uz/en/news/<yyyy>/<mm>/<dd>/<slug>`

The page emits 2 ld+json blocks: `NewsArticle` and `BreadcrumbList` —
the extractor scans all `<script type="application/ld+json">` tags and
picks the one whose `@type` is `NewsArticle`:

```json
{
  "@type": "NewsArticle",
  "headline": "Saida Mirziyoyeva meets Chinese Foreign Minister Wang Yi",
  "description": "Head of Uzbekistan's Presidential Administration ...",
  "image": ["https://storage.kun.uz/source/1/LR9Y7gjbrY6ne-q1Q4kI8klaYDgx3a5L.jpg"],
  "datePublished": "2026-08-26T20:18:00+05:00",
  "dateModified": "2026-08-26T20:18:00+05:00",
  "author": {"@type": "Person", "name": "Дониёр Тухсинов"},
  "publisher": {"@type": "Organization", "name": "Kun.uz", "logo": {...}}
}
```

Quirks observed (consistent across 5 sampled articles):
- **No `articleBody` at all** in the ld+json — comes from HTML.
- **`author.name` is consistently written in Cyrillic script** (Russian
  or Uzbek Cyrillic, e.g. `"Дониёр Тухсинов"`, `"Мирзабек Аҳмедов"`,
  `"Асал Равшанова"`) even though every other field on the same page
  (headline, description, body) is genuine English — the newsroom's
  bylines are simply never localized per edition. Kept as raw
  passthrough, not translated/transliterated.
- `image` is already a list (not a bare dict like Kazinform's
  `rt-scraper`-style single `ImageObject`) — normalized defensively
  regardless (handles dict/string/list shapes).
- No HTML-entity double-escaping observed on any sampled `headline`/
  `description` (no stray `&#039;`/`&amp;`) — `html.unescape()` still
  applied defensively per portfolio convention, no-op here.

Full text comes from `div.article-body > div.container > p` (the
extractor scopes to `div.article-body` and calls `find_all("p")`,
recursive). No ad/embed noise found interleaved with the paragraphs —
`<figure><img>` lead/inline images sit as siblings and are skipped
automatically since the selector targets `<p>` tags only.

**Second template found — `S1b-custom-page` fallback:** a minority of
articles (long-read/listicle features, e.g. travel guides) are built
with a **different, Tilda-style rich-page-builder template** and have
**no `div.article-body` at all**. Their content instead lives across
many small `div.ql-editor` blocks (32 observed on one sample, one per
page-builder "record" section — headings, image captions, and body
paragraphs interleaved). The extractor falls back to joining every
`div.ql-editor` block's text (in document order) when `div.article-body`
is absent, which reconstructs the full ~58,000-character body cleanly
on the one sample checked in depth. The ld+json `NewsArticle` block is
present and correctly shaped on this template too (headline/author/
dates all extracted normally) — only the body-extraction selector
differs. Tagged with `_source: "S1b-custom-page"` so downstream
consumers can distinguish the two templates if body-text fidelity ever
needs auditing.

### 2. Latest headlines — `S2-listing`

`GET https://kun.uz/en/news/list`

The site's dedicated SSR "Latest news" page — linked directly from the
homepage's `<aside><h2><a href="/en/news/list">Latest news</a></h2>`
sidebar widget. Server-renders a fixed list of the newest English
articles as bare `<li><a>...<h3>title</h3>...<span>HH:MM /
DD.MM.YYYY</span>...</a></li>` rows — confirmed **genuinely
newest-first** by cross-checking 3 sampled items' embedded timestamps
against each article's own ld+json `datePublished`
(20:18 → 18:51 → 09:29, strictly descending) and by fetching all 20
items and confirming the full list is strictly monotonically
descending by timestamp with zero out-of-order entries.

No `<img>`/thumbnail on this page (unlike the homepage's curated
sections, which do have images) — a real content difference, not an
extraction bug (confirmed by inspecting the raw markup directly: the
`<li>` wrapper contains only a heading and a timestamp span, no
`<img>`/`<figure>` element at all).

**Timestamp parsing:** each row carries a `"HH:MM / DD.MM.YYYY"` span
(site-local time, UTC+5 — matches the `+05:00` offset seen in every
article's ld+json `datePublished`/`dateModified`) parsed into a proper
ISO 8601 `publishedAt` (e.g. `"2026-08-26T20:18:00+05:00"`) — more
precise than the calendar-only date recoverable from the article's own
URL slug (kept alongside as `publishedDate` in case the timestamp span
is ever missing on a future markup change).

**No RSS/Atom feed found** — `/en/rss`, `/rss`, `/en/feed`, `/feed` all
return HTTP 404. The daily per-language sitemap files
(`site-map-news_day_<d>_year_<y>_month_<m>.xml`, referenced
transitively from the sitemap index) were also considered, but the
**current day's file was still empty** at the moment of recon (index
generation lag — the previous day's file was fully populated with 120
mixed-language URLs), making it unreliable for a real-time "latest"
feed; the SSR listing page updates live and was used instead.

**No working pagination** found on `/en/news/list` — `?page=2`, `?p=2`,
and `?offset=15` all returned byte-identical content to the base URL
(the true "load more" almost certainly calls an internal JSON API
triggered by client-side infinite scroll, not a plain query parameter,
and reverse-engineering it was not pursued for a fixed ~20-item cap).
`limit` in `latest` mode is capped at 20 to match the page's actual
server-rendered item count.

## Transient bad-edge-response quirk found during cloud smoke testing

One `apify call` cloud run (residential proxy, random exit IP) hit an
`UnexpectedShape` on an article that had extracted cleanly on every
local test moments before/after -- the response was a genuine HTTP 200
but carried neither `div.article-body` nor `div.ql-editor`. Immediately
re-running the exact same URL against 2 fresh random residential IPs
both succeeded cleanly. This matches the "genuinely flaky backend"
class already documented for `dailyft-scraper`/`jamaicagleaner-scraper`
(transient 503s/connection resets there) -- except here the flakiness
shows up as a wrong-shape 200 rather than a bad status code, so it
wouldn't have been caught by the client's existing status/marker-based
`is_blocked()` retry. `process_article()` in `main.py` now retries
`UnexpectedShape` once on a **fresh** proxy IP
(`UNEXPECTED_SHAPE_RETRIES = 2` total attempts) before letting it
propagate and fail the run loudly -- a single bad exit node no longer
crashes an entire batch run, while genuine site-wide schema drift (which
would reproduce on every IP) still fails loud as intended.

## Paywall behavior

None observed. Free, open-access news portal — no "subscribe"/paywall
markers found gating article body text on any of the 5 sampled
articles (both templates).

## Known limits

- 404s for non-existent article slugs are **real HTTP 404s** (confirmed
  on a deliberately-invented slug, canonical tag falls back to
  `https://kun.uz/en` but the status code itself stays 404 — no
  soft-404 quirk).
- `/en/news/list` server-renders a fixed ~20 items with no reachable
  pagination parameter; `limit` is capped at 20 to match.
- Only 5 articles sampled in depth (general/diplomatic news x3,
  historical/explainer x1, one long-read travel listicle on the
  alternate template). Other structurally different templates (video
  feature, live-blog, photo gallery) were not sampled.
- `S1b-custom-page` fallback was verified working on exactly one
  sample of that template; body-text completeness on other long-read
  articles built with the same page builder was not individually
  spot-checked beyond confirming the same selector pattern matches.

## Diff cadence

Quarterly smoke test recommended.
