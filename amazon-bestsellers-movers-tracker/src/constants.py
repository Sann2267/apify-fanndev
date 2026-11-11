"""Endpoints, TLS profiles and tuning constants for the Amazon rank tracker.

Access profile (recon 2026-09-01, see CRAWLING_METHOD.md)
--------------------------------------------------------
Amazon's Best Sellers pages are genuinely open to anonymous HTTP. The full
mandatory ladder was run before assuming anything: chrome124/131/116,
chrome99_android, safari17_0/18_0, firefox133 and edge101 **all returned 200
with the bestseller grid** -- no CAPTCHA, no bot wall, no interstitial. This
is not a target that needs a browser.

Two structural facts drive the whole design
-------------------------------------------
1. Each list page carries `data-client-recs-list`, a JSON attribute holding
   **all 50** ASINs with their ranks. Two pages give a clean 1-100. This is
   the stable spine of the extraction and is preferred over CSS selectors.
2. Only **30 of those 50** product tiles are server-rendered with full
   details; the rest lazy-load. So a 100-product run yields 100 ranked ASINs
   and roughly 60 with price/rating/reviews. `hasDetails` marks which.

A crawler User-Agent renders all 50 tiles, but that view is a stripped SEO
page: measured field coverage was price 0/50, rating 0/50, reviews 0/50
versus 29/30, 30/30, 30/30 on the normal view. More rows, far less data --
so the normal browser identity is used deliberately.

Movers & Shakers
----------------
Amazon's own Movers & Shakers pages returned **no data in any category
tested** (electronics, books, toys, home, beauty), each showing "Sorry, there
are no movers and shakers available in this category." The metadata fields
for it exist in the recs-list schema (`render.zg.bsms.percentageChange`,
`currentSalesRank`, `twentyFourHourOldSalesRank`) and are read when present,
but they were empty throughout recon.

So this actor computes movement itself from rank snapshots between runs.
That is more dependable than Amazon's page, and it is what makes the actor a
*tracker* rather than a one-shot scraper.
"""

DOMAINS = {
    "com": "https://www.amazon.com",
    "co.uk": "https://www.amazon.co.uk",
    "de": "https://www.amazon.de",
    "fr": "https://www.amazon.fr",
    "it": "https://www.amazon.it",
    "es": "https://www.amazon.es",
    "ca": "https://www.amazon.ca",
    "com.au": "https://www.amazon.com.au",
    "co.jp": "https://www.amazon.co.jp",
    "in": "https://www.amazon.in",
}

# The three sibling ranked lists. All three were verified to serve the same
# `data-client-recs-list` + faceout structure.
LIST_PATHS = {
    "bestsellers": "/Best-Sellers/zgbs/{category}",
    "new-releases": "/gp/new-releases/{category}",
    "most-wished-for": "/gp/most-wished-for/{category}",
    "movers-and-shakers": "/gp/movers-and-shakers/{category}",
}

TLS_PROFILE_LADDER = ("chrome124", "safari17_0", "firefox133", "edge101", "chrome116")

PAGE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 2.0
REQUEST_TIMEOUT = 45

# 50 ranks per page; Amazon serves ranks 1-100 over two pages.
RANKS_PER_PAGE = 50
MAX_PAGES = 2
DEFAULT_DELAY_SECONDS = 1.5

# Snapshot of the previous run, in a *named* store so it survives between
# scheduled runs (the default store does not).
STATE_STORE_NAME = "amazon-rank-state"

MOVE_NEW = "NEW_ENTRY"
MOVE_RISING = "RISING"
MOVE_FALLING = "FALLING"
MOVE_UNCHANGED = "UNCHANGED"
MOVE_DROPPED = "DROPPED_OUT"

# Rank deltas below this are noise on a list that reshuffles hourly.
SIGNIFICANT_MOVE = 5
