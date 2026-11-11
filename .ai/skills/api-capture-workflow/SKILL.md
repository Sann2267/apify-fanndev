---
name: api-capture-workflow
description: "Decide when to ask the operator for a manual DevTools API capture because code-only research cannot recover rotated persisted-query hashes, signed JWTs, or hidden endpoints/body fields. Use when a WAF-protected target's API changed and outside-in investigation has stalled."
---

# Skill: when to ask the operator for a DevTools API capture

This skill applies to any actor in this repository whose scraping target has changed its public API. **Apply it whenever code-only research has stopped producing new information.**

## Why this skill exists

WAF-protected sites (Airbnb, TripAdvisor, Skyscanner, Booking.com, etc.) periodically rotate their persisted-query hashes, request bodies, endpoint URLs, and fingerprinting checks. The AI agent can do a lot from the outside — but there are blockers an outside agent **cannot** clear:

- **Persisted-query hashes / preRegisteredQueryIds** that live in a lazy-loaded JS chunk the page never references until a specific UI interaction (e.g. clicking "Show all reviews").
- **Signed JWTs** (`updateToken`, `__Secure-anon_token`, `__Secure-session_id`) — the agent cannot forge them; they must be extracted from a real session.
- **Endpoint URLs** that don't appear in any HTML or initial JS chunk.
- **Body field names** that the server validates but never tells you about in error messages.

When the agent's own browser-less reverse-engineering has stalled, the right move is to **ask the operator to capture one network request from their own Chrome session and paste it back**. This skill describes when to ask, what to ask for, and how to consume the capture.

## When to ask (the trigger checklist)

Before asking the operator, the agent should have **already done all of**:

1. **Searched the initial HTML payload** for the operation/endpoint:
   - Inline `<script>` blocks, `data-deferred-state-*`, `__NEXT_DATA__`, `window.__APOLLO_STATE__`, `__WEB_CONTEXT__`, JSON-LD blocks, hidden form fields.
2. **Scanned the JS bundle chunks** that the initial HTML references:
   - Greppped for `operationName`, `operationId`, `preRegisteredQueryId`, `preRegisteredQuery`, the suspected operation name, the persisted-query manifest entry shape (`name:'...',type:'...',operationId:'<64hex>'`).
3. **Tried the obvious endpoint variants**:
   - Versioned paths (`/v1`, `/v2`, `/v3`), pluralization, snake_case vs camelCase, alternate hostnames (regional shards), the public mobile API host.
4. **Read the server's validation errors carefully** (4xx response bodies often reveal the exact missing/wrong field name).
5. **Tried the simplest possible body** the documented endpoint would accept, then added fields one at a time until the error changes.

Only **after** these have been exhausted, ask the operator for a capture.

## What to ask for (the operator request)

When asking, **be specific** about what to capture. Vague requests waste the operator's time and yield unusable captures.

### Required: the exact UI action and URL

> "Please open Chrome, log out (or use Incognito), navigate to `<exact_url>`, and **<the exact UI action: 'click "Show all reviews"' / 'open the month-grid widget' / 'click any destination tile'>**. Then open DevTools → Network tab → filter for `<expected_endpoint_substring>`, right-click the request → **Copy → Copy as cURL (bash)** OR **Copy as Python (requests)**. Paste the result back here."

### Why specify the exact action

The desired request fires only on that specific interaction. Operators who don't know the trick will capture the page-load requests, none of which contain what we need.

### When to ask for "Copy as Python (requests)"

This is the gold-standard format because it preserves: full URL with query string, cookies, every header, and request body (or `json_data` if JSON). Most teams' DevTools default has this option. If not, **cURL (bash)** is fine — we can convert it.

### Format on disk

Tell the operator to save the captured snippet as `docs/captures/<target>_<endpoint>_devtools.py` so it stays out of the actor Docker build path but is version-controlled for future debugging.

## How to consume the capture

Once the operator pastes the capture, do **all of** this before writing code:

1. **Identify the endpoint**: HTTP method, URL, host, path, query parameters.
2. **Identify the operation discriminator**: persisted-query hash, `preRegisteredQueryId`, or operation name. If a hash, note that it will rotate; design the actor to discover it at runtime when possible.
3. **Decode the body**: pretty-print the JSON. Identify which fields are
   - **Required for the server's validation** (will be in error messages if missing)
   - **Identity** (sessionId, traveller-context, view-id) — usually need to come from cookies/headers set by a homepage warmup
   - **User intent** (origin, destination, limit, offset, sort, filters) — these are what the actor's input should map to
   - **Decorative** (tracking, screenName, pageviewUid) — usually safe to randomize per-request
4. **Decode any JWT tokens** (`updateToken`, `__Secure-anon_token`):
   - `base64.urlsafe_b64decode(part_2 + padding)` → JSON
   - If the JWT is **session-state** (e.g. `pageIndex`, `reviewIds`), the actor cannot forge it — it must extract it from a fresh HTML page response on every run.
   - If the JWT is **identity** (e.g. anonymous user ID), the actor can let the cookie-jar set it via a homepage GET.
5. **Identify the cookies that matter**:
   - DataDome: `datadome`, `_abck`, `TASID` family on TripAdvisor
   - PerimeterX: `_pxhd`, `_pxvid`, `__Secure-session_id` on Skyscanner
   - These cookies are set by the *homepage GET* on the same domain. The actor's warmup step gets them automatically.
6. **Identify the headers that matter** (vs. the noise):
   - Real signals: `x-<vendor>-*` custom headers, `X-CSRF-*`, the body-side `headers` envelope on Skyscanner
   - Noise (the impersonation profile sets these correctly): `sec-ch-ua`, `sec-fetch-*`, `accept-language`, `user-agent`
   - **Never reproduce the operator's** `traveller_context` / `utid` / `viewid` UUIDs verbatim — generate fresh ones per actor run with `uuid.uuid4()`.

## How to write the resulting code

- **Move the capture out of the actor's Docker build path**: keep it under `docs/captures/` (or wherever the project standardizes), not in `actor-*/` root.
- **Hard-code the operation hash / preRegisteredQueryId as a fallback constant** with a `Last verified YYYY-MM-DD` comment. Always try to discover it dynamically first (chunk scan, page state extraction); fall back to the constant only when discovery fails.
- **Reference the capture in code comments** so future-you can re-derive the schema when something rotates: `# Body shape verified YYYY-MM-DD from docs/captures/<file>.py`.
- **Don't leak the capture's user-specific identifiers** into committed code — strip cookies, UUIDs, JWTs, pageview IDs. Generate fresh ones per run.
- **Make a fixture for offline tests** by trimming the response body to 1-2 representative entries.

## Anti-patterns to refuse

- Asking the operator to "go run this for me" via Computer Use, MCP CDP, or a headless browser — these all carry `navigator.webdriver` or non-human timing and get fingerprinted within 1-2 requests. The only working path is **manual capture from the operator's own Chrome session**.
- Hallucinating endpoint URLs from training data ("I bet `/api/v2/reviews` works") — every concrete URL must come from a real capture, the JS bundle, or the server's own error responses.
- Hallucinating preRegisteredQueryIds from training data — they are bundle-deployment-specific and rotate.
- Ignoring server validation errors. A 400 with `field X: must not be empty` is far more useful than retrying with a different proxy.

## Script for asking the operator

Use language like:

> "Saya sudah cek <inline state / JS chunks / known endpoint variants> dan endpoint untuk `<feature>` tidak ada di sana — kemungkinan dia lazy-loaded chunk yang baru ke-fetch ketika user `<specific action>`. Bisa minta tolong:
>
> 1. Buka Chrome (atau Incognito).
> 2. Navigate ke `<exact_url>`.
> 3. Buka DevTools → Network tab → filter `<endpoint_substring>`.
> 4. Lakukan `<specific UI action>`.
> 5. Klik kanan request yang relevan → Copy → Copy as Python (requests).
> 6. Paste hasilnya ke sini (atau simpan di `docs/captures/<filename>.py`).
>
> Saya tidak bisa drive Chrome dari sini — extension VSCode tidak punya akses ke browser kamu. CDP / playwright-mcp bisa tapi pasti ke-detect bot karena `navigator.webdriver` flag + automation timing. Real human session adalah satu-satunya cara yang reliable."

Then explicitly list **what's blocking** so the operator understands why this is the unblocker — e.g. "Tanpa capture ini, hash persisted-query yang dibutuhkan tidak bisa ditemukan; semua variant endpoint yang saya coba dari knowledge return 4xx atau 404."
