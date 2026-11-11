"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-24): chicagotribune.com has NO WAF on the homepage or
article pages -- chrome124 returns clean 200s, no challenge body. However,
the RSS feed (`/feed/`, any `/*/feed/` section variant) AND the dated
sitemap endpoints (`/sitemap.xml?yyyy=...&mm=...&dd=...`, though the bare
top-level `/sitemap.xml` sitemap-index works) are gated by a custom
JS hashcash proof-of-work challenge (`X-Hashcash-Solution` header, SHA-256
computed client-side, POST to `/__challenge`). This is NOT one of the
standard vendor WAFs (Cloudflare/DataDome/PerimeterX/Akamai) -- looks
homegrown or a niche product, selectively applied to feed/sitemap
endpoints only, not the page-render path. Solving it HTTP-only is possible
in principle (replicate the SHA-256 PoW in Python) but wasn't pursued here
since the homepage itself is open and sufficient for `latest` mode -- see
CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.chicagotribune.com"
WARMUP_URL = f"{BASE_URL}/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
