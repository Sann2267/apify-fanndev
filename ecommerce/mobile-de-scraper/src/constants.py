"""Endpoints, gate profile and the hard limits mobile.de enforces.

Everything here was established by probing the live site on 2026-09-22; the
reasoning behind each value is in `CRAWLING_METHOD.md`. The short version:

* mobile.de fronts every host with **Akamai Bot Manager** (`AkamaiGHost`,
  `_abck`). The gate is TLS-fingerprint-only. Plain `requests`/`httpx` get a
  7.7 KB "Zugriff verweigert" page; every `curl_cffi` impersonation profile
  tried got 200. There is no JS challenge to solve, no sensor to replay, no
  cookie to warm and no token to harvest -- see `client.py`.
* The gate is **host-scoped, not IP-scoped**. `m.mobile.de` and
  `suchen.mobile.de` answer 403 to the same request that `www.mobile.de`
  answers 200. The web app points its own API base at `m.mobile.de`; this
  actor deliberately uses the `www.mobile.de` mirror of the same service,
  which is the whole reason it works without a German proxy.
"""

from __future__ import annotations

SITE_ROOT = "https://www.mobile.de"

# The consumer API the mobile.de React app talks to. The app's own
# window.__PUBLIC_CONFIG__ sets apiBaseUrl to https://m.mobile.de/consumer/api,
# but that host is 403 from outside Germany while this www mirror is not.
API_ROOT = "https://www.mobile.de/consumer/api"

# Search/detail URLs are resolved by the API against suchen.mobile.de, so the
# `url` parameter is always sent as a ROOT-RELATIVE PATH. Passing an absolute
# https://www.mobile.de/... URL returns 400 "SVC API request failed".
PAGE_URL_BASE = "https://suchen.mobile.de"

# Akamai's allowlist here is broad -- all seven profiles tried returned 200 on
# a cold connection. Ordered newest-first; the client rotates through them only
# if one starts being refused, which recon never triggered.
TLS_PROFILES = (
    "chrome136",
    "chrome131",
    "chrome124",
    "edge101",
    "firefox133",
    "safari17_0",
)

# --- Hard server limits -----------------------------------------------------

# `psz` (page size) is honoured up to at least 200 organic rows per request.
# Above that mobile.de was not probed; 200 is used as the safe ceiling.
MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 200

# `ps` (page start) is a TRUE item offset and the only reliable way to
# paginate -- see parsers/modes. Offset 1900 is the last that returns rows;
# 1901 and beyond return an empty item list (while still claiming
# hasNextPage: true). So one distinct query yields ~2000 listings, no matter
# that numResultsTotal reports 1.5 million. Going deeper needs the query to be
# SLICED (narrower price band, year, model, radius), not paged further.
MAX_OFFSET = 1900
MAX_RESULTS_PER_QUERY = MAX_OFFSET + MAX_PAGE_SIZE

# mobile.de's own VEHICLE_CATEGORY enum, lifted from the client bundle.
# An unrecognised value is NOT rejected: the server silently falls back to
# Car, so "Van" or "Truck" return the full 1.5M car count and look like they
# worked. Validated against this tuple before a request is ever sent.
VEHICLE_CATEGORIES = (
    "Car",
    "Motorbike",
    "Motorhome",
    "EBike",
    "VanUpTo7500",
    "TruckOver7500",
    "SemiTrailerTruck",
    "SemiTrailer",
    "Trailer",
    "Bus",
    "ConstructionMachine",
    "AgriculturalVehicle",
    "ForkliftTruck",
)

# --- Filter parameters ------------------------------------------------------

# mobile.de's short filter codes, lifted from SEARCH_FILTERS in the bundle.
# The API accepts ONLY these; the legacy `makeModelVariant1.makeId=` shape
# that older scrapers and many blog posts still use is silently DROPPED,
# returning the unfiltered 1.5M-row result set while looking perfectly fine.
FILTER_PARAMS = frozenset(
    """ab ao asl av ax bat bc bcw bds bgt blt bm bp bsf bu bw c cc cd cht chtf
    clim cn cnc cnv con cy dam dc dlt dm doc door drl dt ecol el emc ems eu fe
    fe! fh fin fm fr fs ft ftv gi hght hi hlt ht htg ic icol ih id! it lcp le
    lh lic ll ls lsc lscd lsdt lsft lsml lsrt lst lstm lt lw ml mnw mpr ms ms!
    nog np nsr nw od oh p pa ps psz pvo pw q rad rd re ref refId rtd s sb sbs
    sc sfmr sh sid sid! sld spc sr st sth subc tct tlb tlu tr ucs ucsa vat vc
    wb wdth wf ws yc z""".split()
)

# Legacy parameters that mobile.de accepts syntactically and then ignores.
# Their presence in a user-pasted URL is a silent correctness bug, so the
# actor detects them and says so rather than returning 1.5M unfiltered cars.
DECOY_PARAMS = frozenset(
    {
        "makeModelVariant1.makeId",
        "makeModelVariant1.modelId",
        "makeModelVariant2.makeId",
        "makeModelVariant2.modelId",
        "makeModelVariantExclusions1.makeId",
        "scopeId",
        "isSearchRequest",
        "damageUnrepaired",
        "pageNumber",
    }
)

SORT_BY = {
    "relevance": "rel",
    "price": "p",
    "mileage": "ml",
    "firstRegistration": "fr",
    "power": "pw",
    "age": "doc",
    "newestFirst": "doc",
    "distance": "dist",
}

SELLER_TYPES = {"dealer": "DEALER", "private": "FSBO"}

# --- Pacing -----------------------------------------------------------------

DEFAULT_TIMEOUT_SECS = 45
DEFAULT_MAX_RETRIES = 4
DEFAULT_REQUEST_DELAY_SECS = 0.4

# Recon never saw a 429 on this API. Treated as precautionary: a volume limit
# is not fingerprint-shaped, so sit still rather than rotate the TLS profile.
RATE_LIMIT_COOLDOWN_SECS = 30.0
