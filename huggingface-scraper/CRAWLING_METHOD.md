# Crawling Method — Hugging Face Scraper

**Last verified:** 2026-08-26

## Architecture decision: one multi-mode actor, not seven

Hugging Face's public data splits into three parallel entity types
(models, datasets, Spaces) each with a search/list view and a full-detail
view, plus a seventh event (user/organization profiles) — but all seven
are served by Hugging Face's own **official, documented, public REST
API** at `huggingface.co/api/*`, the same base URL, the same (no) auth,
the same client. This follows the same reasoning already applied to
`twitch-channel-scraper` and `civitai-scraper` in this portfolio: one
actor with a `mode` input beats seven actors duplicating the same
Dockerfile/retry-client/proxy wiring for zero technical benefit.

Granular per-entity modes (`models`/`model-detail`/`datasets`/
`dataset-detail`/`spaces`/`space-detail`/`creator`) were chosen over a
single generic `mode=search`+`entityType` combo, matching the
`civitai-scraper` convention: each mode is independently discoverable in
the Apify Console's mode dropdown, and the input schema fields relevant
to each mode are self-documenting per-mode rather than requiring a
two-select combination to understand.

## WAF

**None.** `huggingface.co/api` is Hugging Face's own documented,
versioned, public REST API — not a reverse-engineered internal one, and
explicitly intended for exactly this kind of external consumption
(the Hugging Face Hub Python client library itself uses this same API).
`curl_cffi` `chrome124` gets clean 200s on every endpoint (`/models`,
`/models/{id}`, `/datasets`, `/datasets/{id}`, `/spaces`, `/spaces/{id}`,
`/users/{username}/overview`, `/organizations/{name}/overview`) with
nothing but an `Accept: application/json` header — no login, no API key,
no cookies.

## Pagination: standard HTTP `Link` header, NOT a JSON field

Unlike Civitai (`metadata.nextPage` in the JSON body), Hugging Face uses
the same convention GitHub's REST API uses: a `Link` response header,
e.g. `<https://huggingface.co/api/models?limit=2&cursor=...>;
rel="next"`. Confirmed live via raw header inspection. `src/client.py`'s
`paginate()` parses this with a small regex (`parse_next_link`) rather
than assuming a JSON pagination field exists — this is the one place
this actor's plumbing differs structurally from `civitai-scraper`'s.

## Rate limit (respected, not just documented)

Response headers on every request confirm: `ratelimit-policy: "fixed
window";"api";q=500;w=300` — 500 requests per 300-second window for
anonymous (no API key) access. `src/client.py`'s retry logic treats HTTP
429 as retryable and honors a `Retry-After` header if present, falling
back to the standard exponential backoff otherwise.

## Real quirk found #1: nonexistent repo returns 401, not 404

`GET /models/{id}`, `/datasets/{id}`, and `/spaces/{id}` all return
**HTTP 401** (`{"error":"Invalid username or password."}`) for a
repo that does not exist — confirmed on three separate cases: a real
namespace with a fake model name, a fully-fake single-segment name, and
a fake dataset name, all three producing byte-identical 401 bodies. This
reads as a deliberate privacy-preserving design: a 401 is indistinguishable
from "this repo exists but is private and you're not authorized to see
it," which prevents using this endpoint to enumerate private repos by
elimination. Since this actor never sends any credentials, **every 401
on a repo-detail lookup is treated as `<entity>_not_found`**, not a real
authentication failure (`src/client.py`'s `get_repo_detail_json` handles
401 and 404 identically via the `NotFound` exception).

This is the opposite convention from `/users/{username}/overview` and
`/organizations/{name}/overview`, which DO return a clean, unambiguous
**404** with `{"error":"This user does not exist"}` (or, seen on a
different sample, `{"error":"Sorry, we can't find the page you are
looking for."}`) for a genuinely nonexistent account — no privacy
ambiguity needed there since profile existence isn't sensitive the same
way repo existence can be. `get_repo_json` (used for creator mode) only
treats 404 as not-found, matching this different real-world behavior.

## Real quirk found #2: users and organizations are different endpoints

There is no single unified "account" lookup. An individual user lives at
`/api/users/{username}/overview`; an organization lives at
`/api/organizations/{name}/overview` — querying the wrong one 404s even
for an account that definitely exists (confirmed: `openai` 404s on the
`/users/` path since it's an organization, then 200s cleanly on
`/organizations/`). `creator` mode's default `accountType: "auto"` tries
`/users/` first and falls back to `/organizations/` on a 404, so callers
don't need to know in advance which type an account is.

## Real quirk found #3: ascending sort is only supported for `createdAt`

`direction=1` (ascending) returns a clean 400
(`{"error":"Invalid sort direction, only descending sort is supported
for <field>"}`) for every sort field except `createdAt` — confirmed by
testing all 5 sort values with `direction=1`: `downloads`, `likes`,
`lastModified`, and `trendingScore` all reject ascending order;
`createdAt` is the only one that accepts it. This is a genuine platform
constraint (these fields are presumably indexed/cached only in
descending order for performance), not a bug — the actor surfaces it as
a structured `_error: "invalid_request"` record (via the `InvalidRequest`
exception) rather than crashing or silently falling back to descending.

## Confirmed enum values

| Param | Confirmed valid values | Source |
|---|---|---|
| `sort` | `downloads`, `likes`, `createdAt`, `lastModified`, `trendingScore` | Live error-probe: a 6th bogus value returned `{"error":"Invalid sort parameter: bogusSortValue"}`, confirming these 5 are the exhaustive set. |
| `direction` | `-1` (descending, all sort fields), `1` (ascending, `createdAt` only) | See quirk #3 above. |

`filter`, `pipeline_tag`, `library`, `author`, `search` are all free-text
(no closed enum) and were confirmed working via live queries returning
real, relevant results (e.g. `pipeline_tag=text-generation`,
`library=transformers`, `author=openai`).

## Data sources (all `S1-api`, no fallback needed)

There is no S2 fallback — this is the one documented, stable, official
API surface for all seven modes.

### 1. `models` / `datasets` / `spaces` modes
`GET /{entity}` with optional `search`/`author`/`filter`/`sort`/
`direction` (`models` only additionally supports `pipeline_tag`/
`library`). Each list item already carries a rich subset of fields
(tags, pipeline_tag, library_name, likes, downloads) — not the full
`siblings` file list, which only appears on the detail endpoint (or the
list endpoint with `full=true`, not used by default here to keep list
responses light).

### 2. `model-detail` / `dataset-detail` / `space-detail` modes
`GET /{entity}/{id}`. Full object including `siblings` (file list),
`cardData` (parsed README front-matter), `config` (models only), and — 
for Spaces — `host`/`subdomain`/`sdk`. See quirk #1 above for 404-vs-401
handling.

### 3. `creator` mode
`GET /users/{username}/overview` or `GET /organizations/{name}/overview`
depending on `accountType` (default `auto`, see quirk #2 above).

## Known limits

- List-mode responses do not include the full `siblings` file list by
  default (only detail-mode responses do) — this matches the platform's
  own default and keeps list-mode payloads light for browsing/filtering
  use cases; use `model-detail`/`dataset-detail`/`space-detail` mode for
  the full file manifest of a specific repo.
- Private/gated repos are out of scope — this actor never authenticates,
  so gated models (e.g. some Llama variants requiring a license
  acceptance click-through) return their public metadata (tags, likes,
  gated: true) but not download-restricted file contents; this is
  already the correct behavior for a "Public Data / No Login" actor, not
  a limitation to route around.
- `filter` values are Hugging Face's own internal tag vocabulary (things
  like `license:mit`, `dataset:squad`, `pytorch`) — there is no
  authoritative enumerable list of every valid tag (unlike `sort`), so
  invalid/nonexistent filter values simply return zero results rather
  than a 400.

## Diff cadence

Quarterly smoke test recommended. If any mode starts returning
unexpected 400s, the error message names the exact invalid param/enum —
update `src/constants.py`'s whitelist accordingly rather than guessing.
