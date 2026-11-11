# Bluesky Scraper

Scrape Bluesky (AT Protocol) without an account, an app password, or an
API key. One actor, 15 modes, one consistent output envelope.

Built on Bluesky's own public AppView (`public.api.bsky.app`) — the same
XRPC API the bsky.app web client calls. No login, no browser, no
CAPTCHA solving.

## Modes

Pick a `mode`, then fill the one input list it reads.

### Account modes — read **Bluesky accounts** (`actors`)

Accepts a handle (`bsky.app`), an `@handle`, a DID (`did:plc:…`), or a
profile URL (`https://bsky.app/profile/bsky.app`) — mixed freely in one
list.

| Mode | Emits | Notes |
| --- | --- | --- |
| `profile` | `PROFILE` | Full account detail: bio, avatar, banner, follower/following/post counts, verification, pinned post. Batched 25 accounts per request. |
| `posts` | `POST` | An account's timeline. Filter with `postFilter` (replies / media only / video only). |
| `followers` | `FOLLOWER` | Who follows the account. |
| `follows` | `FOLLOWING` | Who the account follows. |
| `lists` | `LIST` | Curation and moderation lists the account created. |
| `starter-packs` | `STARTER_PACK` | Starter packs the account created. |

### Post modes — read **Post URLs** (`postUrls`)

Accepts `https://bsky.app/profile/<handle>/post/<rkey>` or a raw `at://`
URI.

| Mode | Emits | Notes |
| --- | --- | --- |
| `post-detail` | `POST` + `REPLY` | The post plus its reply thread. `threadDepth` controls how deep; replies come back flat with a `replyDepth` field so the tree stays reconstructable. `parentHeight` pulls in ancestors. |
| `post-likes` | `LIKE` | Which accounts liked the post, with timestamps. |
| `post-reposts` | `REPOSTED_BY` | Which accounts reposted it. |
| `post-quotes` | `QUOTE` | Posts that quote it, as full post records. |

### Search modes — read **Search queries** (`searchQueries`)

| Mode | Emits | Notes |
| --- | --- | --- |
| `search-posts` | `POST` | Full-text post search. Filter by `sort`, `since`, `until`, `lang`, `author`, `mentions`, `domain`, `url`, `tag`. **Read the rate-limit note below.** |
| `search-users` | `PROFILE` | Account search. |

### Feed mode — reads **Feed / list URLs** (`feedUrls`)

| Mode | Emits | Notes |
| --- | --- | --- |
| `feed` | `POST` | Posts from a custom feed (`/profile/<did>/feed/<rkey>`) or a list (`/profile/<did>/lists/<rkey>`). The two are told apart automatically. |

### Discovery modes — need no input at all

| Mode | Emits | Notes |
| --- | --- | --- |
| `trends` | `TREND` | What is trending now: topic, category, post count, start time, sample accounts. |
| `popular-feeds` | `FEED_GENERATOR` | The most-liked custom feeds on the network. |

## Output

Every record carries the portfolio envelope, then the upstream payload
**verbatim** — field names are never renamed, so a `POST` record is a
literal `app.bsky.feed.defs#postView` and a `PROFILE` record is a
`app.bsky.actor.defs#profileViewDetailed`.

```json
{
  "_input": "bsky.app",
  "_source": "S1-xrpc",
  "_scrapedAt": "2026-08-29T01:14:13Z",
  "recordType": "POST",
  "uri": "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.post/3mu3jzayuys2k",
  "cid": "bafyreiduk5omcv2kkdmv24nvslkgs65uxpino6ftvukqkkc32qwvzqokzu",
  "author": { "did": "…", "handle": "bsky.app", "displayName": "Bluesky", "…": "…" },
  "record": { "$type": "app.bsky.feed.post", "text": "…", "createdAt": "…", "facets": [], "…": "…" },
  "embed": { "$type": "app.bsky.embed.images#view", "images": [] },
  "replyCount": 42, "repostCount": 17, "likeCount": 310, "quoteCount": 4,
  "webUrl": "https://bsky.app/profile/bsky.app/post/3mu3jzayuys2k"
}
```

Two fields are added by this actor rather than passed through:
`webUrl` (the human-facing permalink) and `replyDepth` (on `REPLY`
records only).

Split mixed output with `recordType`. `_input` always echoes the exact
string you supplied, so results join back to inputs even when you mixed
URLs, handles and DIDs in one list.

### Failures produce rows too

A run never silently drops an input. Failed inputs get a row with
`recordType: "ERROR"` and no payload:

| `_error` | Meaning |
| --- | --- |
| `not_found` | The account, post or thread does not exist (or was deleted). |
| `empty_result` | Upstream returned zero items — e.g. a post with no likes. |
| `bad_input_or_shape` | The input was not the shape the mode needs (e.g. a profile URL passed to a post mode). |
| `rate_limited` | `search-posts` hit the IP limit and had no proxy to rotate to. |
| `invalid_request` | Upstream rejected the parameters. |
| `auth_required` | The endpoint needs a login — out of scope for this actor. |
| `exception` | Anything else, with the repr attached. |

## Limits and gotchas

**`search-posts` is rate-limited per IP.** It is the one endpoint
Bluesky does not serve from the open AppView, and its host applies a
token bucket of roughly 5 requests before returning HTTP 403 for a
minute or more. Retrying eagerly makes it worse — measured, a 300 s rest
after a retry storm still returned zero tokens.

- **With Apify Proxy on (the default): the actor rotates to a fresh exit
  IP on each block, which is a fresh bucket.** Leave the proxy enabled
  for this mode.
- Without a proxy the actor paces itself to ~1 request per 20 s, waits
  90 s on a block, and after two waits gives up with a `rate_limited`
  row rather than hammering.
- `search-posts` is forced to concurrency 1 — parallel workers share one
  IP and only drain the bucket faster.

Every other mode is unaffected and needs no proxy at all: the public
AppView absorbed a 30× burst at `limit=100` without a single failure.

**Not available without a login** (so, not offered here): your home
timeline, an account's own likes, DMs, notifications, and follow
suggestions. These are private or session-scoped in Bluesky itself.

**Counts are point-in-time.** `likeCount`, `followersCount` and friends
are whatever the AppView had indexed at `_scrapedAt`.

**`maxItems` is per input item**, not per run. Three accounts at
`maxItems: 100` yields up to 300 rows.

**`trends` caps at 25** regardless of `maxItems` — that is Bluesky's own
limit on the endpoint, not a choice made here.

## Technical notes

- **No WAF.** Plain `httpx` returns 200; so does every `curl_cffi`
  profile tried. `chrome124` is pinned for portfolio consistency, not as
  a bypass — do not waste time rotating profiles against this target.
- **Pagination** is cursor-based with a hard `limit` cap of 100, and
  stops on any of: cursor absent, empty page, repeated cursor, or
  `maxItems` reached. Verified duplicate-free across 6 pages / 520
  records.
- **Handle-based `at://` URIs are resolved to DIDs before use.** This is
  not cosmetic: `getLikes`, `getQuotes` and `getPosts` return **HTTP 200
  with an empty array**, and `getRepostedBy` returns HTTP 500, when the
  URI authority is a handle instead of a DID. Since every bsky.app post
  URL is handle-based, skipping this produces silently empty datasets.

Full recon evidence, including the endpoint census and the rate-limit
measurements, is in [CRAWLING_METHOD.md](CRAWLING_METHOD.md).

## Local development

```bash
pip install -r requirements.txt

python test_local.py             # smoke-test all 15 modes
python test_local.py posts bsky.app

# Full Apify lifecycle against local storage:
#   put your input in storage/key_value_stores/default/INPUT.json
APIFY_LOCAL_STORAGE_DIR=./storage python -m src
```

`test_local.py` audits the envelope on every row and flags any mode that
returns zero records — a mode answering `200 OK` with nothing is treated
as a failure, not a pass.
