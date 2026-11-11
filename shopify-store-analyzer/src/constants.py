"""Endpoints, detection markers and knobs for the Shopify Store Analyzer.

Recon notes (2026-09-15) that justify the values below:

* Shopify storefronts expose a public, unauthenticated JSON surface. There is NO
  anti-bot layer: plain `requests` with the DEFAULT Python user-agent returns 200
  on /products.json, and every curl_cffi profile tried (chrome99_android,
  chrome124, chrome131, chrome136, safari17_0, edge101, firefox133) returned an
  identical 200. The TLS profile is not load-bearing.
* /products.json is served strictly in `published_at` DESCENDING order. Verified
  across 5 stores / 7,443 products with zero out-of-order pairs. This is what
  makes the new-products mode cheap: stop paginating once the cutoff is passed.
* `sort_by`, `order` and `since_id` are SILENTLY IGNORED on /products.json --
  they return a plausible 200 with unchanged results. Never rely on them.
"""

# --- TLS ---------------------------------------------------------------------
# Not load-bearing (see module docstring). Pinned for portfolio consistency.
TLS_PROFILE = "chrome124"

# --- Endpoint paths (appended to a resolved store origin) --------------------
PATH_PRODUCTS = "/products.json"
PATH_COLLECTIONS = "/collections.json"
PATH_META = "/meta.json"

# Shopify caps page size at 250 and silently clamps anything larger.
PRODUCTS_PAGE_SIZE = 250
COLLECTIONS_PAGE_SIZE = 250

# Hard stop so a pathological store cannot spin forever.
MAX_PAGES = 200

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# --- Platform detection ------------------------------------------------------
# `powered-by: Shopify` is definitive. Hydrogen/Oxygen in the same header means a
# headless storefront: the Liquid theme is gone, but the Shopify backend (and
# usually the .myshopify.com domain) still serves /products.json.
POWERED_BY_HEADER = "powered-by"
HEADLESS_MARKERS = ("hydrogen", "oxygen")

# Body markers, counted to give a confidence signal. A custom frontend that only
# proxies Shopify images scores low (bombas: 6); a real storefront scores high
# (kith: 3000+).
BODY_MARKERS = (
    "Shopify.theme",
    "cdn.shopify.com",
    "/cdn/shop/",
    "Shopify.shop",
    "ShopifyAnalytics",
    "myshopify.com",
)

# --- Retry policy ------------------------------------------------------------
MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.0          # exponential: 1 / 2 / 4 / 8 s
REQUEST_TIMEOUT = 45

# --- Change detection --------------------------------------------------------
# Named key-value store holding the previous run's catalogue fingerprint, so the
# `changes` mode can diff without re-reading the whole dataset.
SNAPSHOT_STORE_NAME = "shopify-store-snapshots"
