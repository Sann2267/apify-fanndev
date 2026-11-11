# Crawling Method — Daily Mirror

**Last verified:** 2026-08-26

## robots.txt

```
User-agent: *
Allow: /
User-agent: Googlebot
Allow: /
User-agent: Slurp
Allow: /
User-Agent: msnbot
Allow: /

Sitemap: https://www.dailymirror.lk/sitemaps
Crawl-delay: 3600
```

Fetched fresh (not reused from a prior check). **Four separate `User-agent`
groups, each with its own `Allow: /` line directly beneath it** — there is
no `Disallow` directive anywhere in the file, under any group, so this is
not the Babak-14 shared-`Disallow` parser-bug pattern (a single `Disallow:`
line shared by multiple preceding `User-agent:` lines that a naive script
attributes only to the last one). Each group was read individually. No
`Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`, or
`anthropic-ai` token appears anywhere in the file. **Verdict: not blocked.**

`Crawl-delay: 3600` (one hour) is present under the wildcard group. This
actor runs on-demand per user request rather than as a continuous crawler,
so it doesn't map cleanly onto a "requests per second" throttle — but it's
a signal the site doesn't expect frequent automated revisits. Kept
`maxConcurrency` default modest (4) and didn't build any scheduled/
continuous-polling pattern into "latest" mode as a result.

## WAF

**No active challenge found.** Plain `curl` with no TLS impersonation at
all already got a clean 200 on the homepage, article pages, and category
listing pages. The full `curl_cffi` profile ladder (`chrome124`,
`chrome99_android`, `safari17_0`, `edge101`, `firefox133`) was still run
per the mandatory triage step — every profile returned 200 with
effectively identical body sizes (317504–317562 bytes on the homepage,
150847–151309 on the sample article). No `_cf_chl_`/"Just a moment"/
`challenge-platform` marker, no `_abck`/`bm_sz`, no CAPTCHA, ever appeared.

The site **is** Cloudflare-fronted (`Server: cloudflare`, `cf-ray` header,
`cf-cache-status: DYNAMIC`, `cf-nel`/`Report-To` beacons) but this is
CDN/edge-caching plumbing only, not an active bot-management challenge.
`chrome124` is pinned for portfolio consistency even though it made no
observable difference over a bare `curl` request here.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://www.dailymirror.lk/<section>/<slug>/<categoryId>-<articleId>`
— `<section>` varies by content type (`breaking-news`, `sports`,
`business`, `school_rugby`, ... observed; likely others not sampled). Only
the trailing `<categoryId>-<articleId>` pair matters for routing — the
slug text and even the section name in the path are cosmetic. Confirmed:
`/breaking-news/foo/108-1` (nonsense slug, ID 1) resolves to a real,
very old article ("KKS port area to be made vibrant economic hub - PM"),
the same "only the trailing numeric ID is real routing state" behavior
documented for ghanaweb-scraper and kyivpost-scraper.

The page emits **one top-level (not `@graph`-wrapped)**
`application/ld+json` block, `@type: "NewsArticle"`, that carries the
**full `articleBody` directly** — no HTML-container fallback is needed at
all for this site (unlike ghanaweb-scraper, whose ld+json omits
`articleBody` entirely). Also present: `headline`, `description`,
`datePublished`/`dateModified` (ISO 8601 with `+05:30` offset), `author`
(a `Person` object — either a specific reporter's full name, e.g.
`"CHATURANGA PRADEEP SAMARAWICKRAMA"`, or the generic literal string
`"DM Editorial"` on many pieces, especially older/syndicated ones), and
`image` (object: `url`/`width`/`height`).

**Quirks found:**

- `articleSection` is **always** the literal string `"Sri Lanka"` on every
  sampled article regardless of actual section (breaking news, sports,
  business, school sport, ...) — useless as a category signal. `category`
  is instead derived from the article URL's first path segment (e.g.
  `breaking-news`, `sports`, `school_rugby`), same pattern as ghanaweb's
  sitemap `section` derivation.
- `publisher` and `mainEntityOfPage` are static boilerplate, identical on
  every article (same organization name/logo, and a URL that duplicates
  the input) — dropped from output rather than repeated on every record.
- `image.url` is sometimes the **literal string `"none"`** (no lead image
  set for that article) rather than being absent/null, and when an image
  does exist the URL is sometimes a **relative path**
  (`assets/uploads/image_a177e06553.jpeg`) rather than an absolute URL —
  passed through as-is per the raw-passthrough convention; downstream
  consumers need to handle both cases.
- **Text fields carry literal, undecoded HTML entities** inside the JSON
  string values themselves — e.g. `"...23&ndash;21 vs..."`,
  `"...development.&nbsp;"`, `"...Sagala Ratnayaka&rsquo;s..."` — rather
  than either real Unicode punctuation or being entity-free. `headline`,
  `description`, and `articleBody` are all passed through `html.unescape()`
  before being added to the record.
- **Invalid raw JSON — the big one.** The ld+json blob embeds literal,
  unescaped control characters (real newline bytes marking `articleBody`'s
  paragraph breaks) directly inside a JSON string value instead of
  encoding them as `\n`. Every single article on the site fails to parse
  under Python's default strict `json.loads()`, raising
  `json.decoder.JSONDecodeError: Invalid control character at: line 1
  column ...` at the position of the first embedded newline. This isn't a
  per-article edge case — it reproduced on every sample fetched (breaking
  news, sports, business, an old 2019-dated archive article). Fixed with
  `json.loads(raw, strict=False)`, which is Python's documented escape
  hatch for exactly this ("control characters will be allowed inside
  strings"). Any future maintenance code that touches this ld+json block
  must remember `strict=False` or every article will silently look like a
  "no ld+json found" case.

### 2. Soft-404 behavior (both article and listing route families)

dailymirror.lk's router **never returns a real HTTP 404** for any path
tried during recon — every request returns 200. Two distinct shapes were
found:

- A syntactically valid article route (`/<anything>/<anything>/<catId>-
  <articleId>`) with a **non-existent** `<articleId>` still renders the
  full article-page template, ld+json block included, but with every field
  an empty string: `"headline":"","url":"","articleBody":"",
  "datePublished":"","author":{"name":""}`. `mainEntityOfPage.@id` is also
  `""`. The `<title>` tag is literally `  -  | Daily Mirror`.
- A path that doesn't match the article-route pattern at all (e.g.
  `/this-page-does-not-exist-at-all`, no trailing `<n>-<n>`) renders a
  **completely different, smaller fallback template with no ld+json block
  at all** (checked: 70,951 bytes vs. ~145–151 KB for a real article page,
  empty `<title>`).

Both cases are detected and treated identically as `_error: "not_found"`
by `extract_article` (see its docstring / `ArticleNotFound` in
`src/extractor.py`) — first by checking whether any `NewsArticle` ld+json
block exists at all, then by checking whether `headline`/`url`/
`articleBody` are all empty.

### 3. Latest headlines — `S2-html-listing`

No working feed of any kind was found:

- `/rss`, `/feed`, `/rss/latest-news` all return **HTTP 200** but with the
  exact same content as the homepage (soft-redirect-via-200 to the
  homepage template, not a real RSS/Atom document).
- `/sitemap.xml`, `/sitemap_index.xml`, `/sitemap-news.xml` all return
  **404**.
- The `Sitemap:` line in `robots.txt` points at
  `https://www.dailymirror.lk/sitemaps` — this URL returns 200 but renders
  an ordinary HTML page (the homepage template), not an XML sitemap, and
  has no `<a>` links to any actual machine-readable sitemap file anywhere
  in its markup.

Instead, "latest" mode scrapes the site's own **Breaking News category
listing page**, `https://www.dailymirror.lk/breaking_news/108`
(`categoryId` 108 = Breaking News — the same category ID that turns up on
the vast majority of front-page news/sports/business articles, since Daily
Mirror routes most wire-style news through this one bucket regardless of
topic). Confirmed **sorted newest-first by descending numeric article ID**
across two consecutive pages of real IDs (348860, 348859, 348857, 348856,
348855, ... descending in strict order) — with **one exception**: a
pinned "Sri Lanka Dengue Cases 2026 – Live Tracker" story (an old,
continuously-updated article, ID 345917) stays fixed at the very top of
every listing page regardless of actual recency. This pinned item is
included in "latest" mode output as a normal record (it's real, current
content the site itself chooses to keep pinned) rather than filtered out,
since distinguishing "legitimately pinned evergreen content" from "stale
listing bug" isn't reliably automatable from the HTML alone.

The listing page supports simple **offset pagination**:
`/breaking_news/108/<offset>` in steps of 30 (`/breaking_news/108/30`,
`/breaking_news/108/60`, ...) returns a different page of ~28–32 articles
with no overlap observed between consecutive pages. `fetch_latest` walks
these pages until it collects `limit` items or a page returns no new
links.

**Quirk:** each article's URL appears in **three separate `<a>` tags** per
listing card — a thumbnail-image link (no text), a headline-text link, and
a teaser-summary link (longer text) — always in that same document order.
`extract_listing_items` keeps the **first non-empty text** found per
unique href, which reliably captures the headline rather than the longer
teaser summary.

## Paywall behavior

**None observed.** Free, ad-supported portal. `articleBody` was returned
complete (multi-paragraph, matching what a human reader would see) on
every sample checked across sections (breaking news, sports, an old 2025
school-rugby piece, a 2019-era archive article via the low-ID probe). No
`isAccessibleForFree` field is emitted in ld+json at all (consistent with
a site that has no metering/subscription product). The only "Subscribe"
strings found in the HTML are a commented-out `<!-- ... -->` newsletter
button and a live "Subscribe" button that links to
`/admin/createview` (an account/CMS admin flow, unrelated to article
access) — neither gates any content.

## Known limits

- `articleId`/`categoryId` extraction relies purely on the URL's trailing
  `<categoryId>-<articleId>` numeric pair via regex — if Daily Mirror ever
  changes its URL scheme (e.g. adds a query string suffix after the ID),
  this would silently return `None` for both rather than crash, since the
  regex is treated as best-effort metadata, not a required field.
- `category` is a raw URL path segment, not a normalized taxonomy — the
  site uses inconsistent casing/spelling across sections (`breaking-news`
  hyphenated, `school_rugby` underscored) and this is passed through
  as-is rather than normalized, per the raw-passthrough convention.
- The "latest" mode pinned-Dengue-tracker quirk (see above) means the very
  first item of every "latest" run for the `breaking_news` category may be
  a stale, non-representative "latest" headline. Documented, not filtered.
- Only ~10 articles were sampled in depth across sections (breaking news,
  sports/cricket, school rugby, a 1-ID archive probe, one soft-404
  probe, one totally-invalid-path probe). A structurally different
  template — photo gallery, video feature, live-blog/liveblog format, the
  paginated columnist archive pages under `/Weekend_Online/...` — was not
  sampled and might not carry the same single top-level `NewsArticle`
  ld+json block this extractor depends on. If such a page is fed to
  `extract_article`, `ArticleNotFound` would incorrectly fire (since no
  ld+json block would be found) rather than a genuine `UnexpectedShape` —
  a low-risk failure mode (an error record instead of a crash) but worth
  knowing about.
- No RSS/sitemap fallback exists for "latest" mode if the Breaking News
  category listing page's HTML structure changes — there is no S3 tier to
  fall back to. `extract_listing_items` raises `UnexpectedShape` (crashing
  the run loudly) rather than returning an empty list if no article links
  are found on a listing page, per the fail-loud convention.

## Diff cadence

Quarterly smoke test recommended.
