"""Endpoints, the gate, and every limit recon actually measured.

THE GATE
--------
Alfagift has **no WAF**. Every TLS profile in this portfolio's ladder
(chrome124/131, chrome99_android, safari17_0, edge101, firefox133) gets HTTP 200
from alfagift.id, and plain `httpx` over HTTP/1.1 reaches the same backend as
`curl_cffi` over HTTP/2. There is no Cloudflare, DataDome or PerimeterX in the
path and no IP gate: a bare datacentre address is served normally.

What looks like a gate is an application header. Every request to
`webcommerce-gw.alfagift.id` answers

    {"code":"401","message":"Unauthorized","trxId":"","token":"","errorFields":[]}

until a `fingerprint` header is supplied. This is NOT a login: the login
endpoint itself (`/v1/account/member/login`) returns the same 401 without it,
which is what gives the mechanism away -- a real auth gate cannot gate its own
front door.

The Nuxt bundle builds the header like this (deobfuscated from
`/_nuxt/d907afd.js`, and the passphrase is repeated verbatim in the app's
injected `env` object):

    passphrase = "m4p1-W3bc0mm-4lf@giFt-3ncRyp-022"   # 32 bytes -> AES-256
    iv         = "m4p1-4lf@giFt-1v"                   # 16 bytes
    fingerprint = Base64(AES-256-CBC(FingerprintJS visitorId, passphrase, iv))

The server only checks that the value **decrypts under that key**. It never
validates that the plaintext is a visitorId any real browser produced, never
ties it to a session, and never expires it -- so this actor mints its own
random plaintext per run and needs no browser, no FingerprintJS, and no login.
See `crypto.py`.

The CORS preflight confirms the full contract and nothing more:

    access-control-allow-headers: devicetype, devicemodel, latitude,
                                  longitude, trxid, fingerprint, authorization

`authorization` is only ever populated for a logged-in member. Everything this
actor reads is anonymous.

WHAT IS CLOSED
--------------
`/v2/stores/*` (store locator, nearest store, coordinate validation), the whole
cart, checkout, order-history and account surface stay 401 with a valid
fingerprint -- those need a real member bearer token. They are out of scope on
purpose: this is a public-data actor.

MEASURED LIMITS (recon 2026-09-21)
----------------------------------
* `start` is a **0-based PAGE INDEX, not an item offset**. start=1&limit=50 is
  rows 50-99, not rows 1-50. Getting this wrong silently duplicates page 0.
* There is **no page-size cap**. limit=5000 on a 2072-product category returned
  all 2072 rows in one 2 MB response in 0.3s. Whole categories and whole
  keyword result sets fit in a single request, so this actor defaults to one
  big page instead of walking.
* Walking past the last page returns HTTP 200 with `products: []` and
  `currentPage` reset to 0 -- a silent empty, never a 404. That is the stop
  condition.
* No rate limiting observed: 20 back-to-back requests in 1.3s, all 200. The
  app redirects to /too-many-request on 429, so a limit exists somewhere, but
  recon never reached it. Pacing defaults stay gentle anyway.
* `sortDirection` on the category endpoint is a **decoy**. '', 'asc', 'desc',
  '1', 'priceAsc' and 'nameAsc' all return byte-identical ordering. It is sent
  for contract fidelity and nothing else.
* Latitude/longitude headers are decoys for anonymous callers. Jakarta,
  Medan and Jayapura all return identical prices; Alfagift publishes one
  national price list (seller SAT) until a member picks a store.
"""

from __future__ import annotations

SITE_ROOT = "https://alfagift.id"
API_ROOT = "https://webcommerce-gw.alfagift.id"

# From the app's own injected env. If Alfagift ever rotates these, every
# endpoint returns 401 again and the key has to be re-harvested from the
# current /_nuxt/*.js bundle -- grep it for "m4p1-" or "passphrase".
GATE_PASSPHRASE = b"m4p1-W3bc0mm-4lf@giFt-3ncRyp-022"
GATE_IV = b"m4p1-4lf@giFt-1v"

# Alfagift is not fingerprint-gated at the TLS layer, so this is a single
# profile rather than a ladder. chrome131 matches the Chrome the site's own
# bundle targets; the ladder is kept only as rotation fodder for transport
# errors, not because any of it is needed to get a 200.
TLS_PROFILES = ("chrome131", "chrome124", "safari17_0", "edge101")

# -- endpoint templates (verbatim from the bundle's API constants module) ---

EP_CATEGORIES = "/v2/categories"
EP_CATEGORY_PRODUCTS = "/v2/products/category/{category_id}"
EP_SEARCH = "/v2/products/searches"
EP_SUGGESTIONS = "/v2/products/suggestions"
EP_PRODUCT_DETAIL = "/v2/products/{product_id}"
EP_BRANDS = "/v2/brands"
EP_BRAND_PRODUCTS = "/v2/products/brand/{brand_id}"
EP_NEW_PRODUCTS = "/v2/products/newproduct"
EP_RECOMMENDATIONS = "/v2/products/recommendations"
EP_BANNERS = "/v1/cms/banner/{location}"
EP_PROMO_DETAIL = "/v1/cms/banner/promotions/{promotion_id}"
EP_PROMO_PRODUCTS = "/v2/products/promotions/{promotion_id}"

# The only banner location the web app ever asks for. Other location strings
# return HTTP 200 with `banners: []` rather than an error, so an unknown
# location looks exactly like an empty one -- hence the default.
DEFAULT_BANNER_LOCATION = "main_banner_new"

# -- server-side ceilings, measured not guessed -----------------------------

# /v2/products/newproduct tops out at 198 rows however large `limit` is.
NEW_PRODUCTS_CEILING = 198
# /v2/products/recommendations tops out at 48.
RECOMMENDATIONS_CEILING = 48
# /v2/brands returns at most 300 brands per alphabet letter. No letter reached
# it during recon (S was highest at 295), but M=265 and S=295 are close enough
# that a catalogue expansion would silently truncate, so the actor warns.
BRANDS_PER_LETTER_CEILING = 300

# `alphabet` is a single character. Digits return an empty list; '' and '#'
# both return the same 300-row unfiltered slab, which is a truncated view of
# the whole brand table rather than a useful "all brands" call.
BRAND_ALPHABET = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# Five letters are permanently broken upstream, not rate limited: they answer
# HTTP 500 `solr.brands.error` on every attempt, with backoff, from every IP
# and TLS profile tried. Alfagift's brand Solr core has bad data behind these
# prefixes. They are listed so the actor can say "known upstream fault"
# instead of burning retries and reporting a scraper bug.
BRAND_LETTERS_UPSTREAM_BROKEN = frozenset({"C", "F", "G", "V", "W"})

# One page big enough that every surface recon measured fits in a single
# request. The largest top-level category is 2072 products.
DEFAULT_PAGE_SIZE = 1000
MAX_PAGE_SIZE = 5000

DEFAULT_MAX_RETRIES = 4
DEFAULT_TIMEOUT_SECS = 90
DEFAULT_REQUEST_DELAY_SECS = 0.2
