# Crawling method — Bluesky (AT Protocol)

Recon date: **2026-08-29**. Everything below was measured, not assumed.

## 1. There is no WAF

Bluesky's AppView is a documented, open, unauthenticated JSON API. The
whole TLS-fingerprint ladder came back identical on the same IP:

| Client | `app.bsky.actor.getProfile?actor=bsky.app` |
| --- | --- |
| `httpx` (no impersonation) | `200` |
| `curl_cffi` chrome124 | `200` |
| `curl_cffi` chrome131 | `200` |
| `curl_cffi` safari17_0 | `200` |
| `curl_cffi` firefox133 | `200` |
| `primp` | `200` |

No Cloudflare, no DataDome, no PerimeterX, no challenge body, no cookie
bootstrap, no token harvest. `public.api.bsky.app` sits behind BunnyCDN
with `cache-control: public, max-age=30`.

**Do not rotate TLS profiles here.** `chrome124` is pinned purely for
portfolio consistency. If a request fails, the cause is upstream load or
a bad parameter — never a fingerprint.

## 2. Hosts

| Host | Use |
| --- | --- |
| `public.api.bsky.app` | Everything except post search. Effectively unthrottled: a 30× burst at `limit=100` returned 30× `200`. |
| `api.bsky.app` | **Only** `app.bsky.feed.searchPosts`. |
| `plc.directory` | Not used by the actor; used during recon to map a DID to its PDS. |

`public.api.bsky.app` returns a **BunnyCDN HTML `403`** for the
`searchPosts` path specifically, regardless of headers — it is a
path-level CDN rule, not a bot check. `api.bsky.app` serves that method.

## 3. The one real rate limit

`app.bsky.feed.searchPosts` on `api.bsky.app` is behind an nginx per-IP
bucket. Measured behaviour:

| Test | Result |
| --- | --- |
| Fresh IP, burst of 8 | `200 ×5` then `403` |
| Paced 1 req / 3 s, 8 novel queries | `200 ×5` then `403` — pacing does **not** help |
| Blocked, retry at +60 s | `200` (one token back) |
| Blocked, rest 120 s, burst of 8 | `200 ×7` then `403` |
| Blocked again, rest 180 s, burst of 8 | `200 ×0` |
| Blocked again, rest 300 s, burst of 8 | `200 ×0` |
| After a day of recon on one IP, rest 420 s, **single** request | `403` |

Two conclusions:

1. It is a **token bucket on request count**, not a requests-per-second
   limiter — spacing requests out does not buy extra calls.
2. **Hammering while blocked extends the penalty, and the penalty
   accumulates over a long horizon.** A 180 s rest returned zero tokens
   where a 120 s rest had returned seven; by the end of recon, a single
   request after 420 s of total silence was still refused. So the retry
   path must be patient, not eager — and on a heavily-used IP, patience
   alone stops working. Rotating the exit IP is the only durable fix.

The block is scoped tightly: while `searchPosts` was `403`, `getProfile`
and `getAuthorFeed` on the *same host* and the *same session* both kept
returning `200`.

**Actor response:** rotate to a fresh exit IP on `403` (a new IP is a new
bucket), and only when no proxy is configured fall back to a long
`SEARCH_BLOCK_COOLDOWN` wait. `search-posts` is also forced to
concurrency 1 — parallel workers share one IP and just drain the bucket
faster.

## 4. The handle-vs-DID trap (the important one)

An `at://` URI can name its author by handle or by DID. They are **not**
interchangeable across methods. Same post, same rkey:

| Method | `at://bsky.app/...` | `at://did:plc:z72i.../...` |
| --- | --- | --- |
| `getPostThread` | `200`, thread object | `200`, thread object |
| `getLikes` | `200`, **`likes: []`** | `200`, `likes: 5` |
| `getQuotes` | `200`, **`posts: []`** | `200`, `posts: 5` |
| `getPosts` | `200`, **`posts: []`** | `200`, `posts: 1` |
| `getRepostedBy` | **`500`** InternalServerError | `200`, `repostedBy: 3` |

Three of those are **HTTP 200 with a silently empty array** — the exact
failure class that corrupts datasets without anyone noticing, because
"this post has no likes" and "you passed the wrong URI shape" look
identical downstream.

Since users paste `https://bsky.app/profile/<handle>/post/<rkey>` URLs,
the naive parse produces exactly the broken handle-based form. The actor
therefore resolves every post-shaped URI to its DID form via
`com.atproto.identity.resolveHandle` (memoised per run) before calling
any of these methods. See `BlueskyClient.resolve_did`.

This was caught by the local test harness auditing for zero-row modes,
not by reading docs — a mode that returns `200 OK` and no rows is a
finding, not a pass.

## 5. Pagination

Every collection method uses the same idiom: `limit` + an opaque
`cursor`, with the next cursor in the response body.

- `limit` caps at **100** everywhere; `101` → `400 InvalidRequest`.
- `getProfiles` / `getPosts` take an array of up to **25** identifiers;
  `26` → `400`.
- Cursor format varies by method (`getAuthorFeed` returns a timestamp,
  `getFollowers` an rkey) — treat it as opaque.
- Three pages of `getAuthorFeed` and `getFollowers` produced zero
  duplicate records.

`searchPosts` participates in the same contract: page 1 at `limit=100`
returned 100 posts, `hitsTotal: 10000`, and a well-formed opaque cursor
(base64 of `{"s":[<timestamp>, <did>, <rkey>]}`).

**Caveat, stated plainly:** the page-2 fetch using that cursor could not
be executed from the recon machine — by then its IP was refusing even a
single search request after 420 s of silence (§3), and no Apify proxy
password was available locally to rotate away from it. What is verified
is that `searchPosts` returns a cursor, and that `paginate` consumes
cursors correctly (520 records over 6 pages, zero duplicates, on
`getFollowers`). The untested combination is specifically those two
together. Confirm on the first cloud run with RESIDENTIAL enabled.

`BlueskyClient.paginate` stops on **any** of: cursor absent, empty page,
repeated cursor, or `maxItems` reached. The repeated-cursor guard exists
because a method that returns a stable cursor forever would otherwise
spin the actor indefinitely.

## 6. What is NOT reachable without login

| Method | Status |
| --- | --- |
| `app.bsky.feed.getTimeline` | `401 AuthMissing` |
| `app.bsky.feed.getActorLikes` | `400` — an account's own likes are private |
| `app.bsky.actor.getSuggestions` | `200` but empty without a session |
| `chat.bsky.*` | Auth-only DMs |
| `com.atproto.repo.*`, `com.atproto.sync.*` | `501 MethodNotImplemented` on the AppView |

All out of scope under the project's public-data / no-login constraint.

Note `com.atproto.repo.listRecords`, `describeRepo`, `getRecord` and
`sync.listBlobs` **do** work anonymously — but on the account's own
**PDS** (resolved from its DID document via `plc.directory`), not on the
AppView. That surface exposes raw un-hydrated records including an
account's own like and follow records. It is deliberately not wired into
this actor: it needs a per-account PDS lookup, returns a different
(un-hydrated) shape that would break the envelope's consistency, and
duplicates data the AppView already serves in richer form. It is the
obvious next mode if raw-repo access is ever wanted.

## 7. Endpoint census

Probed 34 methods anonymously; **28 returned usable data**. The 15 modes
this actor ships cover every one that yields a distinct record type. The
remainder were either auth-walled (§6) or redundant
(`searchActorsTypeahead` duplicates `searchActors`,
`getTrendingTopics` is a thinner `getTrends`, `getSuggestedFeeds`
returns the same payload as `getPopularFeedGenerators`,
`getRelationships` needs a viewer context to mean anything).
