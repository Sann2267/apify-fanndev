"""Endpoints, TLS profiles and tuning constants for the Blibli promo extractor.

WAF profile (recon 2026-09-01, see CRAWLING_METHOD.md)
-----------------------------------------------------
Blibli fronts `www.blibli.com` with **Cloudflare** (`server: cloudflare`,
`cf-ray`, `__cf_bm`). Two independent gates were identified:

1. **TLS/JA3.** Plain `httpx` and un-impersonated `curl_cffi` both get a
   403 carrying a ~248 KB HTML shell. *Every* curl_cffi impersonation
   profile tested (chrome124 / chrome131 / safari17_0 / firefox133)
   returned 200, so the gate is the fingerprint itself, not a specific
   profile allowlist.
2. **`Referer` is mandatory.** With a good JA3 but no `Referer`, the same
   endpoints still 403. Dropping any *other* header (`Accept`,
   `Accept-Language`, every `Sec-Fetch-*`) still returns 200. `Referer`
   alone plus `Accept` is enough. This is the single decisive header, so
   it is never omitted anywhere in this actor.

No cookie, token, signature or login is required on any endpoint below.
"""

ORIGIN = "https://www.blibli.com"

# --- Mode 1: flash sale -------------------------------------------------
# Session windows currently on offer. Each carries an `id` of the form
# "<startEpochMs>-<endEpochMs>" which is the `schedule_id` the product
# endpoint expects.
FLASH_SALE_SCHEDULES_API = f"{ORIGIN}/backend/content-api/flashsale"
# The "new API" the site itself selects via `window._FLASHSALE_NEW_API`.
FLASH_SALE_PRODUCTS_API = f"{ORIGIN}/backend/content-api/flashsale/v2/products"

# --- Mode 2: promo campaign catalogue -----------------------------------
PROMOTIONS_API = f"{ORIGIN}/backend/content/promotions"

# --- Mode 3: discounted / promo-tagged products -------------------------
SEARCH_API = f"{ORIGIN}/backend/search/products"

# TLS impersonation ladder. chrome124 leads because it was the profile the
# whole recon ran on; the rest are rotated in on a block. chrome131 is
# deliberately *not* first -- it is widely blocklisted across other targets
# in this portfolio (see .ai/CLAUDE.md), even though Blibli accepts it.
# The first entry is the default; the client walks the rest on a block.
TLS_PROFILE_LADDER = ("chrome124", "safari17_0", "firefox133", "chrome131", "chrome99_android")

# `Referer` is injected per-request by the client -- it is load-bearing.
BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.5  # seconds; exponential -> 1.5, 3, 6, 12, 24
REQUEST_TIMEOUT = 45

# Flash sale serves 24 items/page. Past the last page it answers either an
# empty list or `404 FLASHSALE_PRODUCT_NOT_FOUND` depending on the sort;
# the client normalises both to an empty page (observed: 768 unique
# products over 32 pages, terminating at page 33).
# Hard ceiling so a schedule that never empties cannot loop forever.
FLASH_SALE_MAX_PAGES = 200

PROMOTIONS_PAGE_SIZE = 50

# The search backend refuses to serve past page 20 whatever the page size
# (`total_page` is capped at 20; page 21 returns an empty payload with
# `total_item: 0`). 40/page * 20 pages = 800 products per query, max.
SEARCH_PAGE_SIZE = 40
SEARCH_MAX_PAGES = 20

# Sort vocabularies, read from the live facet endpoints rather than guessed.
FLASH_SALE_SORTS = {
    "relevance": "6",
    "biggestDiscount": "1",
    "almostSoldOut": "2",
    "mostStockLeft": "3",
    "cheapest": "4",
    "mostExpensive": "5",
    "mostSearched": "7",
}

SEARCH_SORTS = {
    "relevance": "0",
    "bestSelling": "16",
    "cheapest": "3",
    "mostExpensive": "4",
    "newest": "5",
}

PROMOTION_SORTS = ("relevance", "popularity", "newest", "ending_soon")
