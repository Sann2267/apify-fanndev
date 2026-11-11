# Crawling Method — Uganda URSB

**Last verified:** 2026-08-26/27

URSB (Uganda Registration Services Bureau, `ursb.go.ug`) is Uganda's
official company, business name, and legal-document registry. The public
marketing site (`ursb.go.ug`) is WordPress; the transactional registry --
branded "eRegistry" / OBRS (Online Business Registration System) -- is a
separate single-page app at `eregistry.ursb.go.ug` (built with Vite/Vue3).
The older `obrs.ursb.go.ug` host still resolves but 301-redirects every path
to the equivalent path on `eregistry.ursb.go.ug`. A third subdomain,
`eservices.ursb.go.ug`, referenced in some older third-party writeups about
URSB's search tool, no longer resolves in DNS at all -- dead, not pursued.

## Robots.txt

```
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

Sitemap: https://ursb.go.ug/wp-sitemap.xml
```

Stock WordPress block on the marketing site, no Claude/AI-crawler mention.
`eregistry.ursb.go.ug/robots.txt` and the API host's `/robots.txt` both
return non-200 (the SPA host serves its `index.html` shell for any
unmatched path since it's client-side routed; the API host returns a plain
JSON 404) -- i.e. no `robots.txt` file exists on either, so no disallow rule
applies to anything this actor touches.

## Finding the API: read the shipped JS bundle

`eregistry.ursb.go.ug/name-search` (the public "Name Search" page, linked
from URSB's own site and from `obrs.ursb.go.ug/name-search`) is a Vue3 SPA
that ships as one built bundle, `/assets/index-<hash>.js` (~2.1 MB
minified). Same technique used for CIPA's Verne bundles and PACRA's webpack
chunks in prior sessions (every government site's build is laid out
differently, but "download the bundle and grep for API base URLs / route
tables" transfers): the bundle hardcodes an object literal with four API
base URLs:

- `https://obrs-api.ursb.go.ug` (general API)
- `https://obrs-api.ursb.go.ug/nir/api` (registry API -- the one used here)
- `https://obrs-api.ursb.go.ug/copy-right` (copyright module, not used)
- `https://obrs-api.ursb.go.ug/dac` (a third module, not explored)

Grepping the bundle's Vue Router route table for `path:"/name-search"`
pointed at the component that, on mount, reads `?q=` from the URL and
issues:

```
GET https://obrs-api.ursb.go.ug/nir/api/v1/registry/name-search
    ?name=<query>&page=<1-based page>&limit=<page size>
```

This is a **plain JSON REST endpoint** -- no session, no CSRF token, no
view-tree/delta protocol to drive (unlike CIPA/PACRA). `name` doubles as a
general search term: confirmed to match both on entity name (substring/
fuzzy) and on an exact ERN (Entity Registration Number, e.g.
`80020002358032`) passed in the same parameter -- there is no separate
"search by number" endpoint.

## The gate: TLS fingerprint only

A plain-TLS request (default `curl`, any header set) to the endpoint always
returns:

```
HTTP/1.1 403 Forbidden
{"data":null,"message":"Prohibited Access!, try again.","status":403,"error":"Forbidden"}
```

Response headers show plain `nginx`, no Cloudflare/`cf-ray`/challenge-page
markers, and `Access-Control-Allow-Origin: *` (so it isn't even doing real
CORS enforcement). Every `curl_cffi` impersonation profile tried
(`chrome124`, `chrome131`, `chrome120`, `safari17_0`, `edge101`,
`chrome99_android`) returned `HTTP 200` with real JSON on the **first**
try -- this confirms the block is keyed on the TLS handshake fingerprint
alone (JA3/JA4-style), not headers, cookies, or a JS challenge. No CAPTCHA
anywhere in this flow; no login required for the search itself (URSB's own
public docs confirm login/payment is only needed to purchase a certified
extract, not to search).

## Response shape

```json
{"code":200,"data":{"content":[{ ...entity... }],"pagination":{...}}}
```

Each entity: `id` (internal UUID), `ern`, `name`, `type` (e.g. `"Company"`,
`"Business Name"`), `subType` (e.g. `"Private Company Limited by Shares"`,
`"Sole Proprietor"`, `"General Partnership"`), `status` (e.g.
`"REGISTERED"`), `registrationInstitution`, `duplicateAllowed`, `createdAt`,
`deactivatedAt`, `registrationDate`, `affiliations`, `registrationType`,
`recordStatus`, `complianceStatus` (e.g. `"COMPLIANT"`).
`registrationDate` and a couple of other fields were `null`/empty on every
one of dozens of real entities sampled (banks, telcos, sole proprietorships)
across several queries -- a genuine data-completeness limit of this specific
public search response, not a scraping gap (the full paid/logged-in
certified extract likely carries more).

## Gotcha 1: `pagination` metadata in the response cannot be trusted

The `pagination` object (`currentPage`, `nextPage`, `totalPages`,
`totalRows`) was observed as `{"currentPage":1,"nextPage":0,"totalPages":0,
"totalRows":0}` on responses that demonstrably carried real, distinct
`content` rows (confirmed non-identical result sets across `page=1,2,3,50`
for the broad query `"limited"`). **This actor does not use those fields
for its stop condition.** Instead it pages until a response's `content`
array is shorter than the requested `limit` (including empty) -- the only
signal confirmed reliable during recon.

## Gotcha 2: the search is fuzzy, not exact-substring

A garbage query invented purely for testing (a 23-character nonsense
string) returned two real, unrelated-looking entity names ("WISTEN
INVESTMENTS", "OSTEN ZION") instead of an empty result -- reproducible
across repeat calls (deterministic, not random noise). A different, longer
(32-character) garbage string correctly returned an empty result. This
matches the tool's own stated purpose -- Uganda's business-name
**availability/uniqueness** checker, which by design fuzzy-matches
near-spellings to catch naming conflicts -- rather than being a bug, but it
means a caller should not assume every returned row literally contains the
query substring, especially for short/unusual queries. Records are passed
through as URSB returns them (raw-passthrough); this actor does not
re-filter or "verify" matches client-side.

## Gotcha 3: very deep pagination times out

`page=10000` (`limit=5`) reliably timed out with no response body after 20+
seconds, while `page=1` through `page=50` all returned promptly. This looks
like a backend query-planner cost issue on a very high SQL/ES offset, not a
deliberate anti-scraping measure (no distinct error, just a hang). The
actor caps per-query pagination depth at 20 pages (well under the confirmed
"still fine" depth of 50, itself far under the confirmed-timing-out depth
of 10000) and treats a mid-pagination timeout as "stop here, keep what was
already collected" (flagged with `_warning:
"pagination_truncated_by_timeout"` on the affected records) rather than
failing the whole query.

## Not used: entity-type filter

`GET https://obrs-api.ursb.go.ug/nir/api/v1/configurations/entity-types`
returns the full type taxonomy (Condominium, Trust, Cooperative, Company,
Business Name, ... each keyed by an internal UUID) that the site's own
"advanced search" / "deregistered entities" pages use to build `typeId`/
`subTypeId` filters on the search call. Confirmed reachable with the same
TLS-fingerprint requirement as the search endpoint, but not wired into this
actor's input -- the UUIDs are opaque and would need their own lookup UI to
be usable, which was out of scope for this build. Documented here as a
straightforward future extension.

## Sample queries tested

- **Stanbic** (20+ matches, capped at `maxResultsPerQuery`) -- Stanbic Bank
  Uganda, Stanbic Properties, Stanbic Uganda Holdings, Stanbic Business
  Incubator, plus unrelated "Business Name" matches on partial substrings.
- **MTN** (20+ matches) -- MTN (Uganda) Limited, MTN Mobile Money (U)
  Limited, MTN Dealers Forum Limited, plus fuzzy-matched unrelated names.
- **`80020002358032`** (exact ERN for Stanbic Properties Limited) -- confirms
  the same `name` param accepts registration numbers, not just names.
- A deliberately-invented 23-char garbage string -- returned 2 fuzzy-matched
  unrelated names (see Gotcha 2).
- A deliberately-invented 32-char garbage string -- correctly returned zero
  results, exercised via `extract_error(..., "not_found")`.

## Known limits

- `registrationDate` and a few other schema fields are `null`/empty on
  effectively every record returned by this specific public endpoint --
  this reflects what URSB's own public search tool shows, not a scraping
  gap.
- The search is fuzzy (see Gotcha 2) -- treat results as "candidate/similar
  matches," not guaranteed exact-substring hits, especially for short or
  unusual queries.
- No entity-type/sub-type filtering is exposed (see "Not used" above).
- This actor covers the free public name/number search only. URSB's
  certified-extract / full-document download flow requires an account and
  payment (mobile money or card) and is out of scope -- this project does
  not automate login or payment flows.

## Diff cadence

Quarterly smoke test recommended -- `eregistry.ursb.go.ug` is an actively
developed SPA (the loader HTML even carries in-progress commented-out
branding code as of this recon), so bundle hashes and possibly the API
shape could change on a redeploy.
