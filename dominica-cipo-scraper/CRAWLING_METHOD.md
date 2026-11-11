# Crawling Method — Dominica CIPO

**Last verified:** 2026-08-27

CIPO (Companies and Intellectual Property Office, a department of Dominica's
Ministry of National Security and Home Affairs) is the Commonwealth of
Dominica's official company/IP registry. Its public marketing site
(`cipo.gov.dm` / `www.cipo.gov.dm`) is Joomla; its transactional register —
an AngularJS single-page app branded "E-Filing" (internally "OCRS", built on
the same "FM"-prefixed module family used by the Foster Moore-style
platforms seen elsewhere in this project) — lives on a **separate
subdomain**, `efiling.cipo.gov.dm`.

## Domain-hint pivot (important)

Dominica has three CIPO-branded hosts. Two are dead ends; only the third is
the live public system:

1. **`registry.cipo.gov.dm`** — an older Alfa-XP ASP.NET WebForms portal
   ("2017 © CaseFlow Systems Ltd."). Its `OCRS_Home` landing tab requires
   login — confirmed by POSTing directly to its `ResolveTabHandler` AJAX
   endpoint as a guest and getting back `{"Html": "Welcome to E-Registry.
   Please enter your User name and Password to sign in.", "ErrorCode": 2}`.
   Its old public search API, `Entity.svc/GetCases` (a JSONP endpoint found
   via Wayback Machine 2017 snapshots, `parameterList={PageNumber, PageSize,
   SortingField, SortingDirection, CaseSearchCriteria:{SearchFilter,
   Number}}`), now 404s — replaced.
2. **`efileapi.cipo.gov.dm`** — referenced only in a stale JS comment
   (`Entity.js` on `registry.cipo.gov.dm`, last modified 2019) as the
   default `serviceurl` for an old "PublicNameSearch.svc" widget. The
   domain itself no longer resolves (NXDOMAIN) — dead.
3. **`efiling.cipo.gov.dm`** — the live, current system. Reached from
   `www.cipo.gov.dm`'s own "Name Search" menu item (confirmed via a Wayback
   Machine snapshot of the Joomla site, whose menu link target is
   `https://efiling.cipo.gov.dm/`). **This is the one this actor uses.**

## Robots.txt

**Absent (plain HTTP/IIS 404 — no file at all) on every host checked**:
`cipo.gov.dm`, `www.cipo.gov.dm`, `efiling.cipo.gov.dm`, and
`registry.cipo.gov.dm`. No Claude/AI-crawler mention anywhere — there is no
file to contain one.

## WAF / anti-bot

**None observed.** Plain IIS 10 / ASP.NET, no Cloudflare/`cf-ray`/challenge
markers. `curl_cffi` impersonating `chrome124`, `chrome131`, `safari17_0`,
and `edge101` all returned **byte-identical HTTP 200 JSON** for the same
query from the same IP within one recon session. No CAPTCHA is presented on
the search/detail API itself (a reCAPTCHA script is loaded by the Angular
shell, but only for the registration/e-filing/payment flows, not search).

## Login wall? No — for search

The Angular route `ocrs.search` (`/#/ocrs/search/:query/:option`,
`app_custom/ocrs/config-route.js`) is explicitly `access: {isFree: true}`.
Confirmed live: the underlying data call succeeds with **zero
`Authorization` header and zero cookies** — `userDataService
.getSecurityHeaders()` returns just `{"showSpinner": false}` when no access
token is in local/session storage, i.e. a genuine anonymous guest lookup.
(Company *registration*/e-filing is, unsurprisingly, login-walled — out of
scope for this actor, which only does public search + public director/
shareholder-of-record lookup.)

## The API

Everything goes through one endpoint, found by reading
`app/FM/Dataservice/services-data-service.js` and
`app_custom/ocrs/Directives/searchpagedgrid/searchpagedgrid-directive.js`:

```
POST https://efiling.cipo.gov.dm/api/api/1.0/services/loadInfoProc
Content-Type: application/json;charset=utf-8

{"input": "key=<0|1|2>,query=<term>", "name": "EntitySearch"}
```

**The doubled `/api/api/` is correct, not a typo introduced here.** The
page's own inline `configSettings` block sets `apiUrl:
'https://efiling.cipo.gov.dm/api'`, and `services-data-service.js`
concatenates `config.apiUrl + '/api/1.0/services/loadInfoProc'` on top of
that — upstream's own bug. Verified directly: a single `/api/1.0/...` 404s;
`/api/api/1.0/...` returns real data.

`key` selects which register field is searched (from the commented-out
`options` array in `app_custom/ocrs/Directives/search/search-directive.js`):

| `key` | Searches | Extra fields on each row |
|---|---|---|
| `0` | Entity name or registration number | — |
| `1` | Director surname | `Directors`, `Shareholders`, `Secretaries`, `Email`, `ApplicationId` |
| `2` | Shareholder surname/company name | same as `1` |

A follow-up per-entity lookup against the **same** endpoint fills in
directors/secretary/shareholders for `key=0` rows (which omit them):

```
{"input": "entityId=<EntityID guid from a search row>", "name": "EntityInfo"}
-> {"rows": [{"Directors": "...", "Secretaries": "...", "Schareholders": "..."}]}
```

Note upstream's own typo, **`Schareholders`** (not `Shareholders`) — kept
verbatim in the dataset per this project's raw-passthrough convention
rather than silently "corrected", since correcting it would make the field
name diverge from what upstream's own API actually returns.

An unknown or all-zero `entityId` does **not** 404 or error — it returns a
clean `{"Directors": null, "Secretaries": null, "Schareholders": null}` row.

## Two upstream bugs found (both surfaced as `_error: "upstream_error"` /
`"invalid_query"` in the dataset, not crashes)

1. **HTTP 500 with a JSON body, not HTTP 200.** Recon's first pass used
   `curl -s` without `-D -` and mis-read these as 200s — a second pass with
   headers showed they are genuinely `500 Internal Server Error`, just with
   a well-formed `{"message": "..."}` JSON body attached (`Content-Type:
   text/plain`, not even `application/json`, for the error case).
   `client.py`'s `_load_info_proc` deliberately does **not** gate on status
   code — it parses the body as JSON regardless of status and lets
   `extractor.parse_response` decide `rows` vs `message`.
2. **"Divide by zero error encountered."** Triggered by (a) an overly
   broad single-token query — a single letter (`a`), or a common whole word
   that matches very many rows (`international`) — and (b) a literal `=`
   character anywhere in the query. Looks like an unguarded page-count
   division on upstream's side; not a block, not WAF, not IP-related
   (reproduced identically over multiple TLS profiles and repeat calls).
3. **A literal `,` (comma) does NOT error — it silently truncates the
   query** at the first comma, because upstream naively splits the raw
   `"key=0,query=<term>"` string on comma server-side. Confirmed:
   `query=test,comma` matched **"New Testament Worship Centre"** — i.e.
   only `test` was actually searched, `,comma` was dropped without any
   signal. Because this fails *silently* rather than loudly, `extractor
   .validate_query()` rejects `,` and `=` in the query **before** sending
   it (`_error: "invalid_query"`) rather than risk returning quietly-wrong
   matches — this project's "fail loud, never fail silent" rule applies
   even when the failure mode is upstream's, not this actor's own.

## Data model is shallower than this project's Verne-based registries

Unlike `botswana-cipa-scraper` / `png-ipa-scraper` (Foster Moore "Verne",
Vue3, full view-tree with addresses/share-allocations/beneficial-owners),
Dominica's OCRS API only ever exposes:

- Search row: `EntityID`, `EntityName`, `EntityNumber`,
  `DateOfIncorporation`, `StatusName`, `TypeName`, `PrincipalOfficeAddress`
  (one free-text string, not structured), `registry`, `CaricomStatus`,
  `LoweredApplicationName` — plus `Directors`/`Shareholders`/`Secretaries`/
  `Email`/`ApplicationId` on director/shareholder-mode rows.
- Detail lookup: `Directors`/`Secretaries`/`Schareholders` as **plain
  comma-joined name strings**, not structured per-person records (no
  nationality, no address, no appointment date).

There is **no address structure, no share-allocation/percentage data, and
no beneficial-ownership disclosure anywhere on this API** — this reflects
what CIPO's own e-Filing portal exposes publicly, not a scraping gap.

## Sample entities tested

- **Paxum Bank Limited** (`2015/C3218`) — single exact-name match, directors
  + secretary on file, no shareholders on file for this one.
- **CIBAmericas Bank Inc.** (`2015/C3170`) — matched via entity name,
  director surname ("Brito"), and shareholder name ("Padilla") searches;
  each mode returns extra inline fields the others don't.
- **"bank"** (broad name search) — 55 matches, spanning Dominica's large
  offshore/IBC banking-registration sector (an artifact of Dominica's
  economic-citizenship/offshore-finance industry, not a scraping issue).
- **Zaman Tree Restaurant & Bar** (`14562A`, `TypeName: "Business By Firm"`)
  — a local business-name registration (not an IBC), confirms the search
  also covers plain sole-proprietor business names, not just companies.
- `zzzznonexistentxyz999` — confirms the clean `NoResultsFound` -> `_error:
  "not_found"` path (a genuinely empty `{"rows": []}`, no `message` key).
- `test,comma`, `a=b`, `international`, single-letter `a` — confirm the
  `invalid_query` / `upstream_error` handling documented above.

## Known limits

- No server-side pagination — the API returns every match in one response
  (or errors out on an overly broad one); `maxResultsPerQuery` is enforced
  client-side by slicing.
- No structured director/shareholder records (no nationality/address/
  appointment date) — just a joined name string, and only company-level,
  never person-level, detail.
- No documents, no filing history, no beneficial-ownership disclosure.
- Business-name-only registrations (`TypeName: "Business By Firm"`) mostly
  have null Directors/Secretaries/Shareholders on the detail lookup — this
  is what CIPO has on file for a sole proprietorship, not a gap.

## Diff cadence

Quarterly smoke test recommended — this is a smaller, apparently
less-actively-maintained AngularJS app than the newer Vue3 "Verne" builds
elsewhere in this project, but it still receives real registration traffic
(entities incorporated as recently as 2026-07 were found during recon), so
a backend change is plausible over a multi-month horizon.
