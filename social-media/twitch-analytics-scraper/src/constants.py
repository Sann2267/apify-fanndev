"""Endpoints, headers, whitelists -- all in one place.

Recon summary (2026-08-26): this actor is a market/directory-level
sibling to `twitch-channel-scraper` (already in this portfolio, which
covers a SINGLE channel's profile/videos/clips/schedule). This actor
covers cross-channel "analytics" data instead -- trending games/
categories, global top live streams, top channels within a category, and
a per-channel trending-rank lookup -- all via the same gql.twitch.tv/gql
endpoint with the same public web Client-Id
(kimne78kx3ncx6brgo4mv6wki5h1ko), inline (non-persisted) queries, zero
WAF, zero login.

Two platform behaviors confirmed live and worth knowing before touching
this code:

1. **Hard page-size ceilings, different per connection** (not a bug --
   a real GraphQL argument-validation error naming the exact range):
   - `streams` (top-level AND `game.streams`): 1-30. `first: 31+` errors.
   - `games`: 1-100. `first: 101+` errors.

2. **`sort: VIEWER_COUNT` is NOT a strictly monotonic sort.** Confirmed
   repeatedly on both `streams` and `game.streams`: a fetched page of 10
   "VIEWER_COUNT"-sorted live streams came back as
   `[78360, 63866, 63044, 40445, 4212, 34845, 33017, ...]` -- a low
   outlier (4212) sandwiched between much higher values, with every
   sampled stream confirmed `type: "live"` (ruling out a rerun/premiere
   explanation). This reads as Twitch's directory blending additional
   signals (a "trending" score) beyond raw current viewer count, or
   cross-shard eventual-consistency -- either way it is a genuine,
   reproducible platform behavior, not a client-side bug. This actor
   surfaces the field verbatim and documents it as *approximately*
   ordered, never claims a guaranteed strict sort. See
   CRAWLING_METHOD.md.

Same integrity wall as `twitch-channel-scraper`: `after`-cursor
pagination beyond page 1 on `games`/`streams`/`game.streams` returns
`IntegrityCheckFailed` for an HTTP-only anonymous client -- this actor
caps at a single page per connection (up to the ceilings above) and
documents it, rather than chasing a browser-only bypass.
"""

TLS_PROFILE = "chrome124"

GQL_URL = "https://gql.twitch.tv/gql"
CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

DEFAULT_HEADERS = {
    "Client-Id": CLIENT_ID,
    "Content-Type": "text/plain;charset=UTF-8",
}

# Hard platform ceilings confirmed live via GraphQL argument-validation
# errors ("argument 'first' value must be between 1 and N").
MAX_FIRST_STREAMS = 30
MAX_FIRST_GAMES = 100

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
