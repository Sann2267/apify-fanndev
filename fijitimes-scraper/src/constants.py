"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): fijitimes.com.fj (The Fiji Times, Fiji's
leading newspaper -- the FIRST Pacific Islands outlet in this portfolio)
has NO active WAF challenge. The site is Apache (Amazon Linux) fronted by
CloudFront (`x-cache`/`x-amz-cf-*` headers, `Server: Apache/2.4.68`) --
CDN only, no `_abck`/`bm_sz`/`_px3`/`_dd_s` bot-manager cookie, no cf-ray,
no challenge body. Plain `curl_cffi` `chrome124` gets a clean 200 on the
homepage, article pages, robots.txt and the sitemap on the very first
try -- no warmup-then-retry dance needed.

robots.txt is a stock Yoast SEO block (single `User-agent: *` group,
`Disallow:` empty -- allow-all) with no Claude/ClaudeBot/Claude-Web/
Claude-User/Claude-SearchBot/anthropic-ai token anywhere, and no
plain-English prohibition against AI/LLM training or scraping in any
comment (checked per the post-"Babak 17"/Star-Malaysia screening rule --
the file is 10 lines total, only the Yoast boilerplate + a `Sitemap:`
line).

WordPress (Gutenberg/full-site-editing theme) + Yoast SEO v28.2, but --
unusually for a Yoast install -- article pages emit **zero** ld+json:
no `<script type="application/ld+json">` block, no `__NEXT_DATA__`, no
`schema.org` reference anywhere in the page source (confirmed on 3
articles). `extract_article` is pure HTML + `<meta>` tags. The
`/wp-json/wp/v2/posts` REST endpoint is blocked (`401 rest_forbidden`),
so no JSON API shortcut either.

Each article page emits the standard OpenGraph/Twitter meta tags
**twice**, from two different injection points: a Yoast-labeled block
(wrapped in an explicit `<!-- This site is optimized with the Yoast SEO
plugin ... -->` HTML comment) using the bare `fijitimes.com` domain (no
`.fj`) in `og:url` and a `" - The Fiji Times"` suffix on `og:title`/
`<title>`, followed immediately by an unlabeled duplicate block using the
canonical `fijitimes.com.fj` domain (matching `<link rel="canonical">`)
and no title suffix. Both blocks' `article:published_time` represent the
literal same instant in different notations (e.g. `06:20:13+00:00` UTC
vs `18:20:13+12:00` Fiji local -- 6+12=18, consistent) -- not a data
conflict, just duplicate emission. `extract_article` takes the first
occurrence of each field (`soup.find`), which resolves to the
Yoast-labeled block. `article:modified_time` and `meta[name="author"]`
each appear identically in both blocks.

No paywall of any kind was found -- only a normal print-subscription nav
link (`/subscribe/`), and full article text is served in the initial
HTML response with no metering/truncation observed on any of the 3
articles sampled.

Nonexistent article slugs return a REAL HTTP 404 (confirmed on a
deliberately-invented slug) -- no soft-404 quirk observed.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.fijitimes.com.fj"
WARMUP_URL = f"{BASE_URL}/"

# The WordPress default feed (`/feed/`) 301-redirects straight to the
# homepage (a dead/disabled feed, matching this portfolio's prior
# experience with other smaller Commonwealth regional dailies -- Jamaica
# Gleaner, Trinidad Guardian). `latest` mode uses the Yoast SEO
# `sitemap_index.xml` -> newest `post-sitemap*.xml` instead. Each
# `post-sitemap*.xml` page (1000 <url> entries per full page, 260 on the
# newest/partial one) is in ascending chronological order by `<lastmod>`
# (oldest entry first, newest last) -- confirmed across all 5 pages, whose
# ranges chain into one continuous ascending timeline
# (post-sitemap.xml: May25-Jun16 -> ...2: Jun16-Jul05 -> ...3: Jul05-Jul27
# -> ...4: Jul27-Aug20 -> ...5: Aug20-Aug26, the current newest page), and
# the very last entry of the newest page matches the homepage's current
# top story. QUIRK: the unnumbered `post-sitemap.xml` (page 1) has a
# spurious first `<url>` entry for the bare homepage itself (not an
# article) whose own `<lastmod>` happens to equal the true-newest page's
# -- picking the "newest" page by sorting sitemap_index.xml entries on
# their own `<lastmod>` breaks on that tie, so `extract_sitemap_index`
# instead takes the LAST `post-sitemap*.xml` entry in the index's
# document order (Yoast lists pages in ascending page order), and
# `extract_sitemap_items` defensively skips any entry whose `<loc>` is
# just the bare homepage. No `<title>` or per-item publish date is
# carried in this generic post-sitemap (only `loc`/`lastmod`/
# `image:loc`) -- unlike a Yoast *News* SEO sitemap, this site does not
# have that plugin, so latest-mode records carry only `link`/`lastmod`/
# `image`, not a headline (fetch the article in `article` mode for the
# real title/date).
SITEMAP_INDEX_URL = f"{BASE_URL}/sitemap_index.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
