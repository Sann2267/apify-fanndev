"""Endpoints, headers, TLS profiles and retry policy.

WAF profile (recon 2026-10-11): NONE. steamcommunity.com and
api.steampowered.com answer 200 to a bare python-requests TLS fingerprint.
The only gate is a per-IP RATE LIMIT on steamcommunity.com HTML pages:

  * profile / friends / badges HTML  -> HTTP 429 (29 KB HTML body) after ~120
    requests in ~6 s; recovers ~43 s later. This bucket is SEPARATE from the
    XML and stats surfaces - while HTML was 429ing, ?xml=1 and /stats/ kept
    answering 200.
  * ?xml=1 profiles (300 @ c10), stats XML (200 @ c10) and
    IPlayerService/GetGameAchievements (100 @ c10) drew zero 429s.

Keep hammering through the 429s and Akamai escalates to a 414-byte 403
'Access Denied' (server AkamaiGHost) for ~20 s - on XML too. The two limits are
keyed differently: Steam's 429 on the IP only (fresh sessions with other TLS
profiles stayed 429), Akamai's 403 on IP + TLS fingerprint (chrome124 403 while
safari17_0/firefox133 got 200 from the same IP at the same moment).

So HTML requests get their own small semaphore and a long 429 backoff (or an
exit-IP rotation when an Apify Proxy is configured). curl_cffi impersonation is
not what makes requests pass; it is kept as cheap insurance and rotated on a
403/challenge in case Valve ever turns a bot rule on.

robots.txt (steamcommunity.com) only disallows /actions/, /linkfilter/,
/tradeoffer/, /trade/, /email/ - none used here.
"""

from __future__ import annotations

COMMUNITY = "https://steamcommunity.com"
STEAM_API = "https://api.steampowered.com"

# Official Steam Web API - keyless endpoints only (everything else needs key=).
URL_GAME_ACHIEVEMENTS = f"{STEAM_API}/IPlayerService/GetGameAchievements/v1/"
URL_PROFILE_ITEMS = f"{STEAM_API}/IPlayerService/GetProfileItemsEquipped/v1/"
URL_STORE_ITEMS = f"{STEAM_API}/IStoreBrowseService/GetItems/v1/"
STORE_ITEMS_BATCH = 100

# Asset hosts for relative paths returned by the APIs.
ACH_ICON_BASE = "https://shared.fastly.steamstatic.com/community_assets/images/apps"
ITEM_ASSET_BASE = "https://shared.fastly.steamstatic.com/community_assets/images"

STEAMID64_BASE = 76561197960265728

# Badges page: 150 rows per page, `?p=N`.
BADGES_PAGE_SIZE = 150
# Group member list XML: 1000 ids per page, `&p=N`.
GROUP_PAGE_SIZE = 1000

TLS_PROFILES = ["chrome124", "safari17_0", "firefox133", "edge101", "chrome131"]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}

BLOCK_MARKERS = (
    b"Just a moment",
    b"challenge-platform",
    b"cf-mitigated",
    b"Access Denied",
)

RETRY_STATUS = {429, 500, 502, 503, 504, 520, 522, 524}
DEFAULT_MAX_RETRIES = 6
DEFAULT_TIMEOUT_SECS = 40
BACKOFF_BASE_SECS = 1.0
BACKOFF_CAP_SECS = 30.0
# HTML 429 bucket recovers in ~43 s (measured); without a proxy, wait it out.
HTML_429_WAIT_SECS = 45.0
# Akamai 'Access Denied' 403 after sustained 429s; lifted ~20 s later.
AKAMAI_PENALTY_WAIT_SECS = 25.0
DEFAULT_HTML_CONCURRENCY = 2
