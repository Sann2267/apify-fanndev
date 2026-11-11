"""Target constants and recon-derived facts for the Yellow Pages Indonesia actor.

Everything here is a *measured* property of the target (2026-09-20 recon), not a
guess. Each constant carries the observation that produced it so a future
maintainer can re-verify it instead of re-discovering it.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Hosts
# --------------------------------------------------------------------------
# www.yellowpages.id and www.yoys.id are the SAME Django application serving the
# SAME Indonesian dataset (YP Media Ltd white-label). Verified by fetching
# identical product/company IDs on both hosts: /product-DryMassage-_52399.html
# resolves to company 492034 on both, byte-comparable apart from brand strings.
#
# BUT: yellowpages.id puts a Cloudflare *Managed Challenge* on exactly the three
# paths that carry the directory data:
#       /profil-*        403 cf-mitigated: challenge
#       /places/*        403 cf-mitigated: challenge
#       /listing/*       403 cf-mitigated: challenge
# while /, /product-*, /citymap-* stay open. All 18 curl_cffi TLS profiles
# (chrome99_android..chrome136, safari15_5..18_0, edge99/101, firefox133/135)
# return the identical 403, and a homepage warm-up issues no clearance cookie —
# so this is a path-scoped WAF *rule*, not a JA3 gate, and is not solvable
# HTTP-only. yoys.id serves the same rows with no challenge at all.
#
# Therefore: yoys.id is the data host, yellowpages.id is the canonical host we
# mirror back into every record's `yellowpagesUrl`.
DATA_HOST = "https://www.yoys.id"
CANONICAL_HOST = "https://www.yellowpages.id"

# Ordered failover. If the primary ever acquires the same Cloudflare rule the
# client walks this list before giving up.
HOST_LADDER = (DATA_HOST, CANONICAL_HOST)

COUNTRY = "ID"

# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
SEARCH_PATH = "/listing/places/"       # business search  (ctr, q, adm, cty, p)
PRODUCT_SEARCH_PATH = "/listing/products/"  # product search   (ctr, q, p)
CATEGORY_PATH = "/places/{slug}"       # category landing (+ /{City} suffix)
PROFILE_PATH = "/profil-{id}-{slug}.html"
CITYMAP_PATH = "/citymap-ID-{code}/"
CITYMAP_CITY_PATH = "/citymap-ID-{code}-{city}/"

# --------------------------------------------------------------------------
# Pagination — measured ceilings
# --------------------------------------------------------------------------
# GOTCHA 1: `page=N` is accepted and SILENTLY IGNORED — page=1..4 return the
#           byte-identical document. The real parameter is `p`.
PAGE_PARAM = "p"

# GOTCHA 2: the result header advertises "10000 hasil", but the backend only
#           serves p=1..10. p=11 returns HTTP *200* with zero result cards — a
#           silent empty page, not a 404. (A 404 only appears past p>=30.)
#           So the stop condition MUST be content-based, never status-based.
#           Measured identical for q=bank, q=hotel and q=bank&adm=bali.
MAX_PAGE = 10
PAGE_SIZE = 25
MAX_RECORDS_PER_QUERY = MAX_PAGE * PAGE_SIZE  # 250

# GOTCHA 3: the visible `l=` free-text location box is a DECOY — every value
#           tried (Jakarta, DKI Jakarta, Kota Medan, Bandung, Cimahi, Aceh)
#           returned 0 results while the page title happily echoed the place
#           name. Real geo filtering uses the facet params below, which were
#           harvested from the sidebar's ahrefClick() handlers.
REGION_PARAM = "adm"   # e.g. adm=jawa+barat
CITY_PARAM = "cty"     # e.g. cty=bandung
DECOY_LOCATION_PARAM = "l"

# --------------------------------------------------------------------------
# TLS
# --------------------------------------------------------------------------
# yoys.id sits behind Cloudflare but applies no challenge, so any profile works.
# chrome124 is the primary because it is the most common real-world JA3 in the
# 2026 fleet; the ladder exists purely as insurance if the zone ever tightens.
TLS_PROFILE = "chrome124"
TLS_LADDER = ("chrome124", "firefox133", "safari17_0", "chrome131", "edge101")

BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# --------------------------------------------------------------------------
# Retry / concurrency
# --------------------------------------------------------------------------
MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.6      # exponential: 1.6, 2.56, 4.1, 6.55 s (+ jitter)
REQUEST_TIMEOUT = 45
DEFAULT_CONCURRENCY = 4

# Cloudflare challenge markers, used to detect a zone tightening mid-run.
CHALLENGE_MARKERS = ("Just a moment...", "challenge-platform", "__cf_chl", "cf_chl_opt")

# --------------------------------------------------------------------------
# Province codes used by /citymap-ID-{code}/
# --------------------------------------------------------------------------
# MEASURED, not assumed. The site does NOT use Indonesia's official BPS
# numbering — it has its own sequence, so every code below was read back from
# the live page title ("Browse the directory in <name>") on 2026-09-20.
#
# GOTCHA: an unused code answers 200 with a fully rendered page titled
# "Aceh" and zero cities — a hollow 200, not a 404. Codes 06, 09, 16, 19, 20,
# 23, 25, 27 and everything from 43 up behave this way. Only the keys below are
# real; the geo_directory mode flags anything else as a hollow response.
PROVINCE_CODES = {
    "01": "Aceh", "02": "Bali", "03": "Bengkulu", "04": "Jakarta",
    "05": "Jambi", "07": "Central Java", "08": "East Java", "10": "Yogyakarta",
    "11": "West Kalimantan", "12": "South Kalimantan", "13": "Central Kalimantan",
    "14": "East Kalimantan", "15": "Lampung", "17": "West Nusa Tenggara",
    "18": "East Nusa Tenggara", "21": "Central Sulawesi", "22": "Southeast Sulawesi",
    "24": "West Sumatra", "26": "North Sumatra", "28": "Maluku",
    "29": "North Maluku", "30": "West Java", "31": "North Sulawesi",
    "32": "South Sumatra", "33": "Banten", "34": "Gorontalo",
    "35": "Bangka-Belitung Islands", "36": "Papua", "37": "Riau",
    "38": "South Sulawesi", "39": "West Papua", "40": "Riau Islands",
    "41": "West Sulawesi", "42": "North Kalimantan",
}

RECORD_BUSINESS = "BUSINESS"
RECORD_COMPANY = "COMPANY"
RECORD_PRODUCT = "PRODUCT"
RECORD_INSIGHT = "MARKET_INSIGHT"
RECORD_GEO = "GEO_NODE"
RECORD_ERROR = "ERROR"
