# Crawling Method — Daily Post Nigeria

**Last verified:** 2026-08-26

Daily Post Nigeria (`dailypost.ng`) is a major Nigerian online newspaper.

## Robots.txt

Independently re-fetched during this build (`GET https://dailypost.ng/robots.txt` -> HTTP 200):

```
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

User-agent: bingbot
Disallow: /search/

Sitemap: https://dailypost.ng/sitemap_index.xml

#WP Import Export Rule
User-agent: *
Disallow: /wp-content/uploads/wp-import-export-lite/
```

No `Claude`/`ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/
`anthropic-ai` disallow anywhere, and no blanket `Disallow: /`. The only
comment in the file is a WordPress plugin label (`#WP Import Export Rule`)
-- **no plain-English prohibition against AI/LLM training or scraping** of
any kind. Confirmed crawlable, both machine-readable directives and
natural-language comments checked.

## WAF

`dailypost.ng` sits behind Cloudflare (`server: cloudflare`,
`cf-apo-via: tcache` -- Cloudflare's "Automatic Platform Optimization for
WordPress" cache layer) but shows **no active JA3/TLS-fingerprint
challenge**: a plain `requests` baseline with no TLS impersonation at all
gets a clean HTTP 200 on the homepage. `curl_cffi` `chrome124` is used
anyway, for consistency with the rest of this portfolio and resilience
against a future fingerprint-gate rollout -- not because it was required
to get past a block.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://dailypost.ng/<year>/<month>/<day>/<slug>/`

The page emits **one** `<script type="application/ld+json">` block. Daily
Post Nigeria runs Yoast SEO Premium v28.1 (confirmed via an HTML comment:
"This site is optimized with the Yoast SEO Premium plugin v28.1"), but
**unlike Guardian Nigeria and Punch** (also Yoast-powered, also in this
portfolio), the ld+json is **not** a `@graph` array of cross-referenced
nodes with `@id` refs to resolve. It's a flat JSON array with a single
item:

```json
[{"@context": "https://schema.org/", "@type": "NewsArticle", ...}]
```

**Crucially, this node carries a complete, untruncated `articleBody`
directly** — confirmed length-equivalent (within a few characters, from
whitespace normalization) against an independent HTML paragraph walk of
`#mvp-content-main` on 3 sampled articles (News, Sport, and a
Sponsored/Promoted piece). Guardian Nigeria's and Punch's `NewsArticle`
nodes both **omit** `articleBody` entirely and require falling back to an
HTML paragraph walk for body text — that fallback is **not needed here**;
JSON-LD alone is the sole strategy for article mode.

Fields observed on the `NewsArticle` node: `headline`, `name` (duplicate
of headline, dropped), `description`, `articleSection` (a **plain
string** on this site, e.g. `"News"`, `"Sport"`, `"Sponsored"` — not a
list like Guardian Nigeria's), `articleBody`, `keywords` (a list,
sometimes with blank/whitespace-padded entries, e.g.
`["nasarawa", " sule", " "]` — passed through raw, not cleaned),
`datePublished`, `dateModified`, `thumbnailUrl`, `wordCount` (emitted by
upstream as a **numeric string**, e.g. `"368"`, not a JSON number — passed
through as-is, not cast),
`timeRequired` (an ISO 8601 duration estimate, e.g. `"PT28S"`),
`mainEntity` (a self-referencing `WebPage` stub, dropped as low value),
`author` (a single **inline** `Person` object — not a list like Guardian
Nigeria, not a bare `{"@id": ...}` reference like Premium Times), `editor`
(same shape as `author`, often literally the same person on this site but
kept as a separate field since upstream keeps it separate), `publisher`
(an inline `Organization` object with `name` and a `logo` `ImageObject` —
no `@id` resolution needed, unlike Guardian Nigeria's bare-ref
`publisher`), and `image` (a list of `ImageObject` entries, passed
through raw).

HTML entities (`&nbsp;` etc.) appear in `description` and `articleBody`
text — `html.unescape()` applied to every text field pulled from the
ld+json for robustness.

**A red herring, resolved:** during recon, an apostrophe in
`Balami's`/`Sa'ad` rendered as a box/replacement glyph (`�`) in this
session's terminal, which initially looked like a mojibake/encoding bug.
Codepoint inspection (`ord()` on the actual character) confirmed the
underlying character is genuinely `U+2019` (RIGHT SINGLE QUOTATION MARK)
— correct, valid Unicode. The `�` was purely this terminal's inability to
render that glyph, not a data quality issue. No special decoding
workaround was implemented; standard UTF-8 decoding is sufficient.

A 200-OK page that isn't an article at all (e.g. `/privacy-policy/`)
carries **zero** `application/ld+json` blocks whatsoever — simpler to
detect than Guardian Nigeria/Punch, which still emit a
`WebPage`/`CollectionPage`-style graph (just without a `NewsArticle`
node) on non-article pages. Detected here as: no ld+json block found, OR
no item typed `NewsArticle`/`Article` found across all blocks — both
raise `ArticleNotFound`, reported as `_error: "not_article"`.

### 2. Latest headlines — `S2-rss`

`GET https://dailypost.ng/feed/`

The WordPress core RSS feed. Confirmed clean 200 with `curl_cffi`
`chrome124`. Each `<item>` carries `title`, `link`, `dc:creator` (a
**real per-article byline**, e.g. `"Nana Ismail"`, `"Don Silas"` — unlike
`punchng.com/feed`, which has a constant generic `"Punch Newspapers"`
creator on every item), `pubDate`, **real per-article `<category>`
tags** (a mix of section and freeform tags, e.g.
`["News", "nasarawa", "sule"]` — unlike Punch, whose category tag is
always empty), a `guid`, and a teaser `description` (CDATA HTML: a
featured-image `<img>` tag plus a `<p>` of body text truncated with a
WordPress `[&#8230;]` ellipsis marker, plus a trailing "Read More"-style
link paragraph — real feed content, kept as-is, `html.unescape()`d).
`content:encoded` is also present (a longer/full-body CDATA block) but
not used — `article` mode against `link` is the reliable path to full
`articleBody`. **No `<enclosure>` tag is present on any of the 20 sampled
feed items** (unlike Punch, which always has one pointing at a generic
masthead logo) — no `enclosureUrl` field is emitted, rather than
fabricating an always-null one.

No dedicated Yoast News SEO sitemap was found (only a plain, heavily
paginated `post-sitemap*.xml` series going back to 2012, unsuitable for
"latest") — the RSS feed is the best latest-mode source and was never
observed blocked.

## Paywall behavior

None observed. Daily Post Nigeria is a free, open-access site — no
"subscribe to continue reading" marker, no truncated `articleBody`, on
any of the 3 sampled articles across News, Sport, and a Sponsored piece.

## Known limits

- 404s for deleted/never-existed article slugs are **real HTTP 404s**
  (confirmed on a deliberately-invented slug) — no soft-404 quirk
  observed.
- A 200-OK page that isn't an article at all (e.g. `/privacy-policy/`)
  carries zero ld+json blocks — detected explicitly and reported as
  `_error: "not_article"`.
- Only 3 articles sampled in depth (News, Sport, and a
  Sponsored/Promoted piece), plus one non-article page and one
  invented-slug 404 probe. A structurally different template (e.g. a
  live-blog, video feature, opinion/cartoon, or photo-gallery page) was
  not sampled.
- `articleSection` is a plain string on every sample seen; if a future
  article ever carries multiple sections as a list, the field is passed
  through raw either way (no type constraint in the output schema).

## Diff cadence

Quarterly smoke test recommended.
