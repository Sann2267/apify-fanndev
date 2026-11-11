"""Endpoints, TLS profiles and tuning constants for the Blibli merchant scraper.

WAF profile (recon 2026-09-01, see CRAWLING_METHOD.md)
-----------------------------------------------------
`www.blibli.com` is behind **Cloudflare**: plain `httpx` gets a 403 with a
~248 KB HTML shell, and a `Referer` header is mandatory on every request.

**This actor differs from the other Blibli actors in one load-bearing way.**
The merchant-profile endpoint `/backend/search/merchant/{code}/info` is
blocked *per TLS fingerprint*, not merely by the generic Cloudflare rule:

| Profile | `/backend/search/merchant/{code}/info` | every other endpoint here |
| --- | --- | --- |
| `chrome124` | **403** (Cloudflare HTML) | 200 |
| `chrome131` | **403** | 200 |
| `safari17_0` | 200 | 200 |
| `firefox133` | 200 | 200 |
| `edge101` | 200 | 200 |
| `chrome99_android` | 200 | 200 |

`/backend/search/products` and `/backend/search/brand/{name}/info` are fine
on chrome124, so this is a rule targeting the merchant-profile path
specifically rather than a blanket `/backend/search/*` block. The ladder
below therefore leads with `safari17_0` -- the profile verified against all
five endpoints this actor uses. Leading with chrome124 would silently lose
the entire profile record while every other call kept working.
"""

ORIGIN = "https://www.blibli.com"

# Store profile: name, level, badge with its sub-ratings, respondTimeRating,
# province, pickup point (address/lat-long/business hours), activationDate.
MERCHANT_INFO_API = f"{ORIGIN}/backend/search/merchant/{{code}}/info"
# Follower count.
MERCHANT_FAVORITES_API = f"{ORIGIN}/backend/official/merchant-favorites/{{code}}"
# Store catalogue. Note the parameter is `merchant`, NOT `merchantCode`
# (which returns 422 here, while the review endpoint wants the opposite).
SEARCH_API = f"{ORIGIN}/backend/search/products"
# Rating histogram + Blibli's own review-topic counts for the whole store.
REVIEWS_API = f"{ORIGIN}/backend/product-review/public-reviews"
# The store's active voucher arsenal.
VOUCHERS_API = f"{ORIGIN}/backend/search/vouchers"

# safari17_0 first -- see the module docstring. chrome124/chrome131 are kept
# at the end only as last-resort rotation targets for the endpoints that do
# accept them; they can never serve the profile call.
TLS_PROFILE_LADDER = ("safari17_0", "firefox133", "edge101", "chrome99_android", "safari18_0")

BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.5
REQUEST_TIMEOUT = 45

# The catalogue search caps at 20 pages regardless of page size, so one
# query slice tops out at 800 products. Most stores fit well inside that
# (measured: 154, 187); large ones do not (adidas: 3,112).
SEARCH_PAGE_SIZE = 40
SEARCH_MAX_PAGES = 20

# Extra query slices used by `deep` catalogue coverage. Each opens its own
# 800-product window; the caller dedupes by SKU. Measured on a 3,112-product
# store: unfiltered 800, then +489 (cheapest), +437 (most expensive),
# +43 (best selling), then price bands added ~500 more -> 2,271 of 3,112.
CATALOG_SORTS = ("3", "4", "16")
PRICE_BANDS = (
    (0, 200_000),
    (200_000, 500_000),
    (500_000, 1_000_000),
    (1_000_000, 3_000_000),
    (3_000_000, 99_000_000),
)
