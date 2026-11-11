"""Endpoints, rate-limit pacing, Steam enums.

Recon 2026-10-11: no WAF on store.steampowered.com or steamcommunity.com -
plain python-requests gets 200 on every endpoint used here (nginx, no
Cloudflare/Akamai markers). The only gate is a per-IP rate limit on
/appreviews/ (HTTP 429 + {"success":84} after ~50 rapid requests, ~30-60 s
cooldown, identical for every TLS profile). /appreviewhistogram/ and
/api/appdetails/ are separate buckets. TLS impersonation is kept only so the
traffic looks like a browser; the profiles below are rotated on odd failures.
"""

STORE = "https://store.steampowered.com"
COMMUNITY = "https://steamcommunity.com"

REVIEWS_URL = STORE + "/appreviews/{appid}"
HISTOGRAM_URL = STORE + "/appreviewhistogram/{appid}"
APPDETAILS_URL = STORE + "/api/appdetails"
STORESEARCH_URL = STORE + "/api/storesearch/"

TLS_PROFILES = ["chrome124", "safari17_0", "edge101"]

BASE_HEADERS = {
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

DEFAULT_TIMEOUT_SECS = 30
DEFAULT_MAX_RETRIES = 8
BACKOFF_BASE_SECS = 1.5
BACKOFF_CAP_SECS = 30.0
# Without a proxy every request shares one IP, so a 429 means "wait out the
# window"; measured cooldown 30-60 s.
RATE_LIMIT_COOLDOWN_SECS = 35.0
RETRY_STATUS = {429, 500, 502, 503, 504}

# Minimum gap between /appreviews/ calls on ONE exit IP. 50 back-to-back
# requests trip the limiter; ~1.3 s spacing was sustained without a 429.
REVIEWS_MIN_INTERVAL_SECS = 1.3
OTHER_MIN_INTERVAL_SECS = 0.4

REVIEWS_PAGE_SIZE = 100  # API maximum

# Steam's own language codes for the reviews API. An unknown code is NOT an
# error upstream - it silently returns "No user reviews" - so validate here.
LANGUAGES = [
    "english", "schinese", "tchinese", "russian", "brazilian", "portuguese",
    "spanish", "latam", "german", "french", "japanese", "koreana", "polish",
    "turkish", "italian", "ukrainian", "czech", "thai", "vietnamese",
    "indonesian", "dutch", "swedish", "danish", "finnish", "norwegian",
    "hungarian", "romanian", "greek", "bulgarian", "arabic",
]

DEFAULT_BREAKDOWN_LANGUAGES = [
    "english", "schinese", "russian", "brazilian", "spanish", "german",
    "french", "japanese", "koreana", "polish", "turkish",
]

REVIEW_FILTERS = {"recent", "updated", "all"}
PURCHASE_TYPES = {"all", "steam", "non_steam_purchase"}
REVIEW_TYPES = {"all", "positive", "negative"}

# Playtime buckets (hours at time of review) for the sentiment-by-playtime table.
PLAYTIME_BUCKETS = [(0, 2), (2, 10), (10, 50), (50, 200), (200, None)]
