# Crawling Method — Business Today

**Last verified:** 2026-08-27

Business Today (`businesstoday.in`) is a major Indian business/finance
magazine and portal, part of Living Media / India Today Group — the same
publisher family as `indiatoday-scraper`.

## Robots.txt

Independently re-verified (per project policy — both the machine-readable
directives AND a plain-English scan for AI/LLM-training prohibitions were
checked, not just relying on the orchestrator's fast screen).
`https://www.businesstoday.in/robots.txt` returns HTTP 200, 31 lines,
plain-text.

Only two `User-agent` blocks exist: `*` (`Allow: /` plus a short list of
specific `Disallow:` paths — `/topic/*`, `/prnewswire/*`, `/sitetakeoverad`,
`/visualstories/preview.php?*`, `/shopping/*`, `/custom-search`, `/ajax/*`,
`/shorts/*`, `/pti-feed/*`, and several wire-service author archive pages
(`/author/pti/`, `/author/ani/`, `/author/reuters/`, etc.) — none of which
overlap with the `/<vertical>/story/<slug>` article URLs or the RSS/sitemap
endpoints this actor uses) and `Googlebot-News` (a separate, unrelated set of
disallows: `/impact-feature/*`, `/visualstories/preview.php?*`,
`/sitetakeoverad`).

No `Claude`/`ClaudeBot`/`Claude-Web`/`Claude-SearchBot`/`anthropic-ai`/
`GPTBot`/`CCBot`/`Google-Extended` user-agent block anywhere in the file, and
no blanket `Disallow: /` under `User-agent: *`. A full-text case-insensitive
grep for `claude|gptbot|ccbot|anthropic|ai-|artificial|train|llm|permission|
prohibit|consent` against the raw file returned zero matches — no
plain-English natural-language prohibition against AI/LLM scraping or
training exists anywhere in the file (comments or otherwise). **Clear to
build.**

## WAF

**None detected.** `curl_cffi` `chrome124` (no warmup-then-retry dance
needed) returned clean HTTP 200 on the first try for the homepage, multiple
article pages across different verticals (`india`, `latest/economy`,
`technology/news`), `robots.txt`, the RSS feed, and the news sitemap.

The homepage `server` response header is `itgdweb` — the same value observed
on `indiatoday-scraper`, confirming Business Today shares the "India Today
Group Digital" (ITGD) CMS/CDN infrastructure with its sibling site, as
expected from both being part of Living Media / India Today Group. No
Akamai/Cloudflare challenge body, captcha, or JS-challenge marker was
observed on any request during recon.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default and with `indiatoday-scraper`, even though nothing in front of this
site currently requires impersonation — cheap insurance against Bot Manager
being turned on more strictly later.

## Data sources

### 1. Article pages — `S1-jsonld` (primary)

`GET https://www.businesstoday.in/<vertical>/[<subvertical>/]story/<slug>-<id>-<date>`

Every article page sampled (India, Economy/Latest, Technology verticals)
emits a single `application/ld+json` `NewsArticle` block among 8 total
ld+json script tags on the page (also seen: `ImageObject`, `ProfilePage`,
`WebPage`, `BreadcrumbList`, `SiteNavigationElement`, `WebSite`,
`Organization`).

The `NewsArticle` node carries `mainEntityOfPage`, `inLanguage`, `headline`,
`articleSection`, `url`, `description`, `keywords` (comma-separated string),
`datePublished`/`dateModified` (with `+05:30` IST offsets), full plain-text
`articleBody` (2,400–3,000+ characters across samples), `publisher`
(Organization object with logo), `author` (a single `Person` object — a desk
credit like "Business Today Desk", not a named reporter, same pattern as
`indiatoday-scraper`), `associatedMedia`, and `image`.

No `__NEXT_DATA__` was found — same as `indiatoday-scraper`, the ITGD CMS
server-templates ld+json blocks directly into the HTML rather than using
Next.js SSR data injection.

**Unlike `indiatoday-scraper`, strict `json.loads()` parses the NewsArticle
block cleanly on every sample checked** — no unescaped control-character
issue was observed here. `json.loads(raw, strict=False)` is still used
defensively (same helper reused across the ITGD-family actors) since it's a
no-op when the bytes are already valid strict JSON, but it was not required
to trigger successfully in this recon.

**Quirk — double-HTML-escaped entities in text fields:** `headline` and
`articleBody` contain literal `&amp;#039;` sequences in place of a plain
apostrophe (e.g. `"...caused Nepal&amp;#039;s deadly flood"`), i.e. the
upstream CMS has escaped an already-escaped `&#039;` entity a second time.
Confirmed via `html.unescape()` applied twice reconstructs the intended
apostrophe, but per this portfolio's raw-passthrough convention (rule #5 —
minimal renaming, mirrored from `indiatoday-scraper` which also does no
unescaping on its JSON-LD spread) the value is passed through completely
unmodified, entities and all. Downstream consumers that want clean text
should apply `html.unescape()` twice on `headline`/`articleBody`/`keywords`.

## Paywall behavior

No `isAccessibleForFree`/`hasPart` paywall-signal fields were observed on any
sampled article, and no truncated `articleBody` was seen. No "subscribe",
"premium", "BT-Prime", or similar gating markers were found anywhere in the
homepage or sampled article HTML. Business Today's main news content does
not appear to carry a functional paywall.

### 2. Latest headlines — `S2-rss`

`GET https://www.businesstoday.in/rss/latest.xml`

Standard RSS 2.0 (`<channel>/<item>`), titled "Business News India: Latest
Business News Today, Share Market, Economy". Confirmed live 2026-08-27: 114
items, mixing multiple verticals (Economy, Markets, India, Technology,
Magazine/Cover Story...), freshest `pubDate` within minutes of the request —
a genuine site-wide feed, same tier as `indiatoday-scraper`'s `/rss/home`.

Fields used: `title`, `link`, `pubDate`, `description`, `guid`. Unlike
`indiatoday-scraper`'s feed (no `<guid>` element at all), this feed DOES
carry a `<guid>` per item — identical to `link` on every sample checked (not
a separate stable ID).

**Quirk — `link`/`guid` carry a tracking query param:** every item's
`<link>`/`<guid>` has `?utm_source=rssfeed` appended (note: `rssfeed`, not
`rss` as on `indiatoday-scraper`). Confirmed the underlying article loads
identically with or without the param — passed through as-is.

**Quirk — some items have genuinely empty `pubDate`/`description`:**
magazine/cover-story items (`/magazine/cover-story/story/...`) were observed
with an empty `<pubDate></pubDate>` and empty `<description><![CDATA[]]>
</description>` in the raw upstream XML — not a parsing bug on this actor's
side (confirmed by inspecting the raw feed bytes directly). These come
through as empty strings (`""`), distinct from a genuinely absent tag (which
would come through as `null`).

## Known limits

- `latest` mode returns the single site-wide feed only — no per-section
  filter is exposed as an input.
- `keywords` is a comma-separated string, not an array.
- `headline`/`articleBody`/`keywords` may contain double-HTML-escaped
  entities (see Quirk above) — not unescaped by this actor.
- Only 3 articles sampled in depth (India, Economy/Latest, Technology
  verticals) plus one deliberately-invented-slug 404 probe. A structurally
  different template (e.g. a magazine/cover-story page, video, live-blog, or
  photo-gallery page) was not sampled for `extract_article` — if the ld+json
  shape differs there, `UnexpectedShape` will raise and fail the run loudly
  rather than emit a corrupt record.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and `latest` mode, and confirm the `NewsArticle` ld+json block is
still found. If Business Today redesigns the page, `extract_article` will
raise `UnexpectedShape` and the run will fail loudly rather than emit corrupt
records.
