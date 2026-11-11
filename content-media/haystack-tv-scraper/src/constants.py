"""Endpoints, headers, TLS profile and knobs for the Haystack News actor.

Recon notes (2026-09-14) that justify the values below:

* haystack.tv fronts on Heroku/Express with NO anti-bot vendor -- no Cloudflare,
  DataDome, PerimeterX, Akamai or AWS WAF. Plain `requests` (no impersonation at
  all) returns 200, and every curl_cffi profile tried -- chrome99_android,
  chrome124, chrome131, chrome136, safari17_0, edge101, firefox133 -- also
  returns 200 on the authenticated playlist endpoint. We still go through
  curl_cffi because it costs nothing and keeps one HTTP stack across the
  portfolio, but the profile is NOT load-bearing here.
* The API has exactly two gates, both satisfiable without a login:
    1. `hs-client-version` / `hs-client-os` headers. Omit the version and the
       API answers 400 {"errorTitle":"Please Upgrade"} on /playlist.
    2. `Authorization: Bearer <hs_access_token>` -- an ANONYMOUS JWT that
       www.haystack.tv hands out in a Set-Cookie on any page load. No sign-in,
       no device registration. Valid ~1 year and portable across IPs.
"""

# --- TLS ---------------------------------------------------------------------
# Not load-bearing (see module docstring): every profile tested returned 200.
# chrome124 is the portfolio default and matches the UA the site expects.
TLS_PROFILE = "chrome124"

# --- Hosts -------------------------------------------------------------------
SITE_URL = "https://www.haystack.tv"
API_URL = "https://api.haystack.tv"

# Token comes from a Set-Cookie on any www page; the homepage is the cheapest.
WARMUP_URL = f"{SITE_URL}/"
ACCESS_TOKEN_COOKIE = "hs_access_token"

# --- Endpoints ---------------------------------------------------------------
EP_PLAYLIST = f"{API_URL}/api/v1/playlist"          # Bearer required
EP_SEARCH = f"{API_URL}/api/v1/search"              # Bearer required
EP_SUGGEST = f"{API_URL}/api/v1/suggest"            # open
EP_CHANNEL = f"{API_URL}/api/v1/channel"            # open
EP_SITEMAP = f"{API_URL}/api/v1/sitemap"            # open
EP_LOCAL_EVENTS = f"{API_URL}/api/v1/localEvents"   # Bearer required
EP_POLLS_DATA = f"{SITE_URL}/polls/__data.json"     # open (SvelteKit SSR)
EP_SITEMAP_XML = f"{SITE_URL}/sitemap.xml"          # open

# --- Client contract ---------------------------------------------------------
# `hs-client-version` is read off the live bundle as the constant `Ca=7.1`. If
# Haystack retires 7.1 the API answers 400 "Please Upgrade" and the client walks
# this ladder (newest first) rather than dying -- see client.refresh_client_version.
CLIENT_VERSION = "7.1"
CLIENT_VERSION_LADDER = ["7.1", "7.2", "7.3", "8.0", "7.0", "6.9"]
CLIENT_OS = "web"

# Thumbnail sizes the website itself asks for; keeps the payload shape identical
# to what a real browser receives.
SNAPSHOT_QUALITY = "low,720"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": SITE_URL,
    "Referer": f"{SITE_URL}/",
}

# --- Retry policy ------------------------------------------------------------
MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0          # exponential: 1 / 2 / 4 / 8 / 16 s
REQUEST_TIMEOUT = 45

# --- Local events ------------------------------------------------------------
# Anonymous users get 10 events per query out of `total` (700 for Houston).
# `category` x `sort` are the only two filters the API honours for us, so we
# slice on both to widen the harvest. Verified 66 unique from 16 calls.
LOCAL_EVENT_SORTS = ["diversified", "date", "distance"]
LOCAL_EVENT_CATEGORIES = [
    "music_concerts",
    "sports",
    "performing_visual_arts",
    "lifestyle_culture",
    "community_events",
]
