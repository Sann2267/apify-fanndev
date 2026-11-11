"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): kathmandupost.com (The Kathmandu Post,
English-language Nepali national newspaper) has NO active WAF challenge --
it sits behind Cloudflare (cf-ray header present) but never serves a JS
challenge / "Just a moment" page, only a plain 200. robots.txt is a
single `User-agent: * / Disallow:` group (wide open, nothing disallowed
at all) -- no Claude/GPTBot/anthropic-ai disallow of any kind, and no
`Sitemap:` line either. chrome124 gets a clean 200 on the homepage,
article pages, and `/rss`. Soft-404s confirmed (synthetic bogus slug --
see CRAWLING_METHOD.md); no real 404 status observed for a bad article
path.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://kathmandupost.com"
WARMUP_URL = f"{BASE_URL}/"

# /feed, /rss.xml, /sitemap.xml, /news-sitemap.xml, /sitemap_news.xml,
# /sitemap-news.xml all soft-404 back to the homepage shell (HTTP 200,
# generic HTML, not XML). Only /rss returns real RSS 2.0 XML.
RSS_URL = f"{BASE_URL}/rss"

GENERIC_TITLE = "The Kathmandu Post | Read online latest news and articles from Nepal"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
