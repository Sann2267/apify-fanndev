"""Endpoints, headers, TLS profiles and retry policy.

WAF profile (recon 2026-10-11): NONE on every surface used here.
api.steampowered.com, store.steampowered.com and steamcharts.com (behind
Cloudflare, but no bot rules) all answer 200 to a bare python-requests UA with
no TLS impersonation; 100 API calls at concurrency 10 and 100 steamcharts
pages at concurrency 6 drew zero 429s. curl_cffi impersonation is kept only as
cheap insurance: if Cloudflare ever turns a rule on for steamcharts, the client
already rotates TLS profile + exit IP instead of failing outright.
"""

from __future__ import annotations

STEAM_API = "https://api.steampowered.com"
STORE = "https://store.steampowered.com"
STEAMCHARTS = "https://steamcharts.com"

# Official Steam Web API - keyless.
URL_TOP_CONCURRENT = f"{STEAM_API}/ISteamChartsService/GetGamesByConcurrentPlayers/v1/"
URL_TOP_DAILY_PEAK = f"{STEAM_API}/ISteamChartsService/GetMostPlayedGames/v1/"
URL_CURRENT_PLAYERS = f"{STEAM_API}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
URL_STORE_ITEMS = f"{STEAM_API}/IStoreBrowseService/GetItems/v1/"
URL_STORE_SEARCH = f"{STORE}/api/storesearch/"
URL_STEAM_ONLINE = f"{STORE}/stats/userdata.json"

# GetItems accepts up to 250 ids per GET (500 -> HTTP 400); 100 keeps the URL short.
STORE_ITEMS_BATCH = 100
# GetNumberOfCurrentPlayers: unknown appid -> HTTP 404 + {"response":{"result":42}}.
RESULT_NO_MATCH = 42

# steamcharts.com /top: 25 rows per page, ~507 pages (~12.7k games) on 2026-10-11.
STEAMCHARTS_TOP_PAGE_SIZE = 25

# First profile is the one recon ran on; the rest are the ladder from
# .ai/skills/tls-fingerprinting for when a gate ever appears.
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

RETRY_STATUS = {429, 500, 502, 503, 504, 520, 522, 524}
DEFAULT_MAX_RETRIES = 5
DEFAULT_TIMEOUT_SECS = 30
BACKOFF_BASE_SECS = 1.0
BACKOFF_CAP_SECS = 30.0

SNAPSHOT_STORE = "steam-players-monitor-snapshots"
