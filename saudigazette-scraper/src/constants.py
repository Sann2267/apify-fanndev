"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): saudigazette.com.sa (Saudi Arabia's oldest
English-language newspaper) has NO active WAF challenge -- it sits behind
Cloudflare + CloudFront (`server: cloudflare`, `cf-ray`, `via: CloudFront`
headers all present) but every sampled request (homepage, 3 article
categories, news sitemap, a synthetic 404) returned a clean response with
real HTML/XML, no "Just a moment"/challenge-platform body, no 403. Plain
`curl` with a generic Chrome UA (no TLS impersonation at all) already got
200s everywhere during initial triage.

robots.txt has one `User-agent: *` group with narrow path disallows
(`/*page=`, `/ajax/`, `/search/`, `/digital`, `/*.pdf`) plus several
fully-blocked SEO-crawler-specific groups (Baiduspider, SemrushBot, DotBot,
istellabot) that don't apply here -- no Claude/ClaudeBot/Claude-Web/
Claude-User/Claude-SearchBot/anthropic-ai entry anywhere, and no blanket
`Disallow: /` under the `*` group. None of the disallowed paths overlap
`/article/<id>/<slug>` or `/sitemaps/news_sitemap.xml`. See
CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://saudigazette.com.sa"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap, continuously refreshed, advertised in robots.txt.
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemaps/news_sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
