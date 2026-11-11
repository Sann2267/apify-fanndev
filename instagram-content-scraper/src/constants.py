"""Endpoints, headers and per-mode query wiring for Instagram's logged-out web surface.

Why this actor does not touch `/api/v1/...`
-------------------------------------------
Recon on 2026-09-11 found that Instagram's legacy public REST API is closed to
anonymous callers. `web_profile_info`, `feed/user`, `tags/web_info`,
`locations/web_info`, `topsearch`, `highlights_tray` and `media/<id>/comments`
all answer **HTTP 401** with::

    {"message":"Please wait a few minutes before you try again.",
     "require_login":true,"igweb_rollout":true,"status":"fail"}

That is an application-level rollout, not a fingerprint gate: the response is
byte-identical across chrome124 / safari17_0 / firefox133 / edge101 /
chrome99_android on the same IP. No TLS profile, header order or cookie trick
reopens it -- so this actor does not try.

What *is* open is the logged-out server-rendered Relay surface. Instagram still
SSRs a "LoggedOut" variant of its own GraphQL queries into the page, and --
crucially -- ships the query id and its variables inline next to the data::

    {"queryID":"27553725110923321",
     "variables":{"first":12,"username":"nasa"},
     "queryName":"PolarisLoggedOutDesktopWWWProfilePostsTabContentQuery"}

So the doc_id is harvested from the very page being scraped rather than pinned
in source. That sidesteps the usual persisted-query rot entirely: when Meta
rotates ids, the next warm-up picks the new one up. There is nothing to cache
and nothing to refresh.

The endpoint trap
-----------------
Replays MUST go to ``/api/graphql/``. The widely documented ``/graphql/query``
accepts the same body and answers **200 OK** with ``{"data":{"<root>":null}}``
-- a success status carrying no data. Measured side by side: ``/api/graphql/``
returned 18 KB and 12 edges, ``/graphql/query`` returned 174 bytes and null, for
identical form fields. A status-only health check would call that a pass, which
is exactly the silent-empty failure this codebase forbids.
"""

ORIGIN = "https://www.instagram.com"
GRAPHQL_URL = f"{ORIGIN}/api/graphql/"

# Instagram's public logged-out web app id. Not a secret, not account-bound.
# Kept because it is what the real client sends; the replay works without it.
IG_APP_ID = "936619743392459"

# Instagram applies no TLS gate (see module docstring), so the ladder exists
# only to vary the fingerprint after a throttle, not to defeat a JA3 blocklist.
# chrome124 leads because it is the profile the whole recon was measured on.
TLS_PROFILE_LADDER = ("chrome124", "safari17_0", "firefox133", "edge101", "chrome99_android")

PAGE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

GRAPHQL_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "X-IG-App-ID": IG_APP_ID,
    "Origin": ORIGIN,
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

REQUEST_TIMEOUT = 60
MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0

# Instagram throttles anonymous traffic per IP and answers with a login wall
# rather than a 429, so pacing keeps a run alive far longer than hammering.
DEFAULT_DELAY_SECONDS = 1.5

# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------
# `query` is the *substring* used to pick the right preload out of the warm
# page -- the full names carry a "LoggedOutDesktopWWW" infix that Meta has
# already renamed once, so matching loosely survives that.
MODE_PROFILE = "profile"
MODE_POSTS = "posts"
MODE_REELS = "reels"
MODE_POST_DETAIL = "post_detail"
MODE_LOCATION = "location"

ALL_MODES = (MODE_PROFILE, MODE_POSTS, MODE_REELS, MODE_POST_DETAIL, MODE_LOCATION)

# Root keys of the Relay payload each mode reads, both in SSR and on replay.
ROOT_USER = "xig_user_by_username"
ROOT_MEDIA = "xig_polaris_media"
ROOT_LOCATION_INFO = "xdt_location_get_web_info"
ROOT_LOCATION_TAB = "xdt_location_get_web_info_tab"

# Connection key per mode, used to tell the timeline connection apart from the
# highlights-tray connection that shares the same `xig_user_by_username` root.
CONN_POSTS = "polaris_ordered_timeline_connection"
CONN_REELS = "polaris_clips_connection"
CONN_HIGHLIGHTS = "lox_highlights_connection"
CONN_COMMENTS = "comments_connection"

PAGE_SIZE = 12

SOURCE_SSR = "ssr-relay-island"
SOURCE_GRAPHQL = "api-graphql-replay"

# Error codes emitted as diagnostic rows. Every input yields at least one row.
ERR_INVALID_INPUT = "INVALID_INPUT"
ERR_NOT_FOUND = "NOT_FOUND"
ERR_PRIVATE = "PRIVATE_ACCOUNT"
ERR_BLOCKED = "BLOCKED_AFTER_RETRIES"
ERR_SHAPE = "UPSTREAM_SHAPE_CHANGED"
ERR_EMPTY = "EMPTY_RESULT"
ERR_GATED = "GATED_FOR_LOGGED_OUT"
