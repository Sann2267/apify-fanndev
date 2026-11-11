# Crawling Method — Ghana Business Registry (ORC Name Search)

**Last verified:** 2026-08-27

## Target discovery — `rgd.gov.gh` is not where the data lives

The brief named `rgd.gov.gh` (the old Registrar General's Department site).
Recon found it's legacy and partially compromised:

- `curl_cffi` `chrome124` gets a clean `200` on `rgd.gov.gh/` (28KB), but
  `robots.txt` is a real `404`.
- The homepage's footer nav contains **injected spam links**
  (`http://pornbox.cc`, `https://domifemdom.com`) mixed in among the
  legitimate government-agency links — a clear sign of a hacked/neglected
  site, not a benign quirk.
- The site's own "eGhana portal" link
  (`https://egovonline.gegov.gov.gh/RGDPortalWeb/portal/RGDHome/eghana.portal`)
  is effectively dead: across repeated attempts it returned a connection
  timeout, then (with `verify=False`) a `200` whose entire body is
  `<h3>Error. Page cannot be displayed. Please contact your service
  provider for more details.</h3>` (122 bytes). One attempt with default
  cert verification failed with `certificate subject name 'testexp' does
  not match target hostname` — a mismatched/self-signed leftover cert.

Ghana's business registry function has moved to a separate agency: the
**Office of the Registrar of Companies (ORC)**, created under the
Companies Act, 2019 (Act 992). Its site is `orc.gov.gh`
(`robots.txt`: `User-agents: *` / `Allow: /` — wide open, plus a
`Sitemap:` line, no AI/scraping prohibition text anywhere). It's a
WordPress site (theme `egovt`, Elementor, WooCommerce) whose "Name Search"
and "Entity Information Search" service pages
(`orc.gov.gh/service/name-search/`, `orc.gov.gh/service/entity-information-search/`)
are **descriptive-only** — marketing copy, no embedded form, no JS widget.

The actual interactive tool is linked from the ORC homepage footer:
`https://rgdonline.gegov.gov.gh/orc-app/`. This is a small, clearly
early-stage Spring Boot Java webapp (footer text: `v0.0.1`), server-
rendered with Thymeleaf, progressively enhanced with htmx 2.0.8. This is
the ONLY functioning public search found across all three domains
(`rgd.gov.gh`, `orc.gov.gh`, `orc.dntsystems.net` — the last one is an
empty `Index of /` Apache directory listing, a dead/unused subdomain from
the same vendor).

## robots.txt / WAF

`rgdonline.gegov.gov.gh/robots.txt` is a `404` (Apache's stock 404 page,
`<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">`) — confirmed this is a
real unmapped-route 404, not a soft-404 (it differs byte-for-byte from the
app's own catch-all page). No `robots.txt` exists, so nothing is
disallowed and there's no plain-English AI/scraping prohibition to find.

No WAF or CDN fingerprint anywhere on this host: every response carries a
bare `server: Apache`, no `cf-ray`, no bot-challenge HTML, no
`_abck`/`bm_sz`/`__cf_bm` cookies. All the friction encountered (below) is
ordinary Spring Security CSRF protection plus htmx request-routing
conventions — not anti-bot defense.

## Data source — S1-name-search

### The tool: a name-availability checker, not a full company-profile lookup

`GET /orc-app/` renders a form: `bizName` (text), `searchType` (radio:
`eq`/`sw`/`ew`/`cn` = exact/starts-with/ends-with/contains), and a hidden
`_csrf` token. Submitting calls `POST /orc-app/search-for-name` via htmx,
swapping the response fragment into `#search-results`.

**Only two fields come back per match: business name and entity type**
(`data-bizcode` on the `<tr>` + a human-readable label in the second
`<td><span>`). No registration number, incorporation date, status
(active/dissolved), address, or director/officer names — ORC's own site
copy elsewhere describes "certified extracts" as a paid, 1–3-business-day
turnaround service requested directly from ORC, confirming those richer
fields simply aren't exposed through this public tool at all.

Entity type codes observed (from `COCOA`/`BANK`/`PARTNERSHIP`/`EXTERNAL`
contains-queries, sampled 2026-08-27) — informational, not exhaustive:

| Code | Label |
|---|---|
| `BN` | Sole Proprietor |
| `CG` | Company Limited by Guarantee |
| `CS` | Company Limited by Shares |
| `ET` | External Company |
| `PN` | Partnership |
| `SN` | Subsidiary Business Name |

### The CSRF/htmx dance (found by trial and error)

A plain `GET` then `POST` with the obvious form fields is NOT enough —
early attempts got a `302` redirect back to `/orc-app/` with an empty
body (looks like success, isn't) or, once, a Spring Boot
"Whitelabel Error Page" `403 Forbidden`. Root-caused to two requirements:

1. **The `_csrf` token must be freshly minted immediately before the
   POST, in the same session.** Each `GET /orc-app/` mints a NEW token
   into the session (overwriting the previous one) — doing two GETs and
   then using the first GET's token fails even though it's from the
   "same session". The client (`src/client.py`) always does exactly one
   GET immediately followed by one POST per search, both on a single
   fresh `AsyncSession`.
2. **The POST must carry `HX-Request: true` together with
   `HX-Trigger`/`HX-Trigger-Name: saveRequest`** (matching the submit
   button's `id="saveRequest"`). `HX-Request` alone is not sufficient —
   without the trigger-name headers too, the controller falls back to
   redirecting to the bare homepage (a `302`) instead of returning the
   results fragment. With the full header set, the response is a clean
   `200` carrying response header `hx-trigger: namesFound` and the actual
   `<table id="search-results-tbl">` fragment.

`src/client.py` treats any POST that returns non-`200` or is missing the
`hx-trigger` response header as a retryable failure (fresh session +
fresh token on the next attempt) rather than a hard block, since this
consistently self-heals — confirmed empirically: 5 consecutive
fresh-session attempts (GET immediately followed by POST) all succeeded
with `200`/`hx-trigger: namesFound`, while a manually-corrupted-cookie
variant reproducibly triggered the `403` Whitelabel page.

### No server-side result cap — a real operational hazard

`DataTables` (loaded client-side) only paginates in the browser; the
server returns every match in one response, always. Confirmed:
`bizName=GHANA, searchType=cn` → **37,659 rows in an 11.48 MB response**.
`bizName=MINING, searchType=cn` → 13,198 rows. `bizName=GOLD, searchType=cn`
→ 12,057 rows. There is no request parameter that limits row count
server-side — `maxResultsPerQuery` in this actor's input can only truncate
the OUTPUT after the full response has already been downloaded and parsed.
Users should prefer specific/narrow query terms; the `_totalAvailable` /
`_truncated` fields on every output record make it obvious when a broader
query would have returned more.

### Validation errors (server-side, message passed through verbatim)

- Blank `bizName` → fragment contains `div.error-message` with text
  `Please enter name to search for`.
- An overly short `searchType=sw` query (tested: a single character) →
  same `div.error-message` wrapper, but with no message text at all
  (`error-message` div with only an empty child `<div></div>`). Treated
  identically — surfaced as `_error: "invalid_query"` with whatever
  (possibly empty) detail text was found.
- Zero matches for an otherwise-valid query → a `#no-search-results` div,
  `No data found`. Surfaced as `_error: "no_results"`, `_totalAvailable: 0`.

## Data quality note (upstream, not a bug in this actor)

The registry itself contains duplicate rows for the same business name —
observed on a real query (`bizName=MTN, searchType=sw`):
`MTNAMBE ENTERPRISE` (Sole Proprietor) appears twice, byte-identical, in
the same response. Per this project's raw-passthrough convention, matches
are NOT deduplicated — each row from the registry becomes its own dataset
record.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. No profile-specific blocking was ever observed on this target —
the friction here is entirely CSRF/htmx routing, not TLS fingerprinting.
