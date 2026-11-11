"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-25): ft.lk (Daily FT, Sri Lanka's leading business
newspaper) has NO active WAF challenge -- robots.txt is fully open
(`Allow: /` for `*`/Googlebot/Slurp/msnbot), no Claude/GPTBot/anthropic-ai
disallow of any kind. chrome124 gets a clean 200 on the homepage, article
pages, and the RSS feed.

Reliability quirk (not a block): the backend (nginx behind Cloudflare)
returns intermittent 503 "Service Temporarily Unavailable" on some
endpoints, including the sitemap index -- confirmed transient (retrying
the exact same request seconds later succeeds with a clean 200). This
matches what earlier recon passes on this project logged as "timeout" --
it's server flakiness, not an anti-bot signal. The existing retry/backoff
in client.py handles it without special-casing.

This site was previously flagged across multiple recon sessions as
"legacy markup, no ld+json, body container unclear" -- confirmed: there
is genuinely NO ld+json anywhere on article pages, and the CMS is an old,
hand-formatted template (`ng-app="single_module"` Angular is present but
ONLY powers a page-view "Hits" counter widget, not the article content --
confirmed by finding the full article body already present in the raw
server-rendered HTML). See CRAWLING_METHOD.md for the full body-extraction
strategy.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.ft.lk"
WARMUP_URL = f"{BASE_URL}/"
HOME_TITLE = "Sri Lanka's only national business newspaper | Daily FT"

# The "top-story" section RSS feed doubles as a general/front-page feed
# spanning multiple sections (confirmed fresh: newest item matched the
# newest article found via direct homepage scraping during recon). The
# sitemap index (`/sitemaps`, 294 paginated files) was found to be
# stale/lagging real content by ~2 months on its highest-numbered file, so
# it is NOT used for "latest" mode despite being advertised in robots.txt.
LATEST_RSS_URL = f"{BASE_URL}/rss/top-story/26"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
