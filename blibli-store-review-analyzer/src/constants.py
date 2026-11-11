"""Endpoints, TLS profiles and tuning constants for the Blibli review scraper.

WAF profile (recon 2026-09-01, see CRAWLING_METHOD.md)
-----------------------------------------------------
`www.blibli.com` is behind **Cloudflare**, gated on two things that were
re-confirmed against the review endpoint specifically:

1. **TLS/JA3** — plain `httpx` gets a 403 with a ~248 KB HTML shell; every
   `curl_cffi` impersonation profile gets 200.
2. **`Referer` is mandatory** — with a valid JA3 but no `Referer`, the
   review endpoint still 403s. It is therefore sent on every request.

No cookie, token or login is needed. Only publicly visible reviews are
returned: Blibli's own UI states "only public reviews appear here", and
reviewer names arrive pre-masked by Blibli (`M***a`) — this actor never
attempts to unmask them.
"""

ORIGIN = "https://www.blibli.com"

# The review list. Found in the lazily-loaded product-detail chunk
# `js/ProductReviews.<hash>.js`, not in the site-wide API map -- the map only
# carries `/backend/product-review/reviews/_summary`, and the similarly named
# `/backend/product-review/reviews` is a different (empty) endpoint that
# returns a valid-looking `{"data":[],"paging":{...}}` for any input, which
# is an easy trap to mistake for "this product has no reviews".
REVIEWS_API = f"{ORIGIN}/backend/product-review/public-reviews"

# Used to enumerate a store's catalogue and to resolve a merchant's display
# name -- there is no public merchant-metadata endpoint (every candidate
# path returns the HTML app shell).
SEARCH_API = f"{ORIGIN}/backend/search/products"

# The three identifier kinds the review endpoint accepts, taken from the
# chunk's own `typeCode` map rather than guessed.
TYPE_MERCHANT = "merchantCode"
TYPE_PRODUCT = "productSku"
TYPE_BRAND = "principalBrandCode"

TLS_PROFILE_LADDER = ("chrome124", "safari17_0", "firefox133", "chrome131", "chrome99_android")

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

# 30 is the largest page size the endpoint honours -- 32 and above return an
# empty body with no paging envelope at all (verified 30 ok, 32/34/35/36/38/
# 39/40 all empty).
REVIEW_PAGE_SIZE = 30
# The server reports `total_page: 20` but will still serve page 21, and from
# page 22 it *repeats earlier reviews rather than returning an empty list*.
# Paging therefore has to stop on "no new IDs", never on "empty page" alone,
# or the walk never terminates. 25 is a hard backstop.
REVIEW_MAX_PAGES = 25

# Each distinct query exposes its own ~600-review window (30 x 20). Slicing
# the same target by rating and by topic opens additional windows, which is
# how this actor gets past the cap -- see `coverage` in the input schema.
# Ascending on purpose: when `maxReviewsPerTarget` cuts a run short, the
# low-star slices must already have been swept. Complaint analysis is the
# main job of this actor, and 1-2 star reviews are the scarce, valuable
# ones -- sweeping 5-star first would spend the whole budget on praise.
RATINGS = ("1", "2", "3", "4", "5")
TOPICS = ("QUALITY", "PRICE", "SHIPMENT", "PACKAGING", "SERVICE", "ORIGINALITY", "GENERIC")

# Blibli's own labels for the topic codes, carried through to the output so
# a consumer does not have to hardcode the translation.
TOPIC_LABELS = {
    "QUALITY": "Product quality",
    "PRICE": "Value for money",
    "SHIPMENT": "Shipping",
    "PACKAGING": "Product packaging",
    "SERVICE": "Seller service",
    "ORIGINALITY": "Product authenticity",
    "GENERIC": "Other",
}

SORT_OPTIONS = ("POPULAR", "LATEST", "OLDEST", "HIGHEST", "LOWEST")

SEARCH_PAGE_SIZE = 40
SEARCH_MAX_PAGES = 20
