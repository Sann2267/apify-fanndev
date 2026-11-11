"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): malaymail.com is fronted by Cloudflare +
CloudFront (`server: cloudflare`, `x-amz-cf-id`/`via: CloudFront` headers on
the homepage) but shows NO active challenge -- curl_cffi chrome124 gets a
clean 200 on the homepage, article pages, and the site-wide RSS feed, no
warmup needed either, though warmup/retry scaffolding is kept anyway per
portfolio convention. robots.txt has no Claude/anthropic-ai-specific stanza
but also no blanket `Disallow: /` -- the generic `User-agent: *` group only
blocks `/ajax/*`, `/print*`, `/search*`, `/archive/*`, `/widget/*`,
`*/page/*`, `/*.php` etc, none of which this actor touches. See
CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.malaymail.com"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide headlines feed. Confirmed live, 50 items per fetch, each item
# carrying the FULL article HTML in <content:encoded> (not just a teaser).
RSS_URL = f"{BASE_URL}/feed/rss"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-MY,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
