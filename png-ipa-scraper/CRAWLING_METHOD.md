# Crawling Method — PNG IPA Business Entities Registry

**Last verified:** 2026-08-27

## Target discovery — `ipa.gov.pg` vs `www.ipa.gov.pg`

The brief named `ipa.gov.pg`. The bare (non-`www`) hostname fails TLS
hostname verification entirely (`curl_cffi` `chrome124`: `SSL: no
alternative certificate subject name matches target hostname 'ipa.gov.pg'`)
— the real, working site is `www.ipa.gov.pg` only. `www.ipa.gov.pg/robots.txt`
is a plain HTTP 404 (`Microsoft-IIS/10.0` stock 404 page) — no robots.txt
exists at all, so there's nothing disallowed and no plain-English
AI/scraping prohibition to find. No terms-of-use/disclaimer link was found
anywhere on the homepage either.

The homepage itself (34.6 KB, `curl_cffi` `chrome124`, first try, no
warmup-then-retry dance needed) states outright in its `<meta
name="description">`: *"The Papua New Guinea Registry Services system is a
single, fully electronic solution hosting both the Personal Property
Securities Registry and Business Entities Registry. Both registries are
searchable by the general public free of charge. It is accessible 24/7."*
This is the same domain/system the "IPA Online" registry lives on — there is
no separate registry subdomain; `/corp/search.aspx` and `/Corp/EntityProfile.aspx`
on `www.ipa.gov.pg` are the real search/profile pages this actor targets.

## robots.txt / WAF

No robots.txt (404, see above). No CDN/WAF fingerprint of any kind — every
response is a bare Azure App Service (`x-powered-by: ASP.NET`,
`ARRAffinity`/`ARRAffinitySameSite` cookies), no `cf-ray`, no bot-challenge
HTML, no CAPTCHA anywhere. A short burst of 10 sequential `/Api/Corp/SearchCorp`
calls in one session all returned clean `200`s, but a heavier burst of
~15 requests in immediate succession (multiple recon scripts run back to
back) did trigger one `HTTP 429`, which resolves after ~15–20s — treat this
as an ordinary small-government-system rate limit, not an anti-bot wall.
`client.py`'s retry-with-backoff handles it as a transient error.

## Data source — S1/S2, `/Api/Corp/*` JSON REST API

### The page shell is ASP.NET WebForms; the actual search/profile UI is not

`/corp/search.aspx` and `/Corp/EntityProfile.aspx?id=<guid>` are classic
ASP.NET WebForms pages (`__VIEWSTATE`/`__EVENTVALIDATION`/`aspnetForm`
postback scaffolding is present in the HTML) — but that scaffolding belongs
to an unused, login-gated internal "workflow" admin feature that shares the
same page template. **The actual public search box and results grid are
rendered entirely client-side**: `/corp/search.aspx` embeds
`<vue-entity-search>` (a Vue 2 component, webpack-chunked, resolved by
decoding `/vue/dist/main/app.js`'s chunk-hash map to fetch
`/vue/dist/main/<hash>.chunk.js`), and `/Corp/EntityProfile.aspx` embeds an
AngularJS controller (`EntityCtrl`, `ng-init="vm.ControllerInit('<guid>', 0)"`,
defined in `/bundles/js/entityprofile`). Both call a clean JSON REST API
directly — **no `__VIEWSTATE` postback is needed for the real data**, only
plain `GET` requests:

```
GET /Api/Corp/SearchCorp?Term=<name>&PaginationPageSize=<n>&PaginationCurrentPage=<n>&ExcludePending=true
GET /Api/Corp/GetCorpProfile?id=<CorpId guid>
```

Both were reverse-engineered by decoding the webpack chunk map in
`/vue/dist/main/app.js` (`p.u` chunk-hash function + `p.p="/vue/dist/main/"`
public path) down to the actual component source
(`vue-entity-search`'s `getRequestParam()`/`getSearchResultsByTermUrl`, and
`entityprofile`'s `vm.GetProfile()`), not from any DevTools network trace.

### The `PA-Token` header — a rotating anti-CSRF token, not a CAPTCHA or login

Every request under `/api/` (case-insensitive path match) must carry a
`PA-Token` request header. Confirmed via
`/bundles/js/GlobalAjaxInterceptor` (a small, unminified script): it patches
`XMLHttpRequest`/`fetch` globally so any call to an `/api/` path
auto-attaches this header from a hidden `<input id="paToken">` on the
current page, and **rotates it on every response** — the server returns a
fresh value in the response's own `PA-Token` header, which must be threaded
into the *next* call. A stale/missing token gets `HTTP 401
{"Message":"Invalid API Token"}`. There is no CAPTCHA, no OAuth, no login
involved in obtaining or refreshing this token — it's purely a
session-bound value harvested from an ordinary page fetch.

`client.py`'s `IpaClient` reproduces this: harvest the token once (regex
`id="paToken"(?:\s+value="([^"]*)")?` against a page fetch — the `value=`
attribute is OPTIONAL in the markup, see below), thread the rotating value
returned on each API response into the next call, and re-harvest once on a
401/403 before giving up.

**Token harvest is always done via the search page (`/corp/search.aspx`),
never via `EntityProfile.aspx?id=<corp_id>`** — even for profile lookups.
Reason: an invalid/nonexistent `corp_id` makes `EntityProfile.aspx`
302-redirect server-side to a generic `/Error.aspx?reason=Error&ref=<n>`
page, whose `#paToken` hidden input has **no `value=` attribute at all**
(`<input type="hidden" name="ctl00$paToken" id="paToken" />`). The token is
bound to the session, not to which page fetched it, so harvesting from the
always-available search page works uniformly for every `corp_id`, good or
bad — bad IDs are instead handled gracefully by the JSON API itself (see
below).

### Search results — real, immediately public, no login

`SearchCorp` returns `{"records": [...], "totalRecordCount": <int>,
"warningMessage": null}`. Each record is a real match: `CorpId` (GUID, used
for the profile lookup), `Name`, `AltName`, `RegistrationNumber(Formatted)`,
`Type`/`TypeId` (Companies/Business Names/Associations/Business
Groups/Overseas Companies/...), `Status`/`StatusId` (Registered/Cancelled/
Removed/Struck-Off/In Liquidation/...), `RegistrationDateFormatted`,
`PriorNames`, `BusinessActivities`, `RegisteredOfficerAddress`. An empty
`Term` gets `HTTP 400 {"Message":"error_searchcriteria_required"}`; a
no-match term gets a clean `200` with `records: []`. Pagination is
`PaginationPageSize`/`PaginationCurrentPage`, both server-honored (confirmed
page 2 of a 57,852-match term returned the next 10, not a repeat of page 1).
`GetSearchConfiguration` (no params, no auth issue) exposes the full
`CorpTypes` enum (13 entity-type codes) used for the `entityTypeId` input
filter.

### Profile lookup — real public fields, but officer/shareholder data is gated

`GetCorpProfile?id=<guid>` returns a large JSON object: `Corp` (the primary
entity record — company name, registration number, status, registered
office + postal address as nested objects, share count/currency, annual
return due date, and for some entities a registrant contact
email/phone captured at registration), plus `Addresses`, `Activities`,
`CorpFilings`, `Mortgages`, and — notably — `Officers`, `Directors`,
`Secretaries`, `Shares`, `Owners`, `BeneficialOwners`.

**The latter group (who actually controls/owns/directs the entity) is
consistently empty for anonymous access.** Verified across 5+ entities of
varying age and type (a 1996-incorporated public company, a company
registered the same day as this recon, several decades-old "Removed"
entities) — every single one came back with `IsAuthorized: false`,
`IsLoggedin: false`, and every officer/director/shareholder/owner array
empty, regardless of the entity's actual age or size. This is server-side
gating on the authentication flag, not missing data — the public,
free-of-charge search the homepage advertises covers entity status/identity/
address/activity lookups, not the ownership-and-control layer, which
requires an authenticated IPA Online account. **This actor does not attempt
to obtain or use such an account (no-login policy)** — the empty arrays are
passed through as-is (raw passthrough, not hidden or faked) so this
limitation is visible in every dataset row rather than silently absent.

An invalid/nonexistent `corp_id` passed to `GetCorpProfile` does **not**
404 — it returns `HTTP 200` with a placeholder `Corp` object where both
`CompanyName` and `RegistrationNumber` are the literal string `"N/A"`.
`extractor.is_not_found_profile()` detects this and emits `_error:
"not_found"` instead of a garbage record.

## Known limits

- Officer/director/secretary/shareholder/beneficial-owner detail is not
  available without an IPA Online account login (see above) — out of scope
  per this project's no-login policy, and clearly documented in the output
  schema rather than silently omitted.
- Only the Business Entities Registry (`/corp/*`) was targeted. The site
  also hosts a Personal Property Securities Registry (`/str/*`, "PPSR
  Search") on the same public/no-login/`PA-Token` pattern — out of scope
  for this actor, a plausible target for a future one.
- A short burst of ~15 rapid requests triggered one `HTTP 429`
  (self-resolving after ~15-20s); `maxConcurrency` defaults to a modest 4 and
  each search-term/corp-id task uses its own `IpaClient`/session/proxy IP
  (matching this portfolio's standard per-item-client pattern), which should
  keep steady-state load well under whatever threshold triggered that one
  observed 429.
- Common single-word search terms (e.g. "TRADING") match tens of thousands
  of entities (`totalRecordCount` observed up to 57,852) — `maxResultsPerTerm`
  (default 20, max 200) caps how many are pulled per term, not a registry
  limitation.

## Diff cadence

Quarterly smoke test recommended — this is a small, actively-maintained
government system (a company was seen registered the same day as this
recon), but the underlying API/token mechanism has no indication of
changing frequently.
