"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): thepeninsulaqatar.com (The Peninsula, English-
language Qatari national newspaper) has NO active WAF challenge -- it sits
behind Cloudflare (cf-ray header present) but every sampled request returned
a clean 200 with real HTML, no "Just a moment"/challenge-platform body.
robots.txt only carries a decades-old generic "Bad-Robots" denylist
(Wget, TeleportPro, EmailCollector, etc., one Disallow-per-User-agent
line, individually blocked -- no grouped/shared Disallow block spanning
multiple User-agent lines) and standard CMS path disallows (/admin/,
/cgi-bin/, install scripts, etc.) -- no Claude/ClaudeBot/Claude-Web/
Claude-User/Claude-SearchBot/anthropic-ai/GPTBot/CCBot entry anywhere.
No `Sitemap:` directive is advertised in robots.txt, but a real sitemap
index lives at the conventional `/sitemap.xml` path. chrome124 gets a
clean 200 on the homepage, article pages, and the sitemap index/shards.
Real 404s confirmed (synthetic out-of-range `/article/<date>/<slug>`).
See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://thepeninsulaqatar.com"
WARMUP_URL = f"{BASE_URL}/"

SITEMAP_INDEX_URL = f"{BASE_URL}/sitemap.xml"


def article_sitemap_url(year: int, month: int) -> str:
    """Monthly-sharded Google News sitemap URL (month has no leading zero)."""
    return f"{BASE_URL}/sitemap_articles-{year}-{month}.xml"


DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
