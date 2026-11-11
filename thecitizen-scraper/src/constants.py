"""Endpoints, headers, profile choices — all in one place.

Recon summary (2026-08-26): thecitizen.co.tz (The Citizen, Tanzania -- part
of the Nation Media Group / Mwananchi Communications Ltd stable, sibling of
Daily Nation Kenya and Business Daily Africa) is Cloudflare-fronted
(`server: cloudflare`, `cf-ray` present) but shows NO active challenge --
`chrome124` gets a clean 200 on the homepage, article pages, and
sitemap.xml, with no `cf-mitigated` header, no bot-management cookie, no
"Just a moment..." interstitial. robots.txt has a single `User-agent: *`
group -- no Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/
anthropic-ai token appears anywhere. See CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.thecitizen.co.tz"
WARMUP_URL = f"{BASE_URL}/"

# Google News sitemap, advertised in robots.txt (`sitemap:` line). Carries
# news:title / news:publication_date / news:keywords / news:access (paywall
# flag) per item -- richer than the site's plain /rss.xml feed, which lacks
# the access/paywall signal. Capped at ~40 of the newest items.
NEWS_SITEMAP_URL = f"{BASE_URL}/sitemap.xml"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
