"""Endpoints, params, headers -- all in one place.

Recon summary (2026-09-08): lelang.go.id is the official e-auction portal
of DJKN (Direktorat Jenderal Kekayaan Negara, Ministry of Finance,
Republic of Indonesia). The page itself is a Vite/React SPA whose HTML is
only ~2 KB and contains **zero** trace of an API path -- everything is
fetched client-side from an undocumented REST API at
`api.lelang.go.id/api`.

How the API was found (worth recording, because guessing failed): the
SPA's single JS bundle (`/assets/index-<hash>.js`, ~7.5 MB) carries a
plain config object literal

    const Pa = { BASE_API:"https://api-auth.lelang.go.id/api",
                 LARAVEL_API:"https://api.lelang.go.id/api",
                 PERMOHONAN_API:"https://api.lelang.go.id/api", ... }

and a service map that pairs each `path` with one of those hosts. The
paths listed in the bundle (`/v1/landing-page/...`) are **relative to a
host that already ends in `/api`** -- so the first two direct guesses
(`api.lelang.go.id/v1/...`) returned 404 even though the path was right.
Host + path must be joined from the config object, never guessed.

WAF: none. Every endpoint below returns a clean JSON 200 to a plain
request -- no TLS impersonation, no Origin/Referer, no cookie, no warmup
(verified against 4 client profiles incl. a bare `requests`-style call).
`curl_cffi` is still used per portfolio convention and for robustness.

Auth: none for any endpoint used here. Endpoints under `/v1/permohonan/*`
(bidding, applications) DO require a signed-in session and are out of
scope per this project's "No Login" constraint -- not wired up.
"""

TLS_PROFILE = "chrome124"

# Host + "/api" prefix are both part of the base -- see module docstring.
BASE_URL = "https://api.lelang.go.id/api/v1"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://lelang.go.id",
    "Referer": "https://lelang.go.id/",
}

# --- endpoints (from the bundle's own service map) ---------------------
EP_CATALOG = "/landing-page/katalog-lot-lelang"
EP_CATALOG_KPKNL = "/landing-page-kpknl/{kpknl_id}/katalog-lot-lelang"
EP_CATALOG_UMKM = "/landing-page-umkm/katalog-lot-lelang"
EP_DETAIL = "/landing-page/info/{lot_id}"
EP_CATEGORIES = "/landing-page/kategori"
EP_OFFICES = "/landing-page/kpknl"
EP_FEED = {
    "hot": "/landing-page/hot-lelang",
    "ending-soon": "/landing-page/lelang-segera-berakhir",
    "live": "/landing-page/lelang-saat-ini",
}
FEED_VALUES = list(EP_FEED)

MODES = ["catalog", "detail", "kpknl", "feed", "reference"]

# --- query params ------------------------------------------------------
# VERIFIED WORKING (each changed totalItem when applied, 2026-09-08):
#   page, limit          -- pagination; totalItem/totalPage are returned
#   search=<text>        -- free-text ("toyota" -> 40 of 11,889 lots)
#   namakategori[]=<x>   -- category filter, REPEATABLE for multi-select
#                           ("Rumah" -> 7,671; "Rumah"+"Mobil" -> 7,800)
#
# SILENTLY IGNORED -- these return a plausible 200 with the FULL unfiltered
# result set (totalItem unchanged at 11,889), which is exactly the trap this
# portfolio hit on Blibli: an ignored param looks like a working one.
# Do not offer them as inputs:
#   katakunci, nama, keyword, namaLotLelang  (all wrong names for `search`;
#       `katakunci` is the frontend's *form field* name, not the API's)
#   provinsi, kota                            (geo filtering is NOT a catalog
#       param -- it is done by scoping to a KPKNL office instead, which is
#       why this actor has a dedicated `kpknl` mode)
#   sortby, sortdir, dcp
#
# HARD ERROR (not ignored): `namakategori=Rumah` without the `[]` suffix
# returns HTTP 400 -- the array syntax is mandatory.
PARAM_SEARCH = "search"
PARAM_CATEGORY = "namakategori[]"

# The 18 categories served by /landing-page/kategori on 2026-09-08. Kept as
# a static list only to populate the input schema's dropdown; the `reference`
# mode always fetches the live list rather than trusting this copy.
CATEGORIES = [
    "Tanah", "Rumah", "Ruko", "Pabrik", "Hotel dan Villa", "Mobil", "Motor",
    "Bongkaran", "Kapal", "Besi Tua", "Elektronik", "Kayu", "Inventaris",
    "UMKM", "Gudang", "Toko", "Apartemen", "Lain-lain",
]

# No page-size cap was found: limit=12/50/100/200/500 all returned exactly
# that many rows with `perPage` echoed back and `totalPage` recomputed
# (11,889 lots -> 991/238/119/60/24 pages). 200 is used as the paging step --
# a balance between request count and per-response payload size, not a limit.
PAGE_SIZE = 200

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
