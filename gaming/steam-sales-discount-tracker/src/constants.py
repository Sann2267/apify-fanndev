"""Endpoints, headers, TLS profiles, rate limits and retry policy.

WAF profile (recon 2026-10-11): NONE. store.steampowered.com, api.steampowered.com
and partner.steamgames.com answer 200 to every TLS profile and to plain
python-requests. The only gate is a per-IP RATE LIMIT on /search/results/:
HTTP 429 + an HTML "You've made too many requests recently" page after ~40
rapid calls; it clears in ~20 s. A 2.5 s pace held 70/70 calls with no 429, so
the search host is driven through a token bucket (burst 20, 1 call / 2.5 s).
appdetails / featuredcategories / GetItems were never limited at these volumes.

curl_cffi chrome124 is the profile recon ran on. Impersonation is insurance:
if a rule ever appears, the client already rotates TLS profile + exit IP.
"""

from __future__ import annotations

STORE = "https://store.steampowered.com"
STEAM_API = "https://api.steampowered.com"
PARTNER = "https://partner.steamgames.com"

URL_SEARCH = f"{STORE}/search/results/"
URL_FEATURED_CATEGORIES = f"{STORE}/api/featuredcategories"
URL_APPDETAILS = f"{STORE}/api/appdetails"
URL_STORE_SEARCH = f"{STORE}/api/storesearch/"
URL_POPULAR_TAGS = f"{STORE}/tagdata/populartags/english"
URL_SALE_PAGE = f"{STORE}/sale/"
# Official keyless Steam Web API. The ONLY bulk source of discount end dates,
# deal labels and package/bundle prices. Note: api.steampowered.com/robots.txt
# is "Disallow: /" (aimed at crawlers); this is Valve's documented developer API,
# called once per 100 items, and every mode can run without it
# (includeDiscountDetails=false).
URL_STORE_ITEMS = f"{STEAM_API}/IStoreBrowseService/GetItems/v1/"
URL_EVENT_CALENDAR = f"{PARTNER}/doc/marketing/upcoming_events"
URL_ECB_FX = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"

SEARCH_HOST = "store.steampowered.com/search/"
# /search/results/ hard-caps count at 100 (count=200 -> 100 rows).
SEARCH_PAGE_SIZE = 100
# A walk counts as complete (ended-deal detection allowed) at >= 99.8% of
# total_count unique items; total_count itself drifts by 1-2 during a walk.
COMPLETE_COVERAGE = 0.998
SEARCH_BUCKET_CAPACITY = 20
SEARCH_REFILL_SECS = 2.5
# Measured lockout after a 429 is ~20 s; without a proxy we must wait it out.
RATE_LIMIT_COOLDOWN_SECS = 25.0

STORE_ITEMS_BATCH = 100   # GetItems: 250 max per GET; 100 keeps the URL short
APPDETAILS_BATCH = 100    # appdetails + filters=price_overview: 100 ids verified

# Search filter values Steam actually honours. Unknown sort_by / category1
# values are SILENTLY IGNORED (return the default 9,462 list), so we validate.
SORT_BY = {
    "relevance": None,
    "priceAsc": "Price_ASC",
    "priceDesc": "Price_DESC",
    "releasedDesc": "Released_DESC",
    "nameAsc": "Name_ASC",
    # Reviews_DESC drops unreviewed items: total shrinks 9,462 -> 5,107.
    "reviewsDesc": "Reviews_DESC",
}
CATEGORY1 = {"all": None, "games": "998", "dlc": "21", "software": "994", "soundtracks": "990"}

# EStoreAppType codes returned in GetItems `type`.
STORE_APP_TYPES = {
    0: "game", 1: "demo", 2: "mod", 3: "movie", 4: "dlc", 5: "guide", 6: "software",
    7: "video", 8: "series", 9: "episode", 10: "hardware", 11: "music", 12: "beta",
    13: "tool", 14: "advertising",
}
ITEM_TYPES = {0: "app", 1: "package", 2: "bundle"}

# appdetails silently falls back to USD for an unknown cc and search returns 0,
# so the country is validated against ISO 3166-1 alpha-2 up front.
ISO_COUNTRIES = set(
    "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ "
    "CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR "
    "GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO "
    "JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR "
    "MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO "
    "RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV "
    "TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF YE YT ZA ZM ZW".split()
)

TLS_PROFILES = ["chrome124", "safari17_0", "firefox133", "edge101", "chrome131"]

BASE_HEADERS = {
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

BLOCK_MARKERS = (
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"Attention Required! | Cloudflare",
    b"Access Denied",
)
RATE_LIMIT_MARKER = b"too many requests recently"

RETRY_STATUS = {429, 500, 502, 503, 504, 520, 522, 524}
DEFAULT_MAX_RETRIES = 6
DEFAULT_TIMEOUT_SECS = 30
BACKOFF_BASE_SECS = 1.0
BACKOFF_CAP_SECS = 30.0

SNAPSHOT_STORE = "steam-sales-tracker-snapshots"
