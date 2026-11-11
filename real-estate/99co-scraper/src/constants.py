"""Fixed facts about 99.co, established by recon on 2026-09-21.

99.co serves two entirely different applications from one domain:

  /id          Indonesia. Next.js Pages Router, data in __NEXT_DATA__.
               The richest surface on the site -- price history, mortgage
               tables, coordinates, agent and POI all arrive as structured
               JSON. Paging is capped at 9 pages (see ID_MAX_PAGE).

  /singapore   Singapore. Next.js App Router, data in RSC flight chunks
               plus a schema.org ItemList. No paging cap found.

They share a Cloudflare edge and nothing else, which is why the modes are
split by market and the parsers do not overlap.
"""

from __future__ import annotations

SITE_ROOT = "https://www.99.co"
ID_ROOT = f"{SITE_ROOT}/id"
SG_ROOT = f"{SITE_ROOT}/singapore"

# Recon 2026-09-21: plain `requests` is answered 403 by Cloudflare on every
# path. Under curl_cffi impersonation, chrome124/chrome131/firefox133/
# safari17_0 were served 200 -- but edge101 and chrome99_android drew
# "Just a moment" (HTTP 429, cf-mitigated: challenge) on the bare homepage,
# so they are deliberately NOT in the ladder: rotating onto a profile that is
# itself challenge-prone turns one bad request into two.
TLS_PROFILES = (
    "chrome124",
    "firefox133",
    "safari17_0",
    "chrome131",
)

# Cloudflare signals a managed challenge with this response header. It is the
# single most reliable block marker on this target -- far better than status,
# because the same challenge arrives as 403 on deep ID pages and as 429 on the
# homepage for a bad TLS profile.
CF_MITIGATED_HEADER = "cf-mitigated"
CF_CHALLENGE_VALUE = "challenge"

BLOCK_MARKERS = (
    "just a moment",
    "cf-mitigated",
    "challenges.cloudflare.com",
    "attention required",
    "enable javascript and cookies to continue",
)

# -- Indonesia ------------------------------------------------------------

# Pagination parameter. `hlmn` is short for "halaman" (page) and is the ONLY
# one that works: `page`, `p`, `offset` and `start` are all accepted with
# HTTP 200 and silently ignored, re-serving page 1 while pagination.page stays
# at 1 -- success-shaped nonsense that a naive scraper reads as real paging.
ID_PAGE_PARAM = "hlmn"

# THE structural limit on this target. hlmn >= 10 is answered with a
# Cloudflare managed challenge (HTTP 403, cf-mitigated: challenge) and NO TLS
# profile passes it -- verified across /id/jual/rumah and /id/sewa/rumah,
# and at depths 10, 11, 12, 15, 20, 30, 50, 100, 200, 300, 400, 450, 499.
# Pages 1-9 are served normally, so anonymous reach is ~9 x 31 = 279 listings
# per distinct query. Deeper inventory is reached by narrowing the query
# (location slug, price band, bedrooms) until each slice fits in 9 pages --
# see the fan-out helpers in modes.py. This is a product/anti-scraping
# decision, not a rate limit: a fresh session at hlmn=10 is challenged on its
# very first request, while hlmn=9 succeeds immediately afterwards.
ID_MAX_PAGE = 9

# pagination.page_size reports 20, but a page carries ~31 entries because the
# listings array interleaves "primary" (developer/project placements) and
# "secondary" (ordinary listings) groups. Both are emitted, tagged by
# groupType, so callers can filter placements out.
ID_TYPICAL_PER_PAGE = 31

ID_SEARCH_PREFIXES = ("jual", "sewa")
ID_DETAIL_PREFIX = "/id/properti/"

# Query parameters that genuinely reach the backend filter object. Verified by
# reading pageProps.data.filter back after the request and watching
# pagination.count move.
ID_FILTER_PARAMS = {
    "minPrice": "harga_min",
    "maxPrice": "harga_maks",
    "minBedrooms": "kamar_tidur_min",
    "propertyType": "tipe_properti",
    "sort": "urut",
}

# -- Singapore ------------------------------------------------------------

SG_PAGE_PARAM = "page_num"
SG_TYPICAL_PER_PAGE = 36

# Open JSON API on the main host. Unknown paths answer
# {"message": "path_not_found"} as clean JSON, which makes endpoint probing
# unambiguous -- there is no hollow-200 fallback here.
API_PREFIX = "/api/v10/web"
HDB_MEDIAN_PATH = f"{API_PREFIX}/hdb-resale-price/transactions/table/median"
API_NOT_FOUND_MARKER = "path_not_found"

# -- shared ---------------------------------------------------------------

DEFAULT_MAX_PAGES = 5
DEFAULT_TIMEOUT_SECS = 45
DEFAULT_MAX_RETRIES = 4
DEFAULT_CONCURRENCY = 3

# Cloudflare on this origin is markedly twitchier than on a plain SSR site.
# A small inter-request delay costs little against 1.5 MB page bodies and
# keeps a long run from looking like a burst.
DEFAULT_REQUEST_DELAY_SECS = 0.8
