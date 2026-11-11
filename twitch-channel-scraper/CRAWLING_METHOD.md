# Crawling Method — Twitch Channel Scraper

**Last verified:** 2026-08-26

## Architecture decision: one multi-mode actor, not four

Twitch channel data splits into four distinct "events" -- channel
profile + live status, VODs, clips, and stream schedule -- all served by
the *same* endpoint, the *same* auth (none), and the *same* client. This
actor follows the `mode` convention used across this portfolio (e.g.
`kyivpost-scraper`'s `article`/`latest`) rather than shipping 4 separate
actors, for three reasons:

1. **Same transport, same client, same recon** -- splitting into 4 actors
   would mean 4x the boilerplate (Dockerfile, client.py retry logic,
   proxy wiring) for zero technical benefit, since none of the 4 events
   need a different HTTP strategy.
2. **Matches the market's own shape.** `ACTOR_MARKET_RESEARCHER_NEW.md`
   (Babak 8) found the ~9-10 existing "Twitch scraper" competitors on
   Apify already bundle "streams/channels/clips/VODs" into one actor --
   buyers expect one Twitch actor that covers a channel, not four.
3. **One buying decision.** A user researching a streamer wants "give me
   everything about this channel," not four separate purchases.

## WAF

`gql.twitch.tv` (Twitch's own internal GraphQL API, used by every
logged-out visitor to twitch.tv) has **no WAF challenge of any kind**.
`curl_cffi` `chrome124` gets clean 200s on every query with just one
header: `Client-Id: kimne78kx3ncx6brgo4mv6wki5h1ko` -- the public web
client ID Twitch's own frontend ships to every anonymous browser tab (not
a secret, not something we extracted from a login session).

Queries are sent as **full inline query text** in the POST body (not
Twitch's persisted-query `sha256Hash` extension that the twitch.tv
frontend itself uses for its own internal optimization) -- this
sidesteps the hash-rotation problem entirely (see
`.ai/skills/graphql-doc-id-rotation.md`): there is no hash to discover or
refresh, ever. User-supplied values (`login`) are passed as GraphQL
**variables**, not string-interpolated into the query text -- both safer
(no injection risk from a login containing a quote character) and the
standard way to parameterize a GraphQL POST body.

## The one real wall found: `IntegrityCheckFailed` on deep pagination

`first: N` (N up to 100) on `videos`/`clips` works with zero friction --
confirmed 100 is the hard ceiling (`first: 101` returns a clean GraphQL
validation error, not a block). But requesting a **second page** via the
`after` cursor consistently returns:

```json
{"errors":[{"message":"failed integrity check","path":["user","videos"],
"extensions":{"code":"IntegrityCheckFailed"}}],
"extensions":{"challenge":{"type":"integrity"}}}
```

This is Twitch's device-attestation gate. It was NOT bypassed despite
trying every HTTP-only lever available:
- Fetching an anonymous `Client-Integrity` token from
  `https://gql.twitch.tv/integrity` (POST with `Client-Id` + a
  self-generated `X-Device-Id`) -- succeeds and returns a well-formed
  PASETO (`v4.local...`) token, but that token still fails the check on
  the follow-up paginated query.
- Warming up with a real page load first (`GET twitch.tv/<channel>`) to
  harvest a genuine `unique_id` cookie, then using that value as
  `X-Device-Id` -- same failure.
- Adding a matching `Client-Session-Id` header to both the integrity
  request and the GQL request -- same failure.

This matches the "genuinely unreproducible without a JS VM" category
documented in `.ai/lessons-learned.md` for Shopee `x-sap-sec` and
pre-X-Gnarly TikTok -- the real client-side integrity computation
almost certainly involves canvas/WebGL fingerprinting or timing signals
that only execute inside an actual browser JS engine. Per project
constraints (HTTP-only, no Playwright/Camoufox unless HTTP is *proven*
exhausted), this actor does **not** reach for a browser to chase 100
extra items per channel -- it caps at the first page (100 items max) and
is explicit about it:

- `videos`/`clips` records carry `_truncatedToFirstPage: true` whenever
  more items exist than were returned (via `pageInfo.hasNextPage` for
  videos, or a full page as a proxy signal for clips, which has no
  `pageInfo`/`totalCount` field at all -- confirmed absent during recon).
- `channelTotalVideoCount` is included on every video row so a consumer
  can see the true archive size even though only up to 100 rows come
  back.
- Documented here and in the input schema's `limit` field description,
  not silently dropped.

`schedule` mode was not observed to need `after` pagination at all in
testing -- `segments` returns the near-term (roughly 1-2 week) window in
a single response with no cursor argument found on the `schedule` field
itself.

## Field-shape discovery (error-probing, introspection disabled)

`gql.twitch.tv` returns `{"errors":[{"message":"GraphQL introspection is
disabled"}]}` for any `__type`/`__schema` query -- so every field name
below was found by the "iterate via server validation error" pattern in
`.ai/playbooks/reverse-engineer-internal-api.md` Step 7: send a guess,
read the "Cannot query field X on type Y" error, try the next guess.
Validation stops at the *first* invalid field in a selection set (not all
of them at once), so this took several rounds per type:

- **`ScheduleSegment`** does NOT have `startTime`/`endTime` (has
  `startAt`/`endAt` instead), does NOT have `isRecurring` (no working
  equivalent was found after trying `recurring`/`isRecurringEvent`/
  `recurrence`/`isReoccurring`/`isRepeating` -- omitted from output
  rather than guessed further), does NOT have `isCanceled` (American
  spelling; has `isCancelled`, British spelling), and does NOT have
  `category` (has `categories`, plural, a list).
- **`Schedule`** (the parent of `segments`) does NOT have a `vacation`
  field at the root, despite that being a real, documented Twitch UI
  concept (streamers can mark a vacation period) -- omitted.
- **`Tag`** (stream tags) errors if queried as a bare scalar --
  Twitch's validator requires an explicit subfield selection
  (`tags { id localizedName }`).
- **Not-found channel**: `user(login: "...")` for a nonexistent login
  returns `{"data":{"user":null}}` with **no `errors` array at all** --
  clean, easy to detect (`data.user is None`), no exception needed.

## Confirmed enum values (also found by error-probing; error messages do
not list valid members, so each candidate was tested individually)

| Enum | Confirmed valid | Tried and rejected |
|---|---|---|
| `VideoSort` | `TIME`, `VIEWS` | `TRENDING`, `RECENT`, `LATEST` |
| `BroadcastType` | `ARCHIVE`, `HIGHLIGHT`, `UPLOAD`, `PAST_PREMIERE`, `PREMIERE_UPLOAD` | (all 5 guesses succeeded) |
| `ClipsPeriod` | `LAST_DAY`, `LAST_WEEK`, `LAST_MONTH`, `ALL_TIME` | `LAST_YEAR` (server error, not a clean "invalid enum" rejection -- treated as unsupported) |
| `ClipsSort` | `VIEWS_DESC`, `TRENDING` | `RECENT` (invalid enum), `CREATED_AT_DESC` (server error) |

## Data sources (all `S1-gql`, no fallback)

Per `.ai/skills/multi-strategy-fallback.md`'s own note for this platform
("Twitch internal GQL → only one path"), there is intentionally no S2
fallback -- documented here so a reviewer knows it's a deliberate
single-strategy design, not an oversight.

### 1. `channel` mode
`user(login) { id login displayName description createdAt
profileImageURL(width:300) bannerImageURL primaryColorHex
followers{totalCount} stream{...} lastBroadcast{...} }`. `stream` is
`null` when the channel is offline -- `isLive` in the output is derived
from `stream is not None`, not a separate upstream field.

### 2. `videos` mode
`user(login) { videos(first, sort, type) { totalCount pageInfo{hasNextPage}
edges{node{...}} } }`. Single page only (see integrity-wall section
above). `url` is constructed (`https://www.twitch.tv/videos/<id>`) since
the GraphQL response does not include a direct URL field for videos.

### 3. `clips` mode
`user(login) { clips(first, criteria:{period, sort}) { edges{node{...}} } }`.
No `totalCount`/`pageInfo` field exists on this connection at all
(confirmed by omission -- not an error, just absent from every sampled
response) -- `_truncatedToFirstPage` here is a heuristic (`len(edges) >=
requested_first`), not a hard signal like `videos` has.

### 4. `schedule` mode
`user(login) { channel { schedule { segments{...} nextSegment{id} } } }`.
A channel with no configured schedule returns `schedule: null` -- treated
as a legitimate empty result (0 rows returned), not an error.

## Known limits

- Deep pagination (page 2+) is blocked platform-side for HTTP-only
  clients -- `videos`/`clips` modes return at most 100 items per run,
  always the most-recent (or most-viewed, depending on `sort`/`clipsSort`)
  ones, never the full archive on channels with more than 100.
- No `isRecurring`-equivalent field was found for schedule segments after
  6 candidate guesses -- omitted from output rather than left wrong.
- `schedule.vacation` (a real Twitch UI feature) has no working GraphQL
  field found -- omitted.
- Chat, followed-channels-of-a-user, and raw HLS stream URLs are
  out of scope for this actor (chat is a WebSocket/IRC protocol, not
  HTTP; stream ripping is outside "public metadata" scope per project
  constraints).

## Diff cadence

Quarterly smoke test recommended. If `videos`/`clips`/`schedule` modes
start returning `GraphQL error(s)` (raised as `RuntimeError`, not
swallowed), re-run the field-shape discovery process in this file's
"Field-shape discovery" section against the live schema before assuming
a queries rewrite is needed.
