# Crawling method — Instagram public content

Recon date: **2026-09-11**. Every claim below was measured live and anonymously,
from a single residential-grade IP, with no login at any point.

## The finding that shapes this actor: the public REST API is closed

Instagram's `/api/v1/...` web API — the one nearly every Instagram scraper and
tutorial is built on — no longer serves anonymous callers. It answers **HTTP
401**:

```json
{"message":"Please wait a few minutes before you try again.",
 "require_login":true,"igweb_rollout":true,"status":"fail"}
```

| Endpoint | Anonymous result |
| --- | --- |
| `/api/v1/users/web_profile_info/?username=` | 401 |
| `/api/v1/users/<id>/info/` | 401 |
| `/api/v1/feed/user/<id>/` | 401 |
| `/api/v1/tags/web_info/?tag_name=` | 401 |
| `/api/v1/locations/web_info/` | 401 |
| `/api/v1/web/search/topsearch/` | 401 |
| `/api/v1/highlights/<id>/highlights_tray/` | 401 |
| `/api/v1/friendships/<id>/following/` | 401 |
| `/api/v1/media/<id>/comments/` | 401 |

**This is not a WAF and not a fingerprint gate.** The response is byte-identical
across `chrome124`, `safari17_0`, `firefox133`, `edge101` and
`chrome99_android` on the same IP — five TLS profiles, one answer. There is no
Cloudflare, DataDome, PerimeterX or Akamai in the path. The `igweb_rollout`
flag names it for what it is: an application-level auth rollout. No JA3/JA4
work, header ordering or cookie trick reopens it, so this actor does not spend
a request trying.

The previous actor in this portfolio (`instagram-merchant-profile-scraper`,
built 2026-09-01) is built on `web_profile_info` and is affected by this change.

## What is still open: the logged-out SSR Relay surface

Instagram server-renders a **logged-out** variant of its own GraphQL queries
into the page HTML. The preloader payload is self-describing — it ships the
query id *and* the exact variables right next to the data:

```json
{"queryID":"27553725110923321",
 "variables":{"first":12,"username":"nasa"},
 "queryName":"PolarisLoggedOutDesktopWWWProfilePostsTabContentQuery"}
```

So the flow is **warm → harvest → replay**:

1. Warm the entity page. It sets `csrftoken`/`ig_did`/`datr`, carries page 1 of
   the data, and carries the query id needed for page 2. The warm-up is never a
   wasted request — it *is* the page-1 fetch.
2. Harvest `lsd`, `queryID` and `variables` out of that HTML.
3. Replay `POST /api/graphql/` for pages 2..n.

**This sidesteps persisted-query rot entirely.** The usual `doc_id` problem —
ids rotate every 2–4 weeks, so you cache and refresh on the first 400 — does
not apply, because the id is read from the page being scraped. A Meta redeploy
is picked up on the next request. There is nothing pinned and nothing to
refresh.

### The endpoint trap

Replays must go to **`/api/graphql/`**. The widely documented `/graphql/query`
accepts the identical body and answers **200 OK** with `{"data":{"<root>":null}}`.

Measured side by side, same form fields, same session:

| Endpoint | Result |
| --- | --- |
| `/api/graphql/` | 200, 18 072 bytes, **12 edges** |
| `/graphql/query` | 200, 174 bytes, `xig_user_by_username: null` |

A status-only health check calls the second one a pass. `client.graphql()`
therefore takes the expected root key and treats a null root as a block, not as
an empty result.

### Minimal request

Reduced field by field from the full 23-field Relay form body. All that is
actually required is a warm cookie jar plus:

```
POST /api/graphql/
Content-Type: application/x-www-form-urlencoded

variables=<json>&doc_id=<queryID>&lsd=<token>
```

Dropping `lsd` is the one thing that breaks it — the response becomes a 626 KB
login page. `X-IG-App-ID`, `X-CSRFToken`, `X-FB-Friendly-Name`, `X-ASBD-ID`,
`X-Root-Field-Name`, `X-IG-WWW-Claim`, `jazoest`, `__hs`, `__rev`, `__spin_*`
and the rest are all optional. They are sent anyway, because matching the real
client costs nothing and reduces the chance of being singled out.

## Surface inventory

| Surface | Route | Relay root | Pagination |
| --- | --- | --- | --- |
| Profile | `/<user>/` | `xig_user_by_username` | n/a |
| Profile posts | `/<user>/` | `polaris_ordered_timeline_connection` | ✅ cursor, unlimited |
| Profile reels | `/<user>/reels/` | `polaris_clips_connection` | ✅ cursor, unlimited |
| Post / reel | `/p/<code>/`, `/reel/<code>/` | `xig_polaris_media` | comments capped |
| Location | `/explore/locations/<id>/` | `xdt_location_get_web_info(_tab)` | ❌ single page |

**Login-walled, therefore not offered as modes** — these serve the
`CAAFetaIGLoginHomepageQuery` sign-in payload instead of content:
`/explore/tags/<tag>/`, `/<user>/tagged/`, `/explore/search/keyword/`.
`/reels/audio/<id>/` renders but carries no Relay data at all.

### The same media, four different widths

This is the single most important thing to understand about the output, because
it decides what a consumer can compute:

| Surface | Engagement | Caption | `taken_at` | Video file |
| --- | --- | --- | --- | --- |
| Profile grid | ❌ | ✅ | ❌ | ❌ |
| Reels tab | ✅ likes, comments, **plays** | ❌ | ❌ | ❌ |
| Post detail | ✅ | ✅ | ✅ | ✅ |
| Location tab | ✅ | ✅ | ✅ | ✅ (69 fields — the widest) |

A missing count is emitted as **null, never 0**. Writing 0 for "this surface
does not publish likes" silently corrupts any average computed downstream, so
each affected row also carries a `_warning` naming the limitation and the mode
that does publish the field.

## Verified limits

- **Comments cap at what the post page ships** (13–15 observed, against posts
  with 1 039 and 4 218 comments). The post query accepts an `after` cursor and
  reports `has_next_page: true`, then returns the same first page forever —
  tested to 4 pages, 0 new comments. Real comment paging runs through
  `/api/v1/media/<id>/comments/`, which is 401. Not recoverable anonymously.
- **The location tab ignores its cursor.** Passing `after` returns HTTP 200
  with zero edges. One shot per place: **63 media on `recent`, 27 on `ranked`**.
- **`page_size_override` is a cap, not a hint.** The preloaded location
  variables carry `page_size_override: 6`; replaying them verbatim returns 6
  media. Dropping the key from the variables returns 60+. The actor strips it.
- **Highlights are titles and covers only.** Their contents need a login.
- **Instagram CDN URLs are signed and expire.** Download media promptly.

## Failure modes and how they are told apart

Instagram answers with HTTP 200 for almost everything, so status codes are
nearly useless here and every check matches the body.

| Situation | Signal | Mapped to |
| --- | --- | --- |
| Account/post does not exist | 200 + `PolarisErrorRoot`, no data root | `NOT_FOUND` |
| Throttled, or a login-walled route | 200 + `caa_login_form_data` / `CAAFetaIGLoginHomepageQuery` | rotate, then `BLOCKED_AFTER_RETRIES` |
| Private account | `is_private: true` on the profile payload | `PRIVATE_ACCOUNT` |
| Post withheld from logged-out viewers | `if_not_gated_logged_out` absent | `GATED_FOR_LOGGED_OUT` |
| Meta moved the payload | data root present but expected key missing | `UPSTREAM_SHAPE_CHANGED` |

Two of these cost a debugging round and are worth flagging to anyone extending
this:

- The literal string `"404"` appears in **healthy** pages too. It is not a
  not-found signal. `PolarisErrorRoot` is.
- `PolarisLoggedOut` appears on genuine pages **and** on the login wall. Using
  it as a "this is real content" marker made the block detector answer *False*
  for actual walls, which would have fed sign-in pages to the parser and
  reported them as schema changes. Only the data-root names
  (`xig_user_by_username`, `xig_polaris_media`, `xdt_location_get_web_info`)
  are safe as content markers.

## Rate limiting

Anonymous access is throttled **per IP**, and Instagram signals it with a 200
carrying a login wall rather than a 429. Throttling is partial and
account-specific rather than an outright ban — during recon a burst produced
empty payloads for some accounts while others kept working from the same IP.

Consequences baked in: targets are fetched sequentially with a delay,
a block rotates both the TLS profile and the proxy session, and residential
proxy is marked strongly recommended rather than optional. The TLS ladder
exists to vary the fingerprint after a throttle — not to defeat a JA3
blocklist, because as established above there is no TLS gate here at all.
