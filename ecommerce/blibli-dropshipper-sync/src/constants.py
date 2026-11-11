"""Endpoints, TLS profiles and tuning constants for the Blibli sync actor.

WAF profile (recon 2026-09-01, see CRAWLING_METHOD.md)
-----------------------------------------------------
Cloudflare, `Referer` header mandatory, ladder leading with `safari17_0`
(Chrome fingerprints are blocked on some `/backend/search/*` paths and drew
403s during recon on the bulk endpoint too). Sustained traffic from one IP
draws intermittent 403s that clear on retry with a rotated fingerprint, so
the backoff in `client.py` is load-bearing and residential proxy is
recommended for scheduled syncs.

The one finding that shapes this whole actor
--------------------------------------------
`/backend/product/products/_basic` is a genuine **bulk** endpoint -- one
request resolves 100+ SKUs -- which is what makes syncing a large reseller
catalogue cheap. But it **silently omits some SKUs that are perfectly
live**. Verified: `VAM-43292-00654` returns `data: []` from `_basic` while
its product page shows a buyable product with stock 6, and search lists it
as `status: AVAILABLE, buyable: true`.

Treating an omission as "delisted" would therefore tell a dropshipper to
pull live products from their own store -- an actively damaging false
signal. Every SKU missing from the bulk response is re-checked against its
product page before this actor will report it as gone.
"""

ORIGIN = "https://www.blibli.com"

# Bulk lookup. `sku` accepts a comma-separated list (or repeated params).
BASIC_API = f"{ORIGIN}/backend/product/products/_basic"

# Product page. The slug segment is ignored by Blibli -- `/p/x/ps--<SKU>`
# resolves any product -- so a SKU alone is enough to reach the page, with
# no need to know or store the product's URL.
PRODUCT_PAGE = f"{ORIGIN}/p/x/ps--{{sku}}"
PRODUCT_STATE_VAR = "__PRODUCT_DETAIL_INITIAL_STATE__"
PRODUCT_SUMMARY_KEY = "productDetail.product/summary"

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

# 100 distinct SKUs resolved cleanly in one call; 50 is used by default to
# stay well inside that and to keep a single failed batch cheap to retry.
BATCH_SIZE = 50

# Key-value store holding the previous run's snapshot, so a run can report
# what actually changed rather than just restating current state.
STATE_STORE_NAME = "blibli-sync-state"
STATE_KEY = "SNAPSHOT"

# Change classifications emitted per SKU.
CHANGE_NEW = "NEW"
CHANGE_UNCHANGED = "UNCHANGED"
CHANGE_PRICE_UP = "PRICE_INCREASED"
CHANGE_PRICE_DOWN = "PRICE_DECREASED"
CHANGE_BACK_IN_STOCK = "BACK_IN_STOCK"
CHANGE_OUT_OF_STOCK = "OUT_OF_STOCK"
CHANGE_NAME_CHANGED = "NAME_CHANGED"
CHANGE_UNAVAILABLE = "BECAME_UNAVAILABLE"
CHANGE_RESTORED = "BECAME_AVAILABLE"

SYNC_OK = "OK"
SYNC_NOT_FOUND = "NOT_FOUND"
