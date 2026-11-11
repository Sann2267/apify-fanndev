"""Endpoints, locales and tuning constants for the noon.com scraper.

WHY THE ACTOR DOES NOT TALK TO www.noon.com
-------------------------------------------
Every Akamai-fronted noon host -- www.noon.com, api.noon.com, catalog.noon.com,
ksa/uae/now/sell.noon.com -- answers a 380-byte `AkamaiGHost` "Access Denied"
page (reference `#18.*`) to addresses outside noon's retail markets. During
recon that deny came back on ALL SIX TLS profiles in the house ladder
(chrome124/131/136, safari17_0, edge101, firefox133), on HTTP/1.1 as well as
HTTP/2, with and without a full Chrome header set, and -- the tell -- even for
`/robots.txt`. It arrives with `server-timing: cdn-cache; desc=HIT`, i.e. the
deny itself is cached at the edge. That is an edge ACL keyed on the client
network, not a JA3 gate and not a bot score, so no amount of fingerprint work
opens it.

`minutes.noon.com` (noon Minutes, the 15-minute grocery arm) is served by
Cloudflare instead of Akamai and is NOT part of that ACL. Its web app reaches
the main marketplace catalogue through a server-side proxy prefix,
`/_vs/nc/mp-customer-catalog-api/`, which is how this actor reads the full noon
marketplace. Behind that prefix there is no WAF at all: plain `requests` with
zero custom headers returns 200, every TLS profile passes, and 30 concurrent
requests completed 30/30 at ~8.8 req/s from an unproxied address.

The gateway is ALLOWLISTED, not open: only `mp-customer-catalog-api` routes.
`mp-reviews-api`, `mp-identity-api`, `mp-seller-api` and a nonsense service
name all return a bare 404. That is why this actor has no review-text mode --
see REVIEW TEXT below.

DECOYS -- endpoints that answer 200 without meaning it
------------------------------------------------------
1. Any unknown path that carries a `q=` parameter falls through to the search
   handler and returns a full, plausible search payload. `/api/u/suggest/?q=x`
   and `/api/u/zzz-not-real/?q=x` both return the same `nbHits` and the same
   `canonical_url` as `/api/u/search/?q=x`. There is NO autocomplete endpoint
   here; a "suggestions" mode built on that 200 would be inventing data. A path
   without `q=` 404s honestly, which is how the two were told apart.
2. `f[filter_attr_brand]=Apple` -- the key the facet payload appears to
   advertise -- is silently ignored: identical `nbHits`, identical first page,
   and the key is dropped from the echoed `canonical_url`. The filter that
   actually works is the top-level `brand=<code>` (echoed back in
   `search.brand`), which is what BRAND_PARAM below uses.

REVIEW TEXT
-----------
Not reachable. The PDP payload carries only the aggregate `product_rating`
(`{"count": N, "value": 4.5}`); individual review bodies live in a service the
`/_vs/nc/` allowlist does not route. `/api/u/reviews/<sku>/` 404s, and
`/api/u/review/<sku>/` returns 200 but is the slug catch-all again (breadcrumb
"Review", 1.6 KB, no reviews). The aggregate is emitted; review text is not,
and the actor does not pretend otherwise.
"""

from __future__ import annotations

# --- Hosts --------------------------------------------------------------
# S1: the Cloudflare-fronted Minutes host. Verified working from an address
# that Akamai denies, which is the whole point of routing through it.
GATEWAY_HOST = "https://minutes.noon.com"

# S2: the marketplace origin. The same proxy prefix exists here, but this host
# is inside the Akamai ACL, so it is only reachable from an allowed network
# (a residential proxy in AE/SA/EG, or a run that happens to exit there).
# UNVERIFIED from the recon address -- every request to it was denied at the
# edge, so S2 is a declared fallback, not a measured one. It is tried only
# after S1 fails, and records it emits are tagged so you can tell them apart.
ORIGIN_HOST = "https://www.noon.com"

# Main marketplace catalogue, proxied. Harvested from the Minutes bundle's
# `getNoonProducts`, which builds `/_vs/nc/mp-customer-catalog-api/api/u<path>/`.
MP_API_PREFIX = "/_vs/nc/mp-customer-catalog-api/api/u"

# noon Minutes' own catalogue (quick-commerce grocery). Different service,
# different response shape -- see parsers.extract_instant_products.
INSTANT_API_PREFIX = "/_svc/catalog"

# --- Locales ------------------------------------------------------------
# `x-locale` alone switches country, currency AND language; no cookie, no
# session, no geo-IP dependency. Verified: en-ae iPhone 4899, en-sa 5699,
# en-eg 58100, ar-ae returns Arabic titles at the AE price.
COUNTRIES = ("ae", "sa", "eg", "kw", "qa", "bh", "om")
LANGUAGES = ("en", "ar")

# The API returns bare numbers and NO currency field anywhere in the payload,
# so a price is meaningless without knowing which country asked. The actor
# derives it from the locale and stamps it on every priced record. This is the
# one place the actor adds a field upstream does not send; nothing is renamed.
CURRENCY_BY_COUNTRY = {
    "ae": "AED", "sa": "SAR", "eg": "EGP", "kw": "KWD",
    "qa": "QAR", "bh": "BHD", "om": "OMR",
}

# noon's own site path per locale, used to rebuild public product URLs.
SITE_PATH_BY_LOCALE = {
    ("ae", "en"): "uae-en", ("ae", "ar"): "uae-ar",
    ("sa", "en"): "saudi-en", ("sa", "ar"): "saudi-ar",
    ("eg", "en"): "egypt-en", ("eg", "ar"): "egypt-ar",
    ("kw", "en"): "kuwait-en", ("kw", "ar"): "kuwait-ar",
    ("qa", "en"): "qatar-en", ("qa", "ar"): "qatar-ar",
    ("bh", "en"): "bahrain-en", ("bh", "ar"): "bahrain-ar",
    ("om", "en"): "oman-en", ("om", "ar"): "oman-ar",
}

# --- Pagination ---------------------------------------------------------
# `limit` is honoured up to 200 and silently clamped there (limit=500 returned
# 201 hits and echoed `limit: 200`). 200 is therefore the default: it is 4x
# fewer round trips than the site's own 50.
MAX_LIMIT = 200
DEFAULT_LIMIT = 200

# `page` is clamped to 50 server-side: page=100 came back with the
# canonical_url rewritten to `page=50`. Past the real end the endpoint returns
# 200 with an EMPTY hits array rather than a 404, so an empty page -- not
# nbPages -- is the stop condition.
MAX_PAGE = 50

# nbHits is an approximate, sharded counter: the same query answered 1309,
# 1293, 1323 and 1301 across four consecutive calls. It is passed through for
# reference but never used to decide when to stop.

# --- Query grammar ------------------------------------------------------
BRAND_PARAM = "brand"          # the filter that actually bites; see DECOYS
SORT_BY_PARAM = "sort[by]"
SORT_DIR_PARAM = "sort[dir]"
PRICE_MIN_PARAM = "f[price][min]"
PRICE_MAX_PARAM = "f[price][max]"
SORT_FIELDS = ("popularity", "price", "new_arrivals", "discount", "rating")
SORT_DIRECTIONS = ("asc", "desc")

# --- HTTP tuning --------------------------------------------------------
# No WAF was found on this door, so the profile ladder exists only as insurance
# against a future edge rule; chrome131 is the default because it is what the
# recon matrix was measured on. All seven profiles returned byte-identical
# payloads.
TLS_PROFILES = ("chrome131", "chrome136", "chrome124", "safari17_0", "firefox133")

DEFAULT_TIMEOUT_SECS = 60
DEFAULT_MAX_RETRIES = 4
DEFAULT_REQUEST_DELAY_SECS = 0.0   # 8.8 req/s ran clean unproxied
DEFAULT_CONCURRENCY = 4
MAX_CONCURRENCY = 10

RETRY_STATUS = (408, 425, 429, 500, 502, 503, 504)
RATE_LIMIT_COOLDOWN_SECS = 20.0

# Body markers that mean "an edge refused us" even behind a 200/403.
BLOCK_MARKERS = (
    b"AkamaiGHost",
    b"Access Denied",
    b"errors.edgesuite.net",
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
)

# --- noon Minutes -------------------------------------------------------
# Minutes is warehouse-scoped: results depend on a delivery zone, not just a
# country. These are the Dubai defaults harvested from the live page; they are
# exposed as inputs so a run can target another zone.
INSTANT_DEFAULTS = {
    "x-lat": "251998495",
    "x-lng": "552715985",
    "x-ecom-zonecode": "AE_DXB-S14",
    "x-nooninstant-zonecode": "W00050759A",
}
