"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-25): lanacion.com.ar (La Nación, Argentina, Arc
Publishing CMS -- same family as eluniversal-scraper) has NO active WAF
challenge. robots.txt (200, ~1.2KB) only disallows internal utility paths
(/pf/api/, /buscador, /Suscripcion form, /registracion, etc.), no
Claude/GPTBot/anthropic-ai disallow. chrome124 gets a clean 200 on
homepage, article pages, RSS feed, and sitemaps. Real 404s confirmed
(synthetic out-of-range article slug). See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.lanacion.com.ar"
WARMUP_URL = f"{BASE_URL}/"

RSS_URL = f"{BASE_URL}/arc/outboundfeeds/rss/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
