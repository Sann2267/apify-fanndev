"""Endpoints, protocol constants and the GetLocalBoqProxy payload contract.

Everything here was verified live against Google on 2026-09-16 -- see
CRAWLING_METHOD.md for the full reconnaissance log and the dead ends.
"""

# --------------------------------------------------------------------------
# TLS profile
# --------------------------------------------------------------------------
# Google Maps applies NO TLS-level gating on these endpoints: all ten profiles
# tested (chrome150/146/131/124, firefox147/135, safari2601/180, edge101,
# chrome99_android) returned identical 200s from a plain residential ISP IP.
# chrome150 is chosen simply as the most current Chrome fingerprint; the
# ladder below exists for future-proofing, not because anything is blocked.
TLS_PROFILE = "chrome150"
TLS_LADDER = ["chrome150", "chrome146", "firefox147", "safari2601", "chrome131"]

# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
BASE_URL = "https://www.google.com"
WARMUP_URL = f"{BASE_URL}/maps/?hl=en&gl=US"

# The live reviews RPC. Google retired the endpoints every public guide still
# documents: /maps/rpc/listugcposts now answers 403 PERMISSION_DENIED (grpc
# code 7) for every TLS profile, country host, header set and session token,
# while /maps/rpc/listentityreviews and /async/reviewDialog return 404.
REVIEWS_URL = f"{BASE_URL}/httpservice/web/PrivateLocalSearchUiDataService/GetLocalBoqProxy"

# Place ID -> Feature ID resolver. The response embeds a small XSSI-prefixed
# blob inside window.APP_INITIALIZATION_STATE carrying the FID and place name.
PLACE_RESOLVER_URL = f"{BASE_URL}/maps/place/"

# Consent cookie. Google shows a GDPR interstitial instead of the page itself
# to clients that have not consented, which is invisible from a non-EU IP but
# routine once a proxy puts the exit IP in Europe. This is the "consented"
# token; CONSENT=YES+1 alone is no longer sufficient.
CONSENT_SOCS = (
    "CAISNQgQEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjQwNDIzLjA2X3AwGgJlbiADGgYIgOy4sQY"
)

# Markers that identify an interstitial rather than the page we asked for.
CONSENT_MARKERS = ("consent.google.com", "Before you continue", "CookieConsent",
                   "/httpservice/retry/enablejs")
CAPTCHA_MARKERS = ("/sorry/index", "CaptchaRedirect", "unusual traffic")

# --------------------------------------------------------------------------
# Headers
# --------------------------------------------------------------------------
# Navigation headers for HTML page loads (warm-up + resolver).
NAVIGATE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

# XHR headers for the RPC itself.
BROWSER_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "referer": f"{BASE_URL}/maps/",
    "x-same-domain": "1",
}

# --------------------------------------------------------------------------
# GetLocalBoqProxy payload contract
# --------------------------------------------------------------------------
# reqpld = [null, [null x9, INNER]] where INNER has exactly 24 slots.
INNER_LEN = 24

SLOT_SORT = 1           # 1 relevant | 2 newest | 3 highest | 4 lowest
SLOT_PAGE_SIZE = 9      # int on the first page, MUST be null when paginating
SLOT_PLACE = 11         # [feature_id, null, null, place_slug]
SLOT_QUERY = 14         # "" -- reviews-only endpoint, a query here is ignored
SLOT_REACTIONS = 16     # [1, 1, null, [[3],[4],[5],[6],[7]]] reaction categories
SLOT_PAGE_TOKEN = 19    # next-page cursor.
SLOT_TRAILER = 23       # constant 0

# NOTE: the only public documentation of this endpoint places the page token at
# slot 20. That is off by one -- slot 20 answers HTTP 400, and slot 19 is the
# real cursor (verified: overlap 0/20 between consecutive pages, 240 unique
# reviews over 12 pages with zero duplicates). Several neighbouring slots accept
# the token and return a plausible 200 while silently ignoring it and re-serving
# page 1, so any change here must be validated by diffing review IDs, never by
# checking the status code.

SORT_MODES = {"relevant": 1, "newest": 2, "highest": 3, "lowest": 4}

# Google caps the first page at 60 regardless of what is requested
# (num=50 -> 50, num=100 -> 60, num=200 -> 60). Paginated pages always
# return 20 whatever the first page asked for.
MAX_PAGE_SIZE = 60
DEFAULT_PAGE_SIZE = 50

# Reaction category 3 is the thumbs-up / "helpful" counter that the Maps UI
# surfaces as a review's like count. Categories 4-7 are other reaction types
# and are passed through untouched under reactionCounts.
REACTION_LIKE_CATEGORY = 3
REACTION_CATEGORIES = [3, 4, 5, 6, 7]

# --------------------------------------------------------------------------
# Review record field map (index -> meaning) inside d[1][10][2][i]
# --------------------------------------------------------------------------
R_RATING = 1
R_TIME = 2              # [relative_str, ?, epoch_millis_str]
R_REVIEWER = 3          # [name, avatar_url, profile_url, review_count, photo_count, ...]
R_OWNER_RESPONSE = 4    # [null, relative_str, text, ...]
R_REVIEW_ID = 5
R_REPORT_URL = 10
R_PERMALINK = 12
R_PHOTOS = 14
R_LANGUAGE = 26
R_TEXT = 27
R_TEXT_DISPLAY = 28
R_ATTRIBUTES = 30       # structured "when did you visit" style answers
R_VISIT_TEXT = 32
R_VISIT_MONTH = 33
R_SOURCE_LANG_NAME = 36
R_TRANSLATED_TEXT = 37
R_TRANSLATED_DISPLAY = 38
R_TARGET_LANG_NAME = 41
R_PLATFORM = 44         # ["Google", [...]]
R_RATING_ALT = 45
R_RATING_MAX = 46
R_REACTIONS = 47        # [null, [[3, n], [4, n], [5, n], [6, n], [7, n]]]

# Response navigation
RESP_REVIEW_NODE = (1, 10)
RESP_REVIEWS_IDX = 2
RESP_TOKEN_IDX = 6

# --------------------------------------------------------------------------
# Retry policy
# --------------------------------------------------------------------------
MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0      # exponential 1 / 2 / 4 / 8 / 16 seconds
REQUEST_DELAY = 0.35        # polite inter-page delay
