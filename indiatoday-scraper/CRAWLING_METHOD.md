# Crawling Method — India Today

**Last verified:** 2026-08-26

## Robots.txt

Independently re-verified (per project policy, following the "Babak 17" false-clear
incident at The Star Malaysia -- both the machine-readable directives AND a
plain-English scan for AI/LLM-training prohibitions were checked).
`https://www.indiatoday.in/robots.txt` returns 200, 125 lines, plain-text.

Only three `User-agent` blocks exist in the whole file: `*` (`Allow: /` plus a
long list of specific `Disallow:` paths -- admin/search/live-score/ajax/API
endpoints, none of which overlap with article, video, or RSS URLs used by
this actor), `Googlebot-News` (a separate, unrelated set of ajax/live-score
disallows), and `Mediapartners-Google` (`Allow: /`).

No `Claude`/`ClaudeBot`/`Claude-Web`/`Claude-SearchBot`/`anthropic-ai`/
`GPTBot`/`CCBot`/`Google-Extended` user-agent block anywhere in the file, and
no blanket `Disallow: /` under `User-agent: *`. A full-text case-insensitive
grep for `claude|gptbot|ccbot|anthropic|ai-|artificial|train|llm|permission|
prohibit|consent` against the raw file returned zero matches -- no
plain-English natural-language prohibition against AI/LLM scraping or
training exists anywhere in the file (comments or otherwise). **Clear to
build.**

## WAF

**None detected gating normal traffic.** A bare, un-impersonated `curl`
(default UA, no TLS impersonation at all) returned 200 with full page
content on the homepage, article pages across every vertical tested
(business/india/technology/movies/sports/world/science/education/
horoscopes/cities), video pages, the news sitemap, and the RSS feed.

Akamai response headers are present (`itgd-akmttl`, `Akamai-GRN`,
`X-Varnish`) confirming an Akamai/Varnish CDN front, but no Bot Manager
challenge body, `Access Denied`/`errors.edgesuite.net` page, captcha, or
JS-challenge marker was observed on any request during recon (unlike
`ndtv-scraper`, also Akamai-fronted, where a plain client IS challenged).

**TLS profile pinned:** `chrome124` anyway, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even though nothing
in front of this site currently requires impersonation) and as cheap
insurance against Akamai Bot Manager being turned on more strictly later.

## Data sources

### 1. Article & video pages — `S1-jsonld` (primary, covers every template)

`GET https://www.indiatoday.in/<vertical>/[<subvertical>/]story/<slug>-<id>-<date>`
`GET https://www.indiatoday.in/<vertical>/[<subvertical>/]video/<slug>-<id>-<date>`

Every page sampled -- across 9+ verticals (business, india, sports, movies,
horoscopes, education-today, ...) and both the `story/` and `video/` URL
families, including `programme/<show>/video/...` -- emits a
`application/ld+json` `NewsArticle` block among 8-10 total ld+json script
tags on the page (also seen: `MobileApplication`, `WebPage`, `WebSite`,
`Organization`, `BreadcrumbList`, a custom `itgd_cdp` tracking block,
`Person`, and on video pages an additional `VideoObject`).

- **`story/` pages** (all non-video verticals): `NewsArticle` carries the
  full plain-text `articleBody` (1,700-4,000 characters across 5 samples),
  `headline`, `description`, `keywords` (comma-separated string, sometimes
  joined with a literal `&nbsp;` instead of a comma between phrases -- an
  upstream CMS quirk, passed through as-is), `articleSection`, a single
  `author` Person object (usually a desk credit like "India Today Business
  Desk" rather than a named reporter, unlike hindustantimes-scraper's
  author *array*), `publisher`, `image`, and `datePublished`/`dateModified`
  with `+05:30` IST offsets.

  **Quirk -- CMS boilerplate baked into `articleBody`:** every sampled
  article's `articleBody` ends with a literal `"- EndsPublished By: <name>
  Published On: <date> <time> IST"` tail, e.g. `"...avoid a wasted
  trip.- EndsPublished By: Jasmine anandPublished On: Aug 26, 2026 12:01
  IST"`. This is baked in by the CMS, not a scraping artifact -- passed
  through raw per this portfolio's convention.

- **`video/` pages** (all verticals, including `programme/<show>/video/...`
  live-show clips): the page additionally emits a `VideoObject` block, but
  the `NewsArticle` node has **no `articleBody` field at all** -- only
  `description` (a genuine multi-sentence prose recap, 400-900 characters
  across samples) and `headline`. Same pattern as `ndtv-scraper`. The
  extractor still returns a valid `S1-jsonld` record (raw passthrough of
  whatever the `NewsArticle` node contains) rather than raising
  `UnexpectedShape`. The richer `VideoObject` block (direct video/stream
  URL, `duration`, `thumbnailUrl`) is present on the page but **not**
  extracted by this actor -- see Known limits.

No `__NEXT_DATA__` was found -- India Today's CMS server-templates the
ld+json blocks directly into the HTML rather than using Next.js SSR data
injection.

**Quirk -- invalid strict-JSON control characters:** the `NewsArticle`
block's raw bytes contain unescaped literal control characters (bare `\r`/
newline bytes) inside `articleBody`/`keywords` on every sample. Python's
`json.loads` in strict mode raises `json.decoder.JSONDecodeError: Invalid
control character` on this block specifically (confirmed live 2026-08-26).
**Fix:** parse with `json.loads(raw, strict=False)` (RFC 8259 permits
control characters in strings when explicitly allowed; Python's `strict`
flag exists for exactly this). Every other actor in this portfolio using the
same `JSON_LD_RE` + `json.loads` pattern should double-check this if it
starts silently skipping blocks on a new site.

A defensive `S1b-jsonld-video` fallback (pick the `VideoObject` block
directly) exists in `extractor.py` for a page that lacks a `NewsArticle`
node entirely, but this was **not observed to trigger** on any of the ~10
URLs sampled across story/video/programme templates -- `NewsArticle` was
present every time.

### 2. Latest headlines — `S2-rss`

`GET https://www.indiatoday.in/rss/home`

Standard RSS 2.0 (`<channel>/<item>`), titled "India Today | Latest
Stories". Confirmed live 2026-08-26: 130+ items, mixing every vertical
(India, World, Business, Technology, Movies, Sports, Cities, Horoscopes...),
freshest `pubDate` within minutes of the request -- a genuine site-wide
feed (same tier as `ndtv-scraper`'s Feedburner feed, unlike
`hindustantimes-scraper` which only has a section-specific feed).

Fields used: `title`, `link`, `pubDate`, `description`. **No `<guid>`
element exists on items** (unlike hindustantimes-scraper/ndtv-scraper) --
not extracted.

**Quirk -- `link` carries a tracking query param:** every item's `<link>`
has `?utm_source=rss` appended, e.g.
`.../are-banks-closed-today-...-2980132-2026-08-26?utm_source=rss`. Confirmed
the underlying article loads identically with or without the param (it's
purely a CMS-side analytics tag, ignored server-side) -- passed through
as-is rather than stripped.

**Quirk -- `description` is HTML, not plain text:** each item's
`<description>` is a raw HTML fragment
(`<a href="..."><img .../></a> <plain text recap>`), not a plain-text
summary like hindustantimes-scraper/ndtv-scraper emit. Passed through
verbatim.

## Paywall behavior

No `isAccessibleForFree`/`hasPart` paywall-signal fields, and no truncated
`articleBody`, were observed on any sampled article. India Today's main news
content does not appear to carry a schema.org paywall marker. A `paywall`
string does appear in the HTML, but only as a CSS class name
(`Story_description__fq_4S description paywall story-with-main-sec`) on the
body container -- not a functional gate; every sampled `articleBody` was
full-length prose, not a preview snippet.

## Known limits

- `latest` mode returns the single site-wide feed only -- no per-section
  filter is exposed as an input.
- Video/programme pages return `NewsArticle` metadata (headline,
  description, dates, author) but **no `articleBody`** -- the richer
  `VideoObject` block (direct video URL, duration, thumbnail) on the same
  page is not extracted. A future enhancement could add a dedicated
  video-object extraction path if that becomes a requirement.
- Cricket live-score pages (`/live-score/...`) are out of scope -- explicitly
  `Disallow`'d for `Googlebot-News` in robots.txt and structurally different
  (JSON widgets, not article pages).
- `keywords` is a comma-separated string, not an array, and is sometimes
  joined with `&nbsp;` instead of a comma between phrases (see Quirk above)
  -- passed through as-is.
- `articleBody` carries an appended `"- EndsPublished By: ... Published On:
  ..."` CMS boilerplate tail (see Quirk above) -- not stripped.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
`story/` URL, a fresh `video/` URL, and `latest` mode, and confirm the
`NewsArticle` ld+json block is still found (with `strict=False` parsing
still required). If India Today redesigns the page, `extract_article` will
raise `UnexpectedShape` and the run will fail loudly rather than emit corrupt
records.
