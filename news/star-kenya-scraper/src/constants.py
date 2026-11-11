"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): the-star.co.ke (The Star, Kenya -- national daily
published by Radio Africa Group) shows NO active WAF challenge. The site is
Cloudflare-fronted (`server: cloudflare`, `cf-ray`) but only as a CDN --
homepage, article pages (both free and premium-gated), and the article
sitemap all return a clean 200 with chrome124 on the first try. No
profile-ladder escalation was needed.

`robots.txt` has a SINGLE `User-agent: *` group: `Allow: /` (fully
permissive, no `Disallow` at all). No `Claude`, `ClaudeBot`, `Claude-Web`,
`Claude-User`, `Claude-SearchBot`, or `anthropic-ai` token appears anywhere
in the file (re-verified fresh -- see CRAWLING_METHOD.md).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.the-star.co.ke"
WARMUP_URL = f"{BASE_URL}/"

# Plain XML sitemap (loc/lastmod/changefreq only -- no <news:*> namespace,
# no title). /sitemap_index.xml lists 50 numbered article sitemaps;
# /articles/sitemap/1.xml was confirmed to carry same-day articles (freshest
# items dated the day of the fetch). Entries are NOT reliably sorted by
# lastmod within the file, so extract_sitemap_items() sorts them itself.
ARTICLE_SITEMAP_URL = f"{BASE_URL}/articles/sitemap/1.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
