"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-25): brecorder.com (Business Recorder, Pakistan's
leading financial/business daily) has NO active WAF challenge -- Cloudflare
is present as CDN only (`server: cloudflare`, `cf-ray` header) but chrome124
gets a clean 200 with full content on homepage, article pages, robots.txt,
and the sitemap. robots.txt has a single `User-agent: *` group disallowing
only `*/print`, `*/authors/*/<digit>*`, and `/search` -- no Claude/GPTBot/
anthropic-ai disallow of any kind. Real HTTP 404s confirmed (synthetic
out-of-range article ID returns a genuine 404 with "Not Found - Business
Recorder" title, not a soft-404). No RSS/Atom feed exists (`/rss`,
`/rss.xml`, `/feed`, `/feeds/rss`, `/feeds/rss.xml` all 404) -- `latest`
mode uses the Google News XML sitemap instead. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.brecorder.com"
WARMUP_URL = f"{BASE_URL}/"

# Business Recorder has no RSS/Atom feed (confirmed 404 on every standard
# path). This is a Google News-flavored XML sitemap (declares the
# `news_sitemap.xsd` namespace) that lists the ~100 most recently published
# articles site-wide, each with a `<news:news>` block carrying title,
# language, and publication_date (date-only granularity). Discovered via
# the `Sitemap:` line in robots.txt.
SITEMAP_URL = f"{BASE_URL}/feeds/sitemap"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
