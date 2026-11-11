# Crawling Method — Twitch Streamer & Channel Analytics

**Last verified:** 2026-08-26

## Relationship to `twitch-channel-scraper`

This portfolio already has `twitch-channel-scraper` (single-channel
profile/live-status/videos/clips/schedule). This actor is a deliberate
sibling, not a duplicate: it covers **cross-channel, market-level**
data — trending games, the platform-wide top live streams, the top
channels within one category, and a per-channel "is this streamer
currently trending" rank lookup. Same endpoint, same client, same
zero-WAF finding, but a genuinely different data shape and use case
(competitive/market research vs. single-channel profile lookup) — kept
as two actors rather than folding a 5th "analytics" mode into the
existing actor, since the query composition for `channel-rank` (3 GQL
calls per input, cross-referencing two directory lists) is meaningfully
heavier than the single-call modes in the other actor.

## WAF

Identical finding to `twitch-channel-scraper`: **none.** `gql.twitch.tv`
(Twitch's own internal GraphQL API, used by every logged-out visitor)
accepts `curl_cffi` `chrome124` with just the public web
`Client-Id: kimne78kx3ncx6brgo4mv6wki5h1ko` header — no WAF challenge,
no login.

## Real platform ceilings confirmed live (not bugs)

| Connection | Max `first` | Confirmed via |
|---|---|---|
| `streams` (top-level) | 30 | `first: 31` → `"argument 'first' value must be between 1 and 30."` |
| `game.streams` | 30 | Same connection type as top-level `streams`. |
| `games` | 100 | `first: 101` → `"argument 'first' value must be between 1 and 100."` |

Same `after`-cursor integrity wall as `twitch-channel-scraper`: paging
past page 1 on any of these three connections returns
`IntegrityCheckFailed`. This actor caps at a single page (up to the
ceilings above) per query and documents it rather than chasing a
browser-only bypass — consistent with project HTTP-only constraints.

## Real quirk found: `sort: VIEWER_COUNT` is NOT strictly monotonic

This is the most important finding in this actor and is surfaced
explicitly in every ranked output row via `_approxSort: true`.

Confirmed repeatedly, on both `streams` and `game.streams`, with
`options: {sort: VIEWER_COUNT}` explicitly set: a fetched page came back
as `[78360, 63866, 63044, 40445, 4212, 34845, 33017, 31506, 30653,
15871]` — note the `4212` sandwiched between `40445` and `34845`. Ruled
out the obvious alternate explanation (a rerun/premiere counted
differently) by checking `type` on every node in that sample — all 10
were `type: "live"`. Reproduced again in this actor's own `test_local.py`
run (rank 4 = 4,454 viewers, rank 5 = 34,323 viewers, same site).

This reads as Twitch's directory blending an undisclosed "trending"
signal into the ranking (recency of stream start, chat velocity,
category momentum, etc.) rather than a pure descending sort on raw
current viewer count, or possibly cross-shard eventual consistency in
how the ranked index is built. Either way it is a **genuine, reproducible
platform behavior**, not a client-side bug or a parsing error — this
actor:
- Never claims a guaranteed strict sort in its field descriptions or
  README.
- Labels every rank field `rankApprox`/`globalRankApprox`/
  `categoryRankApprox` (not `rank`) and stamps `_approxSort: true` on
  every record that carries one.
- Still returns `viewersCount` verbatim on every row so a downstream
  consumer can re-sort locally if they want a guaranteed-exact order
  within the fetched page (re-sorting the *fetched* page is always
  correct; only the *ranking beyond what one page contains* is where the
  30/100-item ceiling plus non-monotonic ordering compound into "don't
  trust position N as global position N").

## Composed analytics: `channel-rank` mode

This is the one mode that isn't a single passthrough query — it composes
three GQL calls to answer "is this channel trending right now":
1. `CHANNEL_LIVE_QUERY` — is the channel live, and if so what game are
   they in and how many viewers do they have right now.
2. If live: `TOP_STREAMS_QUERY` (top 30 platform-wide) — linear-scan for
   the channel's login in the `broadcaster.login` field of each edge.
3. If live and playing a game: `GAME_STREAMS_QUERY` for that exact game
   name (top 30 in-category) — same linear-scan.

A channel not found in either top-30 list gets `globalRankApprox: null`
/ `categoryRankApprox: null` with an explanatory `*Note` string — this
is the expected, common case (only ~30 channels can be in a top-30 list
platform-wide at any moment) and is not treated as an error.

## Data sources (all `S1-gql`, no fallback)

Per this portfolio's convention for Twitch (`.ai/skills/
multi-strategy-fallback.md`: "Twitch internal GQL → only one path"),
there is no S2 fallback for any mode.

### 1. `top-games` mode
`games(first, options: {sort: VIEWER_COUNT})` → id, name, displayName,
viewersCount, broadcastersCount, channelsCount, boxArtURL. Note:
`broadcastersCount` and `channelsCount` were both confirmed to exist as
separate fields and can differ slightly (4623 vs 4624 on one sample) —
both are passed through verbatim rather than picking one arbitrarily.

### 2. `top-streams` mode
`streams(first, options: {sort: VIEWER_COUNT})` — platform-wide top live
streams with broadcaster and current-game info.

### 3. `game-streams` mode
`game(name) { streams(first, options: {sort: VIEWER_COUNT}) }` — top
live streams within one named category. A nonexistent game name
resolves `game: null` (confirmed, not an error) and is reported as a
structured `_error: "game_not_found"` record.

### 4. `channel-rank` mode
See "Composed analytics" above.

## Known limits

- Rank fields are **approximate**, not guaranteed-exact platform
  positions — see the sort-quirk section above. Treat them as "roughly
  where this channel/game sits," not as ground truth for e.g. billing or
  competitive claims.
- Only the top 30 (streams) / 100 (games) items are visible at all — a
  channel or game outside that window returns `null`/not-found for rank
  purposes, not a larger real number.
- Chat activity, follower-count history/trends, and estimated revenue
  are NOT available via any public Twitch endpoint (the old anonymous
  `tmi.twitch.tv/group/user/{channel}/chatters` endpoint was confirmed
  dead — 404 — during recon; it was deprecated platform-side in 2023 in
  favor of an OAuth-gated Helix endpoint, which is out of scope for this
  "No Login" project). Third-party sites that show these numbers
  (TwitchTracker, SullyGnome, StreamsCharts) compute them from their own
  historical scraping archives, not from a live public Twitch API — this
  actor does not fabricate or estimate these figures.

## Diff cadence

Quarterly smoke test recommended.
