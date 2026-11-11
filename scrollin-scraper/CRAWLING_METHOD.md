# Crawling Method — Scroll.in

**Last verified:** 2026-08-27

Scroll.in (`scroll.in`) is an independent, India-based digital-native news
and analysis outlet (donation/membership-funded, not a traditional
newspaper).

## Robots.txt

```
User-agent: *
Disallow: /article/print/
Disallow: /newsrepublic/
User-agent: proximic
Disallow:
Sitemap: https://scroll.in/sitemap/sitemap.xml
Sitemap: https://scroll.in/sitemap/news-sitemap.xml
```

Independently re-fetched with a fresh `curl_cffi` `chrome124` request during
this build (`GET https://scroll.in/robots.txt` -> HTTP 200, body as above).
Only two path-specific `Disallow` rules (a print-view path and a
`/newsrepublic/` path, neither used by this actor), no blanket
`Disallow: /`, and no Claude/ClaudeBot/Claude-Web/Claude-User/
Claude-SearchBot/anthropic-ai user-agent group anywhere. No plain-English
natural-language prohibition against AI/LLM training or scraping in the
comments either (there are no comments at all in this robots.txt).
Confirmed crawlable.

## WAF

`scroll.in` fronts through **Cloudflare** (`server: cloudflare` response
header) but no bot-fight-mode / managed-challenge behavior was observed
anywhere during recon:

- `curl_cffi` `chrome124` got clean HTTP 200s with full content on the
  homepage, all 4 article content-type prefixes (`/article/`, `/magazine/`,
  `/reel/`, `/latest/`), `/sitemap/news-sitemap.xml`, and the third-party
  Feedburner RSS mirror.
- Even a **plain `urllib.request` GET with no TLS impersonation at all**
  (stock Python UA string) got a clean HTTP 200 on the homepage — unlike
  `guardian.ng` in this portfolio, which challenges a bare UA baseline but
  passes under `curl_cffi`. No `cf-ray` challenge body, no
  `captcha-delivery.com`/`_dd_s`/`_abck`/Fastly markers were seen on any
  request.

**TLS profile pinned:** `chrome124` anyway, consistent with the
portfolio-wide default of avoiding the most-blocklisted `chrome131` profile
even when it currently works and even when no WAF is present at all.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://scroll.in/<article|magazine|reel|latest>/<numeric-id>/<slug>`

**Routing quirk:** the numeric ID alone determines which article is served
— the trailing slug is decorative only. `GET
.../article/1095282/totally-wrong-slug-here` returns HTTP 200 with the
*correct* article content for ID `1095282`, not a 404 or a redirect.
A genuinely nonexistent numeric ID (e.g. `99999999999`) returns a real HTTP
404 with a `404 - This page does not exist` title. Confirmed live on both
cases. Because of this, the "wrong-slug" negative test for this actor uses
a **nonexistent ID**, not a real-ID/wrong-slug combination (which would
incorrectly succeed).

Every article page (all 4 content-type prefixes sampled) emits exactly one
`application/ld+json` **bare-dict** `NewsArticle` block (no `@graph`
wrapper, unlike Guardian Nigeria) plus 3 more unrelated ld+json blocks
(`Organization`, `WebSite`, `BreadcrumbList`) that are skipped by the
`@type` filter. The `NewsArticle` node carries `headline`, `description`,
`image`, `keywords` (comma-separated string, not an array), `datePublished`,
`dateModified`, `author`, `publisher`, `mainEntityOfPage` — **but no
`articleBody` field at all**, confirmed absent on every one of the 4 sampled
articles across all 4 content types.

**`author` is always a single bare `Person` dict** (`{"@type": "Person",
"name": ..., "sameAs": "https://scroll.in/author/<id>"}`), never a list —
confirmed on 4 different articles including one syndicated piece (The
Conversation) and one unbylined wire item (`"name": "Scroll Staff"`).

**`dateModified` carries microsecond precision and an IST offset**
(e.g. `"2026-08-26T22:00:00.412764+05:30"`) — this looks like the CMS
stamping render time rather than a genuine editorial revision timestamp,
since it differs from `datePublished` only in the sub-second digits on
freshly-published articles. Passed through verbatim (raw-passthrough
convention) rather than "corrected."

Full body text comes from HTML: `<div id="article-contents"
class="article-body">`, **direct-child `<p>` tags only**
(`find_all("p", recursive=False)`). Confirmed this is necessary, not just
defensive: embedded widgets (pull-quotes, YouTube embeds via
`<figure class="cms-block cms-block-embed cms-block-embed-youtube">`,
tracker pixels via `<div class="cms-block cms-block-tracker">`) sit as
direct-child siblings of the `<p>` tags inside the same container on every
sampled article, and social-embed blockquotes are known to carry their own
nested `<p>` tags that a `recursive=True` walk would incorrectly fold into
the article text.

No HTML entity double-escaping quirk observed on any of the 4 samples
(en-dash `–` and other punctuation decode correctly as real Unicode
characters, not `&amp;`-style escaped entities). `html.unescape()` is still
applied defensively to every text value, matching portfolio convention.

### 2. Latest headlines — `S2-sitemap`

`GET https://scroll.in/sitemap/news-sitemap.xml`

A Google News sitemap (referenced from `robots.txt`), used instead of:

- **`https://scroll.in/feed`** — despite the name, this path does **not**
  return RSS/Atom. It 200s with the ordinary homepage HTML shell instead
  (a dead end, confirmed live).
- **`https://feeds.feedburner.com/ScrollinArticles.rss`** — a real,
  working RSS 2.0 feed (confirmed live, referenced via `<link
  rel="alternate" type="application/rss+xml">` on every page) with full
  `content:encoded` HTML bodies. Not used as the primary `latest` source
  to keep the actor entirely on-domain (`scroll.in`) rather than depending
  on a third-party Google-owned mirror, matching the guardian-nigeria-
  scraper precedent of preferring an on-domain sitemap.

The sitemap carries `loc`, and a `news:news` block with `news:publication`
(`news:name`, `news:language`), `news:publication_date` (real per-article
IST timestamp), `news:title`, and `news:keywords`, plus a sibling
`image:image`/`image:loc`. 100+ `<url>` entries observed in one fetch,
already newest-first in file order (confirmed: top entry matched the
freshest homepage headline at fetch time) — `extract_sitemap_items()`
still sorts descending by `publication_date` defensively.

## Paywall behavior

**No hard paywall observed.** Checked across all 4 content types
(`article`, `magazine`, `reel`, `latest`) — every sampled article's HTML
`#article-contents` body was complete, full-length prose with a natural
ending (byline/attribution line at the close), no "subscribe to continue,"
no truncated final paragraph, no `isAccessibleForFree: false` marker in the
JSON-LD (the field doesn't appear at all).

Scroll.in's site nav does carry a `/tag/Member-Exclusive` link labeled
"Members-Only" in both desktop and mobile menus. Fetching that tag page
returned the site's normal recent-articles listing, not a distinct set of
gated content, and none of the string probes for gating language
(`Scroll+`, `member-only`, `members only` as body copy, `Support Scroll`,
`exclusive to`, `sign up to read`, `subscribe to continue`) matched inside
any sampled article body — only the one incidental nav-menu hit per page.
Guessed membership/subscribe URLs (`/membership`, `/support-us`,
`/subscribe`) all 404. Verdict: Scroll.in is donation/membership-funded but
does not appear to gate article *content* behind that membership — all
sampled content, including the nominally "Member-Exclusive"-tagged nav
section, is fully open access at the time of this build.

## Known limits

- 404s for deleted/never-existed article IDs are real HTTP 404s (confirmed
  on a deliberately-invented numeric ID) — no soft-404 quirk observed. But
  see the routing quirk above: a *wrong slug on a real ID* is NOT a 404.
- Only 4 articles sampled in depth (one per content-type prefix:
  `article`, `magazine`, `reel`, `latest`), plus the sitemap and one
  invented-ID 404 probe. A structurally different template (e.g. a
  live-blog, podcast, or photo-essay page) was not sampled.
- `latest` mode is capped at the sitemap's own window (100+ most recent
  items observed in one fetch); very old articles are not reachable via
  `latest` mode past that window.
- The Feedburner RSS mirror (`feeds.feedburner.com/ScrollinArticles.rss`)
  is a viable alternate `latest` source carrying full HTML bodies in
  `content:encoded`, but is not wired up as a fallback to keep the actor
  on-domain; note it here in case scroll.in's own sitemap ever breaks.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block and the
`#article-contents.article-body` HTML container are both still present. If
Scroll.in redesigns the page, `extract_article` will raise
`UnexpectedShape` and the run will fail loudly rather than emit corrupt
records.
