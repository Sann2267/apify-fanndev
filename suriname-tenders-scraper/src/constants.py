"""Shared constants for the gov.sr (Overheid van de Republiek Suriname)
tenders scraper.

See CRAWLING_METHOD.md for the full recon writeup. Short version: Suriname
has no dedicated e-GP/e-procurement platform (the "GOEDGE" / "Staatstenders
Suriname" names that show up in secondary sources and search-engine AI
summaries do not resolve to any real, reachable host -- hallucinated, same
pattern flagged repeatedly elsewhere in this portfolio). The genuinely
official, reachable source is the government's own WordPress site,
`gov.sr` ("Overheid van de Republiek Suriname"), which publishes tenders
through two separate, fully public WordPress REST API routes:

1. **tenders** -- `GET /wp-json/wp/v2/aanbestedingen`: a dedicated custom
   post type (not a category on the generic blog) used government-wide for
   routine procurement notices -- mostly domestic works/goods/services
   tendered directly by individual ministries, in Dutch. 671+ records at
   recon time, dating back to May 2022. Each record is intentionally thin
   (title, date, ministry/category, link) -- there is no richer body text
   on the individual page for this post type (`content` is not part of its
   REST schema at all, and the rendered page itself carries nothing beyond
   the title and, inconsistently, a one-line ministry attribution already
   redundant with the taxonomy term), so this actor does not attempt a
   separate per-record detail fetch for this list type.
2. **notices** -- `GET /wp-json/wp/v2/posts?categories=<id of "Aanbestedingen">`:
   the same "Aanbestedingen" (Tenders) category applied to the site's
   regular blog `post` type, used for a much smaller number of larger,
   internationally/donor-financed solicitations (World Bank, IDB, the
   February 2026 Social Bond program) -- mostly in English, with full
   rendered body content already included in the same list response
   (background, procurement method, eligibility, bid evaluation criteria,
   submission deadline and address). ~11 currently open notices at recon
   time; older/closed ones appear to be taken down rather than archived,
   so this list type reflects "what's open right now", not a historical
   archive.

Both routes require zero authentication and were reachable with a plain
`curl_cffi` request on the first try -- no WAF challenge, no TLS-profile
sensitivity observed (the host sits behind Cloudflare per its response
headers, but purely as a CDN/cache layer: `cf-cache-status: DYNAMIC`,
`cache-control: max-age=31536000` on the JSON API responses themselves,
no challenge page, no `cf_clearance` cookie required).
"""

BASE = "https://gov.sr"
WP_API = f"{BASE}/wp-json/wp/v2"

TENDERS_CPT_URL = f"{WP_API}/aanbestedingen"
POSTS_URL = f"{WP_API}/posts"
CATEGORIES_URL = f"{WP_API}/categories"

NOTICES_CATEGORY_SLUG = "aanbestedingen"

VALID_LIST_TYPES = ("tenders", "notices")

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
}

PER_PAGE = 100  # WordPress REST API hard cap

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0

# robots.txt (`GET https://gov.sr/robots.txt`) is a blanket allow --
# `user-agent: *` / `disallow:` (empty) -- with a single `crawl-delay: 60`
# directive and no per-bot rules of any kind (no Claude/ClaudeBot/
# anthropic-ai group, no natural-language prohibition). Honored literally
# here via a process-wide rate limiter shared across all requests, same
# pattern as comoros-anpi-scraper.
CRAWL_DELAY = 60.0
