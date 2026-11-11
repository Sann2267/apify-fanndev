"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): organiser.org (Organiser, India, English-language
weekly news magazine published by the RSS) sits behind Cloudflare (server:
cloudflare, cf-ray present on every response) but presents NO challenge to
plain curl_cffi chrome124 impersonation -- homepage, article pages, the
site-wide `/feed/` (including `?paged=N`), and the news sitemap all returned
200 with full content, no "Just a moment"/challenge-platform/captcha body
markers. chrome124 is pinned per the portfolio-wide default of avoiding the
most-blocklisted profile even when it currently works.

robots.txt is a legacy Joomla-style block (leftover directive set --
/administrator/, /components/, /templates/ etc. -- the site actually runs
WordPress today, so these paths don't even exist) plus a couple of
/wp-admin//xmlrpc/ entries, all under one `User-agent: *` group with no
Claude/ClaudeBot/Claude-Web/Claude-SearchBot/anthropic-ai disallow of any
kind, no blanket `Disallow: /`, and no plain-English AI/LLM-training
prohibition text anywhere in the file (checked in full, not just parsed
directives). Confirmed crawlable.

Despite being a *weekly print* magazine, the organiser.org *website*
publishes many articles per day (confirmed via the live news sitemap and RSS
feed, both updating multiple times per hour) -- `latest` mode uses the
normal high-frequency `/feed/` rather than anything print-cadence-limited.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://organiser.org"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide WordPress feed. Confirmed live on 2026-08-26 -- rich fields
# (title, link, guid, pubDate, dc:creator, category (list), and a
# full-HTML content:encoded body ~1.4x longer than <description>).
# NOT actually paginated: `?paged=N` returns HTTP 200 but the byte-identical
# first page again (same 10 guids, same order) -- confirmed via direct
# fetch/diff. `latest` mode is capped at this feed's natural page size (10
# items) as a result. See CRAWLING_METHOD.md.
RSS_URL = f"{BASE_URL}/feed/"
RSS_PAGE_SIZE = 10

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
