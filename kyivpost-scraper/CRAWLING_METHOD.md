# Crawling Method — Kyiv Post

**Last verified:** 2026-08-25

## WAF

`kyivpost.com` shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on the homepage (~178 KB), article pages, `sitemap.xml`,
`news-sitemap.xml`, and `/feed` -- no challenge body, no 403.

`robots.txt` disallows `/login`, `/stats-by-authors/`, and a set of
tracking-parameter query strings (`?s=`, `?topic=`, `?category=`,
`?fbclid=`, etc.) -- none of which affect `/post/<id>` article URLs or the
sitemap/feed endpoints this actor uses. No Claude/GPTBot/anthropic-ai
disallow of any kind. `robots.txt` also advertises
`Sitemap: https://www.kyivpost.com/sitemap.xml`.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://www.kyivpost.com/post/<id>` (also seen under `/opinion/<id>`
-- both share the same template)

The page emits 3 ld+json blocks: `NewsMediaOrganization`,
`BreadcrumbList`, and `NewsArticle` -- the extractor scans all
`<script type="application/ld+json">` tags and picks the one whose
`@type` is `NewsArticle`. That block carries `headline`, `image`,
`datePublished`, `dateModified`, `author` (a **list of `Person` objects**
-- individual bylines, e.g. `"Lesia Dubenko"`, not agency-attributed like
a wire service), `publisher` (`NewsMediaOrganization`, name `"Kyiv
Post"`), `isAccessibleForFree` (`true` on every sample), and
`inLanguage` -- but **no `articleBody`** and **no `description`**.

Full text comes from HTML: `div#post-content > section.entry`. A single
article's body can be split across **multiple sibling `section.entry`
blocks** -- confirmed on a short news brief where a
`section.entry.telegram` widget-embed block (just a `<script>` tag, no
text) sits between two `section.entry.text` blocks holding the real
paragraphs. Only *direct-child* `<p>`/`<h2>`/`<h3>` tags of each section
are collected -- this automatically excludes promo inserts that are
nested *inside* their own wrapper `<div>` (a "JOIN US ON TELEGRAM"
call-to-action `div.inarticle_link_block`, "Other Topics of Interest"
related-post blocks `div#insert-post-by-topic`, and ad placeholders
`div.section-wrapper.ad_between_paragraphs`) without needing a denylist
of CSS classes. Verified clean (no promo/ad text leaking into
`articleBody`) on 5 samples: a long-form opinion piece (56 paragraphs), a
3-paragraph news brief with an embedded Telegram widget, a mid-length
"35 years of independence" feature (56 paragraphs, single section), and
a 2023-dated archive article (`/post/1`, 8 paragraphs) -- confirming the
template is stable across article age and article type (news / opinion).

`description` is pulled from `<meta name="description">` (also mirrors
`og:description`) -- present and populated on every sampled article, even
though it's absent from the `NewsArticle` ld+json block.

`category` is pulled from the `BreadcrumbList` block's second
`itemListElement` entry (position 2, e.g. `"World"`, `"Ukraine"`) --
treated as optional (not raised on if the breadcrumb is missing) since
it's a nice-to-have, not load-bearing for the record to be useful.

### 2. Latest headlines — `S2-rss`

`GET https://www.kyivpost.com/feed`

A WordPress-style RSS 2.0 feed (confirmed `content-type: application/xml`,
**not** advertised via a `<link rel="alternate">` tag on the homepage --
found by probing common feed paths). Returns exactly **100 items**, no
pagination parameter found. Fields: `title`, `link`,
`description` (short teaser, not full article text), `category`
(repeatable), `topic` (repeatable, custom tag not in RSS 2.0 spec but
present and useful), `author` / `dc:creator` (both present, same value),
`guid` (internal numeric post ID, matches the `/post/<id>` URL),
`pubDate`, and `enclosure` (lead image URL).

The Google News sitemap (`sitemap.xml` -> `news-sitemap.xml` -> a
2-item index -> `news-sitemap_en.xml`) was also confirmed working
(34 KB, `news:title`/`news:publication_date` per entry) and would be a
viable fallback, but `/feed` was chosen as the primary `latest`-mode
source because it carries richer fields (description, category, author,
image) in one request, matching the RSS-first convention used across the
rest of this portfolio.

## Paywall behavior

None observed. `isAccessibleForFree: true` on every sampled `NewsArticle`
block; no "subscribe"/"paywall"/"premium"/"member-only" markers found in
raw HTML on any sampled page.

## Known limits

- `description` in `latest` mode is a teaser, not the full article body
  -- use `article` mode against the `link` for full text.
- 404s are real HTTP 404s (verified with a synthetic out-of-range
  `/post/99999999`, 50 KB generic error page) -- no soft-404 behavior
  observed. Very low, old numeric IDs (e.g. `/post/1`) still resolve to
  real archived articles, so don't assume low IDs are invalid.
- `author` in article mode is a comma-joined string when ld+json lists
  multiple `Person` entries -- only single-author bylines were observed
  in the samples, but the field is built to handle more than one.
- Only 5 articles sampled in depth (2 opinion, 3 news/post, spanning a
  2023 archive article to same-day 2026 stories). All shared the exact
  same `div#post-content > section.entry` markup pattern. A structurally
  different template (e.g. a live-blog, video feature, or photo-gallery
  page) was not sampled.

## Diff cadence

Quarterly smoke test recommended.
