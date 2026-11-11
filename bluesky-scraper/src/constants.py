"""Endpoints, hosts, limits, headers -- all in one place.

TLS profile rationale
---------------------
Bluesky's AppView (`public.api.bsky.app`) has **no WAF and no TLS
fingerprint gate**: during recon plain `httpx`, `primp`, and every
`curl_cffi` profile tried (chrome124 / chrome131 / safari17_0 /
firefox133) all returned 200 on the same IP. `chrome124` is used purely
for portfolio consistency and to smooth over transient network errors --
NOT as a bypass. Do not waste time rotating profiles here; the only
throttle on this platform is an IP-bucket on one single endpoint
(see SEARCH_HOST below).
"""

# See module docstring -- not a bypass, just the house default.
TLS_PROFILE = "chrome124"

# ---------------------------------------------------------------- hosts
# The public AppView. Unauthenticated, unthrottled in practice
# (30x limit=100 burst -> 30x 200 during recon).
PUBLIC_HOST = "https://public.api.bsky.app"

# `app.bsky.feed.searchPosts` is the ONE method the CDN in front of
# `public.api.bsky.app` hard-blocks: BunnyCDN returns an HTML 403 for
# that path under every URL variant tried (trailing slash, double slash,
# percent-encoded dot) and regardless of headers -- it is a path rule,
# not a bot check. `api.bsky.app` serves it instead, behind an nginx
# per-IP token bucket (~5 requests, then
# `403 Request forbidden by administrative rules`). Recovery is NOT on a
# fixed clock -- see the retry section below. The block is scoped to
# this one method: every other method on the same host and session keeps
# returning 200 while search is blocked.
SEARCH_HOST = "https://api.bsky.app"
SEARCH_METHOD = "app.bsky.feed.searchPosts"

# --------------------------------------------------------------- limits
# Every cursor-paginated XRPC method caps `limit` at 100; 101 -> 400.
MAX_LIMIT = 100
# `getProfiles` / `getPosts` take an array of up to 25 identifiers; 26 -> 400.
MAX_BATCH = 25
# `getPostThread` depth cap per lexicon.
MAX_THREAD_DEPTH = 1000

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# --------------------------------------------------------------- retry
MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0        # exponential: 1 / 2 / 4 / 8 / 16 s

# The searchPosts bucket does NOT refill on a fixed clock, and blocked
# attempts appear to keep it drained: measured 60s rest -> 1 token,
# 120s rest -> 7 tokens, but 180s and 300s rests after further blocked
# bursts -> 0 tokens. Retrying eagerly makes it strictly worse, so the
# no-proxy path waits long and gives up early rather than hammering.
SEARCH_BLOCK_COOLDOWN = 90.0
SEARCH_MAX_BLOCK_WAITS = 2

# With no proxy to rotate to, pace search requests so the bucket never
# empties in the first place -- roughly the observed sustainable rate
# (~7 requests per 120s). Skipped entirely when a proxy is configured.
SEARCH_PACE_NO_PROXY = 20.0
