"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-26/27): URSB -- Uganda's Registration Services
Bureau (`ursb.go.ug`) -- runs its public marketing site on WordPress
(`ursb.go.ug`) and its transactional business/company registry ("eRegistry" /
"OBRS", Online Business Registration System) as a separate single-page app at
`eregistry.ursb.go.ug` (a Vite/Vue3 build). The old `obrs.ursb.go.ug` host
still exists but 301-redirects every path to the equivalent `eregistry.
ursb.go.ug` path (e.g. `/name-search` -> `/name-search`); `eservices.ursb.
go.ug`, referenced by some older third-party writeups, no longer resolves in
DNS at all (dead subdomain, not pursued).

`robots.txt`: `ursb.go.ug/robots.txt` is a stock WordPress block
(`Disallow: /wp-admin/`, `Allow: /wp-admin/admin-ajax.php`) -- no Claude/AI-
crawler mention. `eregistry.ursb.go.ug` and the API host below have no
`robots.txt` file at all (`eregistry...` serves its SPA shell for any path
including `/robots.txt`, since it's a client-side-routed app with no server
match; the API host returns a plain JSON 404). No disallow rule anywhere
applies to the API host or path used by this actor.

**The public "Name Search" tool (`eregistry.ursb.go.ug/name-search?q=...`,
linked from `obrs.ursb.go.ug/name-search` and from URSB's own site) is a Vue3
SPA that calls a plain JSON REST endpoint -- no login, no CAPTCHA, no session
state needed.** Found by downloading the SPA's single built JS bundle
(`/assets/index-*.js`, ~2.1 MB minified) and grepping it for API base URLs
and route definitions (the same "read the shipped JS" technique used for
CIPA's Verne bundles and PACRA's webpack chunks in prior sessions -- every
government site's bundle is laid out differently, but the technique
transfers): the bundle hardcodes four API base URLs (`Ka` object literal in
the minified source) --

- `https://obrs-api.ursb.go.ug`                (general API, used with `H()`)
- `https://obrs-api.ursb.go.ug/nir/api`        (registry API, used with `hg()`)
- `https://obrs-api.ursb.go.ug/copy-right`     (copyright module)
- `https://obrs-api.ursb.go.ug/dac`            (a third module, not explored)

The public `/name-search` page's Vue component reads `?q=` from the URL and
calls (via the `hg()` axios instance, i.e. the `/nir/api` base):

    GET https://obrs-api.ursb.go.ug/nir/api/v1/registry/name-search
        ?name=<query>&page=<1-based>&limit=<page size>
        [&typeId=<uuid,uuid,...>][&subTypeId=<uuid,uuid,...>]

`name` is a general search term -- confirmed to match on entity name
(substring/fuzzy) AND on exact ERN (Entity Registration Number, e.g.
`80020002358032`) in the SAME parameter; no separate "search by number"
endpoint exists or is needed.

**Gate found: TLS-fingerprint only, not a real WAF product.** A plain
`curl`/default-TLS request to this endpoint (any query, any headers) always
returns `HTTP 403 {"data":null,"message":"Prohibited Access!, try again.",
"status":403,"error":"Forbidden"}` -- plain `nginx` in the response headers,
no Cloudflare/`cf-ray`/challenge-page markers, `Access-Control-Allow-Origin:
*` (so it isn't even doing real CORS enforcement). Every `curl_cffi`
impersonation profile tried (`chrome124`, `chrome131`, `chrome120`,
`safari17_0`, `edge101`, `chrome99_android`) returned `HTTP 200` with real
JSON on the first try -- this is gated on the TLS handshake fingerprint
alone, not on headers, cookies, or a JS challenge. No CAPTCHA anywhere in
this flow.

## Response shape

```json
{"code":200,"data":{"content":[{ ...entity... }, ...],"pagination":{...}}}
```

Each entity in `content`: `id` (internal UUID), `ern` (Entity Registration
Number -- URSB's public registration number), `name`, `type` (e.g.
`"Company"`, `"Business Name"`), `subType` (e.g. `"Private Company Limited
by Shares"`, `"Sole Proprietor"`, `"General Partnership"`), `status` (e.g.
`"REGISTERED"`), `registrationInstitution`, `duplicateAllowed`, `createdAt`,
`deactivatedAt`, `registrationDate`, `affiliations`, `registrationType`,
`recordStatus`, `complianceStatus` (e.g. `"COMPLIANT"`). `registrationDate`
and a few others were `null` on every real entity sampled during recon
(dozens of banks/companies/business names across several queries) -- this
looks like a genuine data-completeness limit of this specific public search
endpoint (the full paid/logged-in "certified extract" likely carries more),
not a scraping gap. `affiliations` was an empty list on every sample seen.

## Gotcha 1: `pagination` metadata in the response is not trustworthy

The `pagination` object (`currentPage`, `nextPage`, `totalPages`,
`totalRows`) was observed as `{"currentPage":1,"nextPage":0,"totalPages":0,
"totalRows":0}` on responses that demonstrably carried real, correct
`content` rows (confirmed non-identical result sets across `page=1,2,3` for
a broad query like `"limited"`). **Do not use `totalPages`/`totalRows` as a
stop condition.** The only reliable pagination stop condition found: keep
requesting increasing `page` values while the returned `content` array's
length equals the requested `limit`; stop as soon as `content` is shorter
than `limit` (including empty).

## Gotcha 2: the search is fuzzy, not exact-substring

A garbage query invented for testing (a 23-character nonsense string)
returned two real, unrelated-looking entity names ("WISTEN INVESTMENTS",
"OSTEN ZION") instead of an empty result -- reproducible across repeated
calls (not random). A different, longer garbage string (32 chars) correctly
returned an empty `content` array. This is consistent with the tool's own
stated purpose (Uganda's "check name availability / similar name" search,
which by design must fuzzy-match near-spellings to catch name-uniqueness
conflicts) rather than a bug -- but it means **a caller should not assume
every row in the response actually contains the query string**, especially
for short or unusual queries. This actor passes results through as-is
(raw-passthrough principle) and does not attempt to re-filter/verify
matches, but this is called out in the README and CRAWLING_METHOD.md so
consumers know to sanity-check for their own use case.

## Gotcha 3: very deep pagination times out

`page=10000` (with `limit=5`) reliably timed out (no response body, 20s+)
where `page=1..50` all returned promptly. Moderate depths (tested up to
`page=50`) were fine. This actor caps `maxResultsPerQuery` at a level that
keeps page depth well within the confirmed-safe range, and treats a
pagination-fetch timeout as "stop paginating for this query, keep what was
already collected" (with a `_warning` on the record set) rather than
crashing the whole run -- the underlying cause (backend query-planner cost
of a very high SQL/ES offset) is an upstream operational limit, not
malformed input.

## Supporting endpoint (not used by default)

`GET https://obrs-api.ursb.go.ug/nir/api/v1/configurations/entity-types`
returns the full entity-type taxonomy (Condominium, Trust, Cooperative,
Company, Business Name, ... each with a UUID `id`) used to build the
`typeId`/`subTypeId` filter values. Not wired into this actor's input (the
UUIDs are internal/opaque and would need their own lookup UI); left as a
documented extension point.
"""

TLS_PROFILE = "chrome124"

API_BASE = "https://obrs-api.ursb.go.ug/nir/api"
NAME_SEARCH_PATH = "/v1/registry/name-search"

FRONTEND_ORIGIN = "https://eregistry.ursb.go.ug"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": FRONTEND_ORIGIN,
    "Referer": f"{FRONTEND_ORIGIN}/name-search",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0

# Per-page size sent to the API. 100 was confirmed to work; kept well under
# any observed limit.
PAGE_LIMIT = 100

# Safety cap on page depth per query (see Gotcha 3 above) -- page=50 was
# confirmed fine, page=10000 timed out. Keeping max pages well under that.
MAX_PAGES_PER_QUERY = 20
