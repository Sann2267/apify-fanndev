# Playbook: Reverse-Engineer an Internal GraphQL/REST API

> **Most modern sites have an internal API more useful than their public one.** GraphQL `doc_id`, persisted-query hashes, RPC IDs, MTOP API names — discoverable through a disciplined DevTools workflow. This playbook is the workflow that has proven out across IG/FB/Threads/X/Airbnb/StockX/Alibaba/Google.

## Tooling

- **Browser:** Chrome / Edge (DevTools is mature)
- **Tab:** Open DevTools → Network → Preserve log + Disable cache
- **Filter:** XHR + Fetch (hide images/CSS/font)
- **Codegen:** Right-click on a successful request → Copy → Copy as cURL (bash)

## Step 1 — Find the right request

Open the page in browser, do the action that loads the data (scroll, search, click filter). In Network tab:

- Look for **JSON responses** (not HTML page loads)
- Filter URL pattern: `/api/`, `/graphql/`, `/data/`, `/rpc/`, `/v1/`, `/v2/`
- **Ignore analytics/telemetry**: anything to `*.google-analytics.com`, `*.facebook.com/tr/`, `*.amplitude.com`, etc.

Sort by **size descending** — the data-carrying call is usually the biggest JSON response (often 50KB–1MB).

## Step 2 — Inspect the chosen request

Click the request. Tabs:

### 2.1 Headers tab
- **Request URL:** note query params, especially `doc_id=`, `variables=`, `features=`, `extensions=`
- **Request Method:** GET / POST / PUT
- **Status Code:** confirm 200
- **Request Headers:** note all `x-*` custom headers (these are platform contract, not anti-bot)
- **Form Data / Request Payload:** if POST, the body shape

### 2.2 Response tab
- **Mode:** prefer "Preview" for collapsible JSON, "Response" for raw bytes
- Confirm this response has the fields you need
- Note shape — top-level keys, nesting, ID formats

### 2.3 Cookies tab
- Note all cookies sent — which are auth (`sessionid`, `c_user`), which are anti-bot (`_abck`, `_px3`), which are state (`csrftoken`, `lsd`)

## Step 3 — Reproduce with curl

Right-click → Copy → Copy as cURL (bash). Run in terminal:

```bash
curl 'https://www.instagram.com/api/graphql' \
  -H 'cookie: csrftoken=ABC; mid=...' \
  -H 'x-ig-app-id: 936619743392459' \
  -H 'x-fb-lsd: <token>' \
  ... \
  --data-raw 'av=0&__user=0&doc_id=8845758582119845&variables=...'
```

If curl returns the same JSON → reproducible. Now port to Python.

If curl returns 403/empty → the missing piece is either:
- TLS fingerprint (curl shows Python/cURL JA3) → use `curl_cffi`
- A cookie that expired between copy and curl → re-copy
- A header you missed → diff curl's headers vs your scraper's

## Step 4 — Identify the volatile vs stable parts

Run the same request 3 times, 5 minutes apart. Diff:

| Field | Stable? | Notes |
| --- | --- | --- |
| URL path | ✅ | Hardcode |
| Query param keys | ✅ | Hardcode key names |
| `doc_id` / `queryId` | ⚠️ | Stable for ~2-4 weeks, then rotate |
| `__hs` / `__rev` / `__spin_*` | ⚠️ | Per-page-load, harvest from HTML |
| `lsd` / `jazoest` | ⚠️ | Per-page-load, harvest from HTML |
| `variables` content | ✅ | Application-controlled |
| `csrftoken` cookie | ⚠️ | Per-session, harvest from cookies |
| `_abck` / `_px3` cookies | ⚠️ | Anti-bot, get via warmup |
| User-Agent | ✅ | Pin to match impersonation profile |

What's "stable" you hardcode. What's "volatile" needs runtime harvest.

## Step 5 — Find where the volatile tokens come from

Open DevTools → Network → click a **page load** (HTML doc, not XHR). Scan the response body for the volatile token values you noticed:

```python
# Example: where does doc_id come from?
# Search the HTML response for the doc_id value (e.g. "8845758582119845")
# Likely match in inline JS like:
#   __require("PolarisPostsByMediaIdQuery").id = "8845758582119845"
# OR in a separate .js bundle
```

If the value isn't in the HTML, check linked JS bundles:

```bash
# Get bundle URLs from the page
grep -oE 'src="[^"]+\.js"' page.html

# Search each for the doc_id
curl https://www.instagram.com/static/bundles/.../route.js | grep "8845758582119845"
```

Once found, write a regex to extract it programmatically:

```python
import re

def harvest_doc_id(html: str, query_name: str) -> str | None:
    """Regex to pull doc_id from HTML or bundle."""
    m = re.search(
        rf'"id":"(\d{{14,18}})","name":"{query_name}"',
        html,
    )
    return m.group(1) if m else None
```

## Step 6 — Verify reproduction in Python

```python
async def call(doc_id, variables, tokens):
    return await session.post(
        "https://www.instagram.com/api/graphql",
        data={
            "av": "0",
            "__user": "0",
            "__a": "1",
            "lsd": tokens["lsd"],
            "jazoest": tokens["jazoest"],
            "__hs": tokens["__hs"],
            "__rev": tokens["__rev"],
            "variables": json.dumps(variables),
            "doc_id": doc_id,
            # ... full form
        },
        headers={
            "x-ig-app-id": "936619743392459",
            "x-csrftoken": tokens["csrftoken"],
            "x-fb-lsd": tokens["lsd"],
            "x-fb-friendly-name": "PolarisPostsByMediaIdQuery",
        },
    )
```

Run, compare output to the browser-captured JSON. Byte-for-byte not required, but the field shapes should match.

## Step 7 — Variable shape discovery

GraphQL queries have typed variable inputs. Wrong types return `noncoercible_variable_value`.

To discover the schema:
- In DevTools, copy a working `variables` from browser
- Diff its structure against what you're sending
- Field types are evident: strings have quotes, ints don't, enums are strings matching a known set

Sometimes you need to call the query with a wrong variable on purpose to get an error message that reveals the schema:

```json
// Sent with broken variable:
{"input": {"username": 12345}}
// Server returns:
{"errors": [{"message": "Variable 'input.username' must be of type String!"}]}
```

This is the iterate-via-server-validation-error pattern — used heavily in Skyscanner's gRPC discovery.

## Step 8 — Special cases

### Persisted-query SHA-256 (Airbnb, StockX)

The hash is the SHA-256 of the query string. Discovery:

1. Find the operationId in webpack chunks: `operationName:"StaysSearch",operationId:"<sha256>"`
2. Hardcode it; auto-refresh on `PersistedQueryNotFound` server response.

### RPC IDs (Google batchexecute)

Open Trends / News / Play in browser, perform an action, look for POST `/_/.../batchexecute`. The `rpcids=` query param is the RPC ID (`i0OFE`, `Ftbldf`, etc.). Document it and the corresponding payload shape.

### MTOP API names (Alibaba family)

Not in the page HTML — embedded in mobile bundles. Approach:

1. Visit `https://h5.m.alibaba.com/...` (mobile site)
2. DevTools → mobile UA emulation
3. Find calls to `h5api.m.alibaba.com/h5/<api.name>/<version>/`
4. Catalog 20-50 names; brute-force probe in production against `FAIL_SYS_API_NOT_FOUNDED`.

### Protocol Buffers (Google Maps `pb=`)

The `pb=` query param is URL-safe protobuf. Reconstruct templates from DevTools:

1. Copy a working `pb=` value
2. Parse with `protoc --decode_raw <message-text>` or online proto-decoder
3. Note field indices and types
4. Create a template with placeholder values; mutate at runtime via `modify_pb()` (see [`skills/google-internal-apis.md`](../skills/google-internal-apis.md))

## Step 9 — Document and version

Write a one-pager in the project README:

```markdown
## Reverse-Engineered Endpoint

- **URL:** POST https://www.instagram.com/api/graphql
- **Auth:** lsd + csrftoken + (warm-page harvest)
- **Volatile:** doc_id (cache 24h, refresh on 400/404)
- **Cataloged doc_ids:** see DOC_ID_SNAPSHOT in src/client.py
- **Last verified:** 2026-05-14
- **Diff cadence:** weekly smoke test, monthly bundle hash diff
```

This is what saves the next person from re-doing all this work in 6 months.

## Time budget

| Stage | Time |
| --- | --- |
| Step 1–3 (find request, reproduce curl) | 30 min |
| Step 4–5 (volatile parts, find sources) | 1–2 hours |
| Step 6 (Python port) | 30 min |
| Step 7 (variable schema) | 1 hour (if needed) |
| Step 8 (special cases) | 2–8 hours (MTOP discovery is the worst) |
| **Total for a standard GraphQL** | **3–5 hours** |
| **Total for MTOP family** | **2–4 days** |

If you're at 4× the budget, the API is either undocumented internal (cut losses, escalate to browser interception) or genuinely unreproducible without JS (TikTok X-Gnarly, Shopee x-sap-sec — see [`lessons-learned.md`](../lessons-learned.md)).

## See also
- [`skills/warm-page-token-harvest.md`](../skills/warm-page-token-harvest.md)
- [`skills/graphql-doc-id-rotation.md`](../skills/graphql-doc-id-rotation.md)
- [`skills/google-internal-apis.md`](../skills/google-internal-apis.md)
- [`skills/mtop-signed-requests.md`](../skills/mtop-signed-requests.md)
