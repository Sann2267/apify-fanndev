"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): The Bahamas' official company/business registry
is run by the **Registrar General's Department (RGD)**, part of the Ministry
of Finance. The RGD's marketing/info site is `www.rgd.gov.bs` (also mirrored
under `bahamas.gov.bs/agencies/registrar-generals-department`); its
transactional registry system -- "BDR Online Public Services" -- is a
separate Angular SPA at `pub.rgd.gov.bs`, backed by a JSON REST API at
`cars.rgd.gov.bs/api` ("CARS" = Corporate Administrative Registry Services).

`robots.txt`: `www.rgd.gov.bs/robots.txt` is a clean, standard multi-agent
file (`User-agent: *` -> `Disallow: /cgi-bin/` only, plus explicit `Allow: /`
groups for Googlebot/Adsbot/Twitterbot/etc.) -- no Claude/ClaudeBot/
anthropic-ai/AI-crawler mention anywhere, no blanket block. `pub.rgd.gov.bs`
has no real `robots.txt` file at all (it's a client-routed SPA that serves
its `index.html` shell for any path, including `/robots.txt`, with HTTP 200)
-- so there is no restriction to violate there either. `cars.rgd.gov.bs` (the
API host) returns plain JSON 404s for unknown paths, also no `robots.txt`
restriction.

**No login, account, or CAPTCHA is required for the basic company NAME
search.** reCAPTCHA (`recaptcha_sitekey` in the SPA's `environment`) only
appears later in the flow, at the credit-card PAYMENT step for the full
$100 BSD "Company Search Report" (login/payment automation is explicitly out
of scope for this project and was not attempted or needed).

Found by downloading the SPA's Angular build (`main.*.js` + lazy chunk
`66.*.js` for the `CompanySearchModule`, plus the shared API-service chunk
`868.*.js`) and grepping for the API base URL and the Angular service class's
HTTP calls -- same "read the shipped JS" technique used for URSB/CIPA/PACRA
in prior actors. The base URL and free search endpoint:

    apiBase = "https://cars.rgd.gov.bs/api"
    GET {apiBase}/public/entities?name=<query>&pageNo=<n>&pageSize=<n>
    GET {apiBase}/public/entities/history?name=<query>&pageNo=<n>&pageSize=<n>

Both confirmed reachable with a completely plain, unauthenticated `curl` --
no TLS impersonation, no special headers, no cookies/session needed. (This
project's `curl_cffi` is still used below for consistency/resilience with
the rest of the portfolio, not because any gate was found requiring it.)

## Gotcha 1: `pageNo`/`pageSize` are accepted but silently ignored

Every query tested -- regardless of `pageSize` (3, 50, 100) or `pageNo`
(1, 2) -- returned **at most 3 results**, always the same 3, in the same
order. This is not a bug in this actor's request construction: it is the
free tool's actual behavior. **The free public search is a "top 3 best
name matches" preview, not a paginated browse of the full registry.** This
lines up with the government's own monetization model (`$100 BSD` per full
"Company Search Report", credit-card gated) -- the free preview exists to
help a payer identify *which* entity they want to pay to search, not to
give away the full result set. This actor therefore does not implement
pagination (there is nothing to paginate into) and returns whatever subset
of the top-3 the query matched.

## Gotcha 2: broad/common queries return HTTP 200 with a genuinely empty body (0 bytes)

A query truly matching nothing returns `200` with a proper empty JSON array
body, `[]` (2 bytes) -- e.g. `name=xyzxyzxyznonexistent12345` or
`name=AML Foundation`. But short/very common queries (`Bank`, `Banks`, `Ba`,
`Ban`, `RBC`, `LTD`) reliably return `200` with a **completely empty body
(0 bytes, no `Content-Type` header, `Transfer-Encoding: chunked` cut short)**
-- reproduced identically across `curl_cffi` (every TLS profile tried),
plain `httpx`, and real system `curl` with zero special headers, so this is
not a client-side/TLS-fingerprint issue. Response time for these was fast
(~1.3s, not a slow-timeout pattern) and deterministic across repeats. The
likely cause: the backend's relevance-ranking query over a very large
candidate set (a common short word/prefix matches thousands of Bahamas IBCs)
hits some internal limit or short reverse-proxy timeout and the gateway
returns a truncated/empty 200 instead of an error. This actor distinguishes
the two empty cases explicitly -- a real `[]` is `not_found`, a 0-byte body
is `result_set_too_broad` -- rather than collapsing both into a false
"not found" (same spirit as `fiji-roc-scraper`'s `result_set_too_broad`
handling for its own overly-fuzzy search). **Practical takeaway for callers:
search with a reasonably specific term (a real company's actual name or a
distinctive fragment of it), not a single common word.**

## Gotcha 3: almost every field in the free result is `null`

Each matched entity in the free preview carries `entityId` (RGD's internal
numeric ID) and `entityName` (exactly as registered) as the only reliably
populated fields, plus `legacyMigrationStatus` (seen as `"NONE"` on every
live sample). Every other field on the entity object -- `entityType`,
`entityNumber`, `entityStatus`, `registrationDate`, directors, shareholders,
share capital, documents, etc. -- was `null`/empty on every real entity
sampled during recon (dozens of banks/hotels/law firms/insurers across many
queries). This is a genuine data-completeness limit of the free preview, not
a scraping gap: the full "Company Search Report" (registration number,
status, entity type, directors, share capital, document list) is exactly
what the $100 BSD paid+credit-card-gated flow sells, and that flow is out of
scope for this project (no payment automation). This actor passes through
every field upstream provides, raw, so if RGD ever populates more fields on
the free tier they show up automatically.

## Name-history variant

`GET {apiBase}/public/entities/history?name=<query>...` searches Bahamas'
name-CHANGE history records instead of current names -- each hit is a
`{"nameHistoryId", "name": "<the old/former name>", "entity": {...}}`
wrapper around the same entity shape as above. Same 3-result cap and same
0-byte-on-too-broad behavior. Exposed as the `includeHistory` input flag,
matching the SPA's own `includeHistory` search-page toggle.
"""

TLS_PROFILE = "chrome124"

API_BASE = "https://cars.rgd.gov.bs/api"
ENTITIES_PATH = "/public/entities"
ENTITIES_HISTORY_PATH = "/public/entities/history"

FRONTEND_ORIGIN = "https://pub.rgd.gov.bs"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": FRONTEND_ORIGIN,
    "Referer": f"{FRONTEND_ORIGIN}/services/company_search",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.0

# The API ignores this, but is sent anyway to mirror the real SPA's request
# shape as closely as possible.
PAGE_SIZE = 3
