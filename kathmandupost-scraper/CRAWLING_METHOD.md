# Crawling Method — The Kathmandu Post

**Last verified:** 2026-08-26

## WAF

`kathmandupost.com` sits behind **Cloudflare** (`server: cloudflare`,
`cf-ray` header present on every response) but shows **no active
challenge**. `curl_cffi` `chrome124` gets a clean 200 on the homepage
(~118 KB), article pages (~60-64 KB), and `/rss` -- no `cf-mitigated`
header, no "Just a moment" interstitial, no 403.

`robots.txt` is a single group: `User-agent: * / Disallow:` (24 bytes
total, nothing disallowed at all -- wide open). No other `User-agent:`
groups exist, so the multi-group parser-merge bug flagged for this
outlet in the market-research backlog doesn't even apply here: there is
only one group, and it blocks nothing. No Claude/ClaudeBot/Claude-Web/
Claude-User/Claude-SearchBot/anthropic-ai disallow of any kind (checked
case-insensitively). No `Sitemap:` line is advertised.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html`

`GET https://kathmandupost.com/<section>/<yyyy>/<mm>/<dd>/<slug>`

The page emits only **2** `<script type="application/ld+json">` blocks:
an `Organization` block and the `NewsArticle` itself. The `NewsArticle`
block is unusually thin compared to most portfolio targets -- it only
carries `headline`, `image` (an `ImageObject` with `url`/`height`/
`width`), `publisher` (`Organization`, name `"The Kathmandu Post"`),
`description`, and a `mainEntityOfPage` whose `@id` is hard-coded to the
literal string `"https://google.com/article"` on every single sampled
article (an obvious upstream CMS placeholder bug, not a real per-article
value) -- deliberately **not** surfaced in the output since it carries
zero information. There is **no `articleBody`, no `datePublished`/
`dateModified`, and no `author`** in ld+json at all.

**lxml HTML-parser gotcha (important):** `BeautifulSoup(html, "lxml")`
silently drops 2 of the 26 `<script>` tags on every sampled article page
-- and one of the two it drops is consistently the
`application/ld+json` `NewsArticle` block (the sibling `Organization`
block survives, which made the bug easy to miss at first: `find_all` on
`lxml` still returns *a* ld+json block, just the wrong one, so
`@type == "NewsArticle"` silently comes back `None` instead of raising
immediately -- the missing `articleBody` container caught it downstream
instead). Confirmed root cause: raw `html.count("<script")` == 26,
`BeautifulSoup(html, "lxml").find_all("script")` == 24, `BeautifulSoup(
html, "html.parser")` (stdlib) == 26 -- all present. **This extractor
uses `"html.parser"` instead of `"lxml"` for article-page parsing** as a
result (the `/rss` feed still uses `BeautifulSoup(xml, "xml")`, which is
a different lxml code path and unaffected).

Full text, byline, and dates all come from HTML instead:

- **Body:** `section.story-section` -- direct-child `<p>` tags only.
  Verified clean (all direct children are plain `<p>` tags, no ads,
  related-post blocks, or embeds mixed in) on 7 sampled articles spanning
  `national`, `world`, `money`, `sports`, `opinion`, `editorial`,
  `columns`, and `visual-stories` sections. The one `visual-stories`
  sample (a photo-gallery-style piece) had only a single `<p>` -- short
  body length, not a broken selector.
- **Byline:** `<a href="/author/<slug>">Name</a>` -- collected via
  `a[href^="/author/"]` and de-duplicated (the same link appears once
  near the top of the page in `<h5 class="text-capitalize">` and again in
  the bottom `div.author-info` bio block). **Absent entirely on
  editorial/unsigned pieces** (confirmed on an `/editorial/` sample) --
  treated as optional (`author: null`), not raised on.
- **Dates:** `div.updated-time` blocks with plain-text
  `"Published at : <date>"` / `"Updated at : <date>"` (e.g. `"Published
  at : August 25, 2026"` / `"Updated at : August 25, 2026 20:48"`) --
  passed through as raw upstream strings since there is no
  machine-parseable ISO date anywhere on the page. A third
  `div.updated-time.updated-time_location` carries just a dateline city
  (e.g. `"Kathmandu"`).
- **Category:** not carried by ld+json (no `BreadcrumbList` block exists
  on this site at all) -- taken from the first path segment of the
  article URL itself (e.g. `/national/2026/08/25/...` -> `"national"`),
  which is stable and always present since it's baked into the URL
  scheme.

### Soft-404 (no real 404 status observed)

A nonexistent article slug (`/national/2026/08/25/this-is-a-totally-
bogus-fake-article-slug-xyz123`) returns **HTTP 200** rendering the
homepage shell: generic `<title>The Kathmandu Post | Read online latest
news and articles from Nepal</title>`, only the `Organization` ld+json
block (no `NewsArticle`), and no `section.story-section` at all.
Detected by requiring **both** signals of a real article (`NewsArticle`
block AND `section.story-section`) to be absent, **and** the `<title>`
text to exactly match the generic homepage title -- a conservative
AND-of-three check chosen so a genuine future schema change (e.g. the
site renaming `section.story-section`) fails loud as `UnexpectedShape`
instead of silently misclassifying as `not_found`.

### 2. Latest headlines — `S2-rss`

`GET https://kathmandupost.com/rss`

**Only `/rss` is real.** `/feed`, `/rss.xml`, `/sitemap.xml`,
`/news-sitemap.xml`, `/sitemap_news.xml`, and `/sitemap-news.xml` were
all probed and every one of them soft-404s to the homepage HTML shell
(`content-type: text/html`, ~44.6 KB, not XML) -- `/rss` alone returns
`content-type: text/html; charset=UTF-8` (mislabeled, but the body is
genuine `<?xml version="1.0" ...?><rss version="2.0">...` content) with
~40 `<item>` entries, newest first, spanning roughly the last 2 days at
sample time. Each item carries only `title`, `link`, and `description`
(short teaser) -- no `pubDate`, `guid`, `category`, `author`, or
`enclosure`. A Cloudflare Insights `<script type="module">` beacon tag
is appended after the closing `</rss>` root element (technically invalid
XML), but `BeautifulSoup(xml, "xml")` tolerates the trailing garbage and
still parses every `<item>` correctly (confirmed 40/40 on a sampled
feed).

## Paywall behavior

None observed. No "paywall"/"premium"/"subscriber-only"/"member-only"/
"sign up to continue" markers found in raw HTML on any of the 7 sampled
article pages, and no `isAccessibleForFree`-style flag exists anywhere
in ld+json to even signal one. A `class="subscribe--wrapperx"` wrapper
div surrounds `section.story-section` on every page, but it wraps fully
visible, untruncated article text on every sample -- read as an inert
leftover CSS hook (perhaps for a subscribe-CTA feature that isn't
currently active), not an active paywall.

## Known limits

- `description` in `latest` mode is a teaser, not the full article body
  -- use `article` mode against the `link` for full text.
- No real HTTP 404 was observed for a bad article path -- every
  synthetic bad slug tried returned the soft-404 homepage shell (HTTP
  200). If the upstream ever starts returning real 404s for some URLs,
  `process_article` already handles that branch too (`_error:
  "not_found"`).
- `author` is built as a de-duplicated, comma-joined list to handle
  multiple bylines, but only single-author (or fully unsigned) bylines
  were observed in the 7 samples -- multi-author co-bylines were not
  directly confirmed.
- `publishedAt`/`updatedAt` are raw upstream display strings (e.g.
  `"August 25, 2026"`, `"August 25, 2026 20:48"`), not normalized ISO
  8601 -- there is no cleaner machine-readable date available anywhere
  on the page to normalize from.
- 7 articles sampled in depth across 8 different sections (`national`,
  `world`, `money`, `sports`/`cricket`, `opinion`, `editorial`,
  `columns`, `visual-stories`). All shared the exact same
  `section.story-section` / `div.updated-time` / `a[href^="/author/"]`
  markup pattern. A structurally different template (e.g. a live-blog,
  video feature, or interactive/data-viz page) was not sampled.

## Diff cadence

Quarterly smoke test recommended.
