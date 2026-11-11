"""Endpoints, headers, profile choices -- all in one place.

Recon summary (2026-08-26): mmegi.bw (Mmegi, Botswana's leading independent
newspaper) sits behind a layered CDN -- Cloudflare at the edge
(`server: cloudflare`, `cf-ray`, `cf-cache-status`) fronting an AWS
CloudFront/ALB origin (`X-Cache: ... cloudfront`, `AWSALB`/`AWSALBCORS`
cookies) -- but shows NO active bot-management challenge. `chrome124` gets a
clean 200 on the homepage, article pages (3 sections sampled: news, sports,
opinion), and the RSS feeds on the first try. No `cf_clearance` cookie, no
`__cf_chl_*`, no "Just a moment..." interstitial, no CAPTCHA. The
`AWSALB`/`AWSALBCORS` cookies are plain load-balancer session stickiness, not
a challenge token.

`robots.txt` has a single `User-agent: *` group (plus narrow MJ12bot/PetalBot
blocks that don't apply here) with `Disallow: /ajax/*`, `/*.pdf`, `/widget/*`,
`*/page/*`, `/search*` -- no blanket `Disallow: /`, and no `Claude`,
`ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`, or
`anthropic-ai` token appears anywhere in the file (re-verified fresh). See
CRAWLING_METHOD.md.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.mmegi.bw"
WARMUP_URL = f"{BASE_URL}/"

# Site-wide "News" RSS feed -- one of several category feeds advertised on
# the human-readable /rss sitemap page (News=1, Business=2, Sports=3,
# Features=4, Opinion & Analysis=13, ...). Not listed in robots.txt (no
# `sitemap:` line at all on this site), discovered by following the /rss
# page's own links. Confirmed same-day freshness and a consistent item shape
# (title/link/description/author/pubDate/media:thumbnail/media:content)
# across all sampled categories -- see CRAWLING_METHOD.md.
RSS_URL = f"{BASE_URL}/rssFeed/1"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
