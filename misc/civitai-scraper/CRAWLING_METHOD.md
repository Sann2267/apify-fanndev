# Crawling Method — Civitai Scraper

**Last verified:** 2026-08-26

## Architecture decision: one multi-mode actor, not five

Civitai's public data splits into five "events" -- model search, model
detail, image gallery, creators, and tags -- but all five are served by
Civitai's own **official, documented, public REST API** at
`civitai.com/api/v1/*`, the same base URL, the same (no) auth, and the
same client. Following the same reasoning already applied to
`twitch-channel-scraper` in this portfolio: one actor with a `mode`
input beats five actors that would each duplicate the same Dockerfile,
retry/backoff client, and proxy wiring for zero technical benefit. A user
researching a model wants "give me everything about Civitai," not five
separate purchases.

## WAF

**None.** `civitai.com/api/v1` is not a reverse-engineered internal
API -- it's Civitai's own documented, versioned, public REST API,
intended for exactly this kind of external consumption. `curl_cffi`
`chrome124` gets clean 200s on every endpoint (`/models`, `/models/{id}`,
`/images`, `/creators`, `/tags`) with nothing but an `Accept:
application/json` header -- no login, no API key, no cookies. 15 rapid
sequential requests hit zero rate-limiting (all 200s, ~0.3s/request).

Query-param validation uses Zod, and its 400 error bodies are unusually
generous: they list **every valid enum member directly** in the message
(e.g. `"values": ["Highest Rated", "Most Downloaded", ...]`). Every enum
whitelist in `src/constants.py` was confirmed this way -- send a bogus
value, read the list back, no guessing needed (a much easier discovery
process than the error-probing needed for Twitch's undocumented internal
GraphQL schema in this same portfolio).

## Pagination

Both cursor-based connections (`/models`, `/images`, params like
`cursor=3|1719470081918`) and page-based connections (`/creators`,
`/tags`, params like `page=2`) use the **same response field name**,
`metadata.nextPage` -- a ready-to-fetch full URL. `src/client.py`'s
`paginate()` method exploits this: it doesn't need to know which style a
given endpoint uses, it just follows `metadata.nextPage` until either the
field is absent (list exhausted) or the caller's `max_items` cap is hit.
Confirmed no overlap between page 1 and page 2 items on `/models`
(different, non-overlapping ID sets).

`limit` (page size) is capped by the platform at **100** -- confirmed
live: `limit=100` returns 100 items, `limit=101`/`200`/`500` all return a
400 ZodError. `max_items` in this actor's input can go higher (up to
10,000) and the pagination loop transparently makes as many requests as
needed to reach it.

## Real bug found: `/images?modelId=X` is broken upstream

`/images` accepts a `modelId` query param without any validation error
(200 OK), but it **consistently returns `{"items":[],"metadata":{}}`** --
confirmed on `4201` (Realistic Vision, millions of gallery images) and
`257749` (Pony Diffusion V6 XL, one of the single most-used checkpoints
on the entire platform) across multiple repeated requests, several
minutes apart. This is not a rate-limit or transient blip -- it is a
consistent, reproducible empty result for a filter that Civitai's own
API happily accepts as valid.

The root cause is visible in the image object's own shape: every image
returned by `/images` carries `modelVersionIds` (plural, a list) --
there is **no `modelId` field on an image at all**. Images are indexed
by model *version*, not by model. `/images?modelVersionId=X` was tested
against the same models and works reliably and consistently (`5/5`,
`5/5`, `5/5` across three repeated calls).

**Fix implemented** (`src/main.py`, `_resolve_model_version_ids`): when
`images` mode is given a `modelId` (rather than a `modelVersionId`), the
actor first calls `GET /models/{modelId}` to enumerate every version ID,
then queries `/images?modelVersionId=<id>` once per version, merging
results until `maxItems` is reached. This is slightly more expensive
(N+1 requests instead of 1) but returns real data instead of a silently
empty result — consistent with this portfolio's "no silent failure"
convention. `modelVersionId` is still accepted directly and is the
cheaper, single-request path when the caller already knows the exact
version they want.

## Known, deliberate restriction: `meta` is always null

The public/unauthenticated `/images` endpoint always returns `"meta":
null` for every image, regardless of the image's own `hasMeta`/
`hasPositivePrompt` boolean flags seen elsewhere (e.g. inside a model
version's `images` array, where `hasMeta: true` is visible per-image but
the actual prompt/sampler/seed/cfgScale values are never included even
there). This was confirmed on 50 sampled images across `sort=Newest` and
on 5 images filtered by a specific `modelVersionId` -- 0/55 had non-null
`meta`. This reads as a deliberate Civitai privacy choice (many users
don't want their exact prompts scraped), not a shape change or bug on
our end, and is not routed around (no login/account flow is in scope per
project constraints).

## Data sources (all `S1-api`, no fallback needed)

There is no S2 fallback because there is nothing to fall back from --
this is the one documented, stable, official API surface for all five
modes.

### 1. `models` mode
`GET /models` with optional `query`/`tag`/`username`/`types`/`sort`/
`period`/`nsfw`. Each list item is the **full** model object already --
`modelVersions` (with `files`, `hashes`, `downloadUrl`, `images`) is
present on list items, not just on the single-model detail endpoint
(confirmed by comparing key sets side by side -- identical).

### 2. `model-detail` mode
`GET /models/{id}`. Same full shape as a `models`-mode list item. A
genuinely nonexistent ID returns a clean `404` with
`{"error":"No model with id <id>"}` (confirmed distinct from the 400
`ZodError` returned for a syntactically invalid ID, e.g. a string or a
number `> 2147483647` -- both are handled, but as different error kinds:
`model_not_found` vs `invalid_request`).

### 3. `images` mode
`GET /images` with optional `modelVersionId`/`username`/`postId`/`sort`/
`period`/`nsfw` (see the `modelId` bug section above for why `modelId`
is resolved client-side rather than sent as-is).

### 4. `creators` mode
`GET /creators` with optional `query`. Page-based pagination
(`metadata.currentPage`/`totalPages`/`nextPage`).

### 5. `tags` mode
`GET /tags` with optional `query`. Same page-based pagination style as
`creators`.

## Known limits

- `meta` (prompt/sampler/seed/steps/cfgScale) is never available via the
  public API -- see above. If prompt-level data is a hard requirement,
  it is out of scope for this actor (would need an authenticated,
  presumably per-own-image-only, API key flow, which is out of scope per
  project's "No Login" constraint).
- `/images?modelId=X` is resolved via an extra `/models/{id}` lookup
  plus one `/images` call per model version -- for a model with many
  versions this is more requests than a single filtered call would be,
  but it is the only way to get correct (non-empty) results.
- No model-version-by-hash or single-model-version-by-id endpoints are
  wired up in this actor (`/model-versions/{id}`,
  `/model-versions/by-hash/{hash}`) -- `model-detail` mode's full
  `modelVersions` array covers the common case; these could be added as
  a future mode if a use case needs an exact version lookup by SHA256.

## Diff cadence

Quarterly smoke test recommended. If any mode starts returning HTTP 400s
that weren't there before, the Zod error message will name the exact
invalid param/enum -- update `src/constants.py`'s whitelist accordingly
rather than guessing.
