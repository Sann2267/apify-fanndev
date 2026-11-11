"""Endpoints, pb templates and the place field map.

Everything here was verified live against Google on 2026-09-16 -- see
CRAWLING_METHOD.md for the reconnaissance log.

The single most useful discovery: search results and place details share the
SAME positional schema. A `tbm=map` search entry carries the full lead record
(name, category, address, phone, website, hours, coordinates), so a lead-gen run
needs one request per 20 leads rather than one request per lead.
"""

# --------------------------------------------------------------------------
# TLS profile
# --------------------------------------------------------------------------
# Google applies no TLS gating on these endpoints -- ten profiles all returned
# 200 from a plain ISP connection. chrome150 is simply the most current Chrome
# fingerprint; the ladder exists for future-proofing, not to defeat a block.
TLS_PROFILE = "chrome150"
TLS_LADDER = ["chrome150", "chrome146", "firefox147", "safari2601", "chrome131"]

# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
BASE_URL = "https://www.google.com"
WARMUP_URL = f"{BASE_URL}/maps/?hl=en&gl=US"
SEARCH_URL = f"{BASE_URL}/search"                      # with tbm=map
PLACE_URL = f"{BASE_URL}/maps/preview/place"
PLACE_RESOLVER_URL = f"{BASE_URL}/maps/place/"

# --------------------------------------------------------------------------
# Headers
# --------------------------------------------------------------------------
NAVIGATE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

BROWSER_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "referer": f"{BASE_URL}/maps/",
}

# Consent cookies. Google shows a GDPR interstitial instead of the page to
# clients that have not consented -- invisible from a non-EU IP, routine once a
# proxy puts the exit IP in Europe. CONSENT=YES+1 alone is no longer sufficient.
CONSENT_SOCS = (
    "CAISNQgQEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjQwNDIzLjA2X3AwGgJlbiADGgYIgOy4sQY"
)
CONSENT_MARKERS = ("consent.google.com", "Before you continue", "CookieConsent",
                   "/httpservice/retry/enablejs")
CAPTCHA_MARKERS = ("/sorry/index", "CaptchaRedirect", "unusual traffic")

# --------------------------------------------------------------------------
# tbm=map search pb
# --------------------------------------------------------------------------
# The viewport block decides WHERE Google searches: !1d is a distance/zoom span
# in metres, !2d longitude, !3d latitude. Changing !1d demonstrably changes the
# result set, which is what makes real geographic targeting possible.
SEARCH_VIEWPORT = (
    "!4m12!1m3!1d{distance}!2d{longitude}!3d{latitude}"
    "!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1"
)

# !7i20 = page size (20 is Google's max here), !8i = result offset.
SEARCH_TAIL = (
    "!7i20!8i{offset}!10b1!12m6!1m1!18b1!2m1!20e3!6m1!114b1!17m1!3e1"
    "!20m57!2m2!1i203!2i100!3m2!2i4!5b1!6m6!1m2!1i86!2i86!1m2!1i408!2i240"
    "!7m33!1m3!1e1!2b0!3e3!1m3!1e2!2b1!3e2!1m3!1e2!2b0!3e3!1m3!1e8!2b0!3e3"
    "!1m3!1e10!2b0!3e3!1m3!1e10!2b1!3e2!1m3!1e10!2b0!3e4!1m3!1e9!2b1!3e2!2b1!9b0"
    "!15m8!1m7!1m2!1m1!1e2!2m2!1i195!2i195!3i20"
)

SEARCH_PAGE_SIZE = 20       # Google's hard cap for this endpoint

# --------------------------------------------------------------------------
# /maps/preview/place pb
# --------------------------------------------------------------------------
# NOTE on the trailing !13b1: without one extra token past !37i771 Google
# returns a reduced record carrying only today/tomorrow opening hours and no
# review count. Appending ANY additional token switches it to the full record
# (all seven days, review totals). Several different tokens produced a
# byte-identical response, so this is a payload-framing effect rather than a
# meaningful flag -- do not "tidy it away".
PLACE_PB = (
    "!1m14!1s{feature_id}!3m9!1m3!1d5000!2d0!3d0!2m0!3m2!1i1024!2i768!4f13.1"
    "!4m2!3d0!4d0!13m1!2m0"
    "!15m47!1m8!4e2!18m5!3b0!6b0!14b1!17b1!20b1!20e2!4b1!10m1!8e3!11m1!3e1!17b1"
    "!20m2!1e3!1e6!24b1!25b1!26b1!29b1!30m1!2b1!36b1!43b1!52b1!55b1!56m1!1b1"
    "!65m5!3m4!1m3!1m2!1i224!2i298!22m1!1e81!29m0!30m6!3b1!6m1!2b1!7m1!2b1!9b1"
    "!32b1!37i771!13b1"
)

# --------------------------------------------------------------------------
# Place field map -- shared by search entries and place details
# --------------------------------------------------------------------------
# Search: response[0][1][i][14] -> this shape.
# Details: response[6]          -> this same shape.
P_ADDRESS_PARTS = 2      # ["Jl. Daksa I No.11A", "RT.4/RW.2", "Kebayoran Baru", ...]
P_RATING_BLOCK = 4       # [..., [reviews_url, "826 reviews", ...], ..., 4.4, 826]
P_WEBSITE = 7            # [full_url, display_domain, ...]
P_COORDS = 9             # [null, null, latitude, longitude]
P_FEATURE_ID = 10
P_NAME = 11
P_CATEGORIES = 13        # ["Dental clinic", ...]
P_ADDRESS_WITH_NAME = 18
P_TIMEZONE = 30
P_ADDRESS = 39           # single-line formatted address
P_PREVIEW_URL = 42
P_PLACE_ID = 78          # ChIJ...
P_GOOGLE_SLUG = 89       # /g/11c...
P_LANGUAGE = 110
P_THUMBNAIL = 157
P_REGION = 166
P_PHONE = 178            # [pretty, [[local,1],[intl,2]], null, e164, null, [tel:..]]
P_DESCRIPTION = 154
P_HOURS = 203            # [[[day, n, [y,m,d], [[ "10 AM-8 PM", ...]], ...], ...]]
P_ATTRIBUTES = 100
P_PLUS_CODE = 183

# Response navigation
SEARCH_RESULTS_PATH = (0, 1)     # response[0][1] -> list of entries
SEARCH_ENTRY_PLACE_IDX = 14      # entry[14] -> place record
PLACE_DETAIL_IDX = 6             # response[6] -> place record

# --------------------------------------------------------------------------
# Enrichment
# --------------------------------------------------------------------------
# Paths on social domains that are share widgets / tracking pixels rather than
# a business account. Without this, nearly every site "has" a Facebook account
# called "sharer" and a Twitter account called "share".
SOCIAL_PATH_BLOCKLIST = {
    "sharer", "share", "sharer.php", "share.php", "intent", "tr", "plugins",
    "dialog", "home", "login", "signup", "help", "privacy", "terms", "policies",
    "search", "hashtag", "explore", "watch", "events", "pages", "groups",
    "profile.php", "people", "embed", "widgets", "oembed", "v", "results",
}

CONTACT_PAGE_HINTS = ("contact", "kontak", "hubungi", "about", "tentang",
                      "impressum", "reach-us", "get-in-touch")

MAX_ENRICH_BYTES = 2_000_000     # stop reading a page after this much HTML
ENRICH_TIMEOUT = 20

# --------------------------------------------------------------------------
# Retry policy
# --------------------------------------------------------------------------
MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
REQUEST_DELAY = 0.35
