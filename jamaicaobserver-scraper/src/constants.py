"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): jamaicaobserver.com (Jamaica Observer, one of
Jamaica's two main daily newspapers -- a genuinely separate publisher from
The Gleaner, already covered by this portfolio's jamaicagleaner-scraper) has
NO active WAF challenge. robots.txt is a short, fully-open file (`Disallow:`
empty, `Allow: /` for `User-agent: *`, plus a no-op `grapeshot` group with an
empty `Disallow:` too) -- no Claude/ClaudeBot/Claude-Web/Claude-SearchBot/
anthropic-ai disallow, and no plain-English AI/LLM-training prohibition text
anywhere in the file. Even a plain `requests` baseline with no TLS
impersonation gets a clean 200 on the homepage (`server: BunnyCDN-LA1-900`,
a CDN, not a WAF) -- `curl_cffi chrome124` is used anyway for consistency
with the portfolio-wide default and resilience against a future WAF rollout.

Unlike jamaicagleaner-scraper (sitemap.xml 404, rss.xml an empty stub,
requiring a homepage-link-scrape fallback), this site's WordPress `/feed/`
RSS endpoint works cleanly: 37 items, real `pubDate`, `dc:creator` (a real
byline -- reporter name + title + email, not a Cloudflare-obfuscation
placeholder), `category`, and full `content:encoded` HTML body. No fallback
discovery strategy was needed.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.jamaicaobserver.com"
WARMUP_URL = f"{BASE_URL}/"
LATEST_RSS_URL = f"{BASE_URL}/feed/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
