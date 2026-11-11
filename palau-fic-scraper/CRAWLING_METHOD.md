# Crawling Method — Republic of Palau Business Registry (FIC)

**Last verified:** 2026-08-27

## Target discovery

Web search for "Palau company registry search online" surfaced a public
notice from the Palau Financial Institutions Commission (FIC) itself
(`ropfic.org/2025/01/20/public-notice-new-online-corporate-registry/`)
announcing a **new Online Corporate Registry**, launched 20 January 2025
alongside a new Corporations Act, linking to **palauregistries.pw** — "the
Republic of Palau Financial Institutions Commission Registry Services". The
site's own meta description states outright: *"The Palau Registry Services
system is a single, fully electronic solution hosting both the Personal
Property Securities Registry and Business Entities Registry. Both
registries are searchable by the general public free of charge. It is
accessible 24/7."* This is the real, current, official portal — not a
third-party SEO/KYC blog guess.

## Robots.txt

`https://palauregistries.pw/robots.txt` returns a plain **HTTP 404** (IIS
default 404 body) — the file does not exist. No restriction of any kind,
and therefore no `ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/
`anthropic-ai` mention either (there's nothing to mention). The related
`.gov`-adjacent domains (`www.palaugov.pw`, `ropfic.org`) both run WordPress
with a stock `robots.txt` (`Disallow: /wp-admin/` only) — no bot-blocking
signal anywhere in the chain.

## WAF / anti-bot

**None observed.** Plain IIS/ASP.NET responses (`X-Powered-By: ASP.NET`),
no Cloudflare/`cf-ray`, no CAPTCHA, no bot-challenge HTML. `curl_cffi`
`chrome124` worked on the first try for every request during recon — no
warmup-then-retry dance needed.

## Same Foster-Moore-derived platform as PNG IPA, Tonga MCCTIL, Fiji ROC,

## Solomon Islands SBR — all already in this portfolio

`/corp/search.aspx` is a classic ASP.NET WebForms page shell
(`__VIEWSTATE`/`aspnetForm` postback scaffolding present, unused for the
real data) whose real search/profile UI talks to a clean JSON REST API:

```
GET /Api/Corp/SearchCorp?Term=<name>&PaginationPageSize=<n>&PaginationCurrentPage=<n>&ExcludePending=true&OrderBy=&OrderAscending=true
GET /Api/Corp/GetCorpProfile?id=<CorpId guid>
```

Confirmed live (not just by JS reading) against real, current data — see
"Sample entities tested" below.

### The `PA-Token` header — identical rotating anti-CSRF mechanism

Every request under `/Api/` must carry a `PA-Token` request header, sourced
from a hidden `<input id="paToken" value="...">` embedded in the search
page's HTML. The token rotates on every API response (the fresh value comes
back in the response's own `PA-Token` header and must be threaded into the
next call). A stale/missing token gets `HTTP 401`/`403`. `client.py`'s
`PalauRegistryClient` reproduces this exactly like the other actors on this
platform in the portfolio: harvest once from `/corp/search.aspx`, thread the
rotating value, re-harvest once on a 401/403 before giving up.

Confirmed live: reusing the exact same already-consumed token for a second
call returns `HTTP 403` with body
`{"Message":"Search page has expired. Please refresh the page.","ErrorReferenceNumber":null}`
— a fresh token harvest immediately resolves it back to a normal `200`
response. `client.py` treats this the same as any other 401/403.

Token harvest is always done via the search page, never via
`EntityProfile.aspx?id=<corp_id>` — matching the documented quirk on this
same platform elsewhere in the portfolio (an invalid/nonexistent `corp_id`
can render that page with an empty `#paToken`). The token is session-bound,
not page-bound, so harvesting from the always-available search page works
uniformly.

### Search results — real, immediately public, no login

`SearchCorp` returns `{"records": [...], "totalRecordCount": <int>,
"warningMessage": null}`. Each record: `CorpId` (GUID), `Name`, `AltName`,
`RegistrationNumber(Formatted)`, `Type`/`TypeId` (Palau For Profit
Corporation / Foreign For Profit Corporation / Palau Nonprofit Corporation /
Foreign Nonprofit Corporation — only 4 types on this registry, fewer than
Tonga's 8, matching the homepage's own meta keywords), `Status`/`StatusId`,
`RegistrationDateFormatted`, `PriorNames`, `BusinessActivities`. An
empty-result term gets a clean `200` with `records: []`.
`GetSearchConfiguration` (no auth issue) exposes the full `CorpTypes` enum —
hardcoded into `constants.CORP_TYPE_IDS` since it's small and stable. It
also exposes `CorpStates` (10 status codes, e.g. Active/Registered/
Revoked/Voluntarily Dissolved/Administratively Dissolved) and a 20+-item
`CorpActivity` enum, not surfaced as a separate filter in this actor's input
(the free-text `Term` search already covers the common case).

### Profile lookup — rich public access, matching Tonga rather than PNG on

### this same platform

`GetCorpProfile?id=<guid>` returns a large JSON object. Confirmed live on
**"ASIA PACIFIC COMMERCIAL BANK, INC."** (registration `10000895`):
`Directors` (4, full names + Malaysian nationality + appointment date +
residential address), `Officers` (2, e.g. President, same address
richness), `Members`/shareholders (3), `ShareAllotments` (3),  `Addresses`
(2: Registered Office + Postal), and `CorpFilings` (1) all come back
**populated for anonymous access** — while `IsAuthorized: false` and
`IsLoggedin: false`.

`Secretaries`, `Owners`, `BeneficialOwners`, `Mortgages`, and `Documents`
were empty on the one entity tested — could reflect a stricter server-side
gate specific to those role/record types, or simply no data on file for
this sample; not distinguishable without a login this actor deliberately
never attempts. All arrays (empty or populated) are passed through as raw
passthrough, not hidden or special-cased.

A `GetCorpProfile` call for a nonexistent/invalid CorpId does **not** 404 —
it returns `HTTP 200` with a placeholder `Corp` object where both
`CompanyName` and `RegistrationNumber` are the literal string `"N/A"`,
confirmed live against the all-zero GUID. `extractor.is_not_found_profile()`
detects this and emits `_error: "not_found"`.

## Sample entities tested

- **"Bank"** search term (5 matches) — "ASIA PACIFIC COMMERCIAL BANK, INC."
  (Palau For Profit Corporation, `10000895`), "BANK OF GUAM CO." (Foreign
  For Profit Corporation, `10001283`), "BANK OF HAWAII CORPORATION"
  (Foreign For Profit Corporation, `10050268`), "BANKPACIFIC, LTD.", and one
  more — all real, currently-registered financial institutions.
- **"ASIA PACIFIC COMMERCIAL BANK, INC."** full profile (`CorpId`
  `0668ffe3-79c4-4d9e-866c-48c385ed97f6`) — 4 directors, 2 officers, 3
  shareholders, 3 share allotments, 2 addresses, 1 filing, all populated
  with no login.
- Deliberately-invalid all-zero GUID — confirms the clean `_error:
  "not_found"` path, not a crash or a false match.
- Deliberately-invented garbage search term
  (`zzzznonexistentxyz999`) — confirms the clean `_error: "no_results"` path.
- Deliberately reused (already-consumed) `PA-Token` — confirms the
  `{"Message":"Search page has expired..."}` / `HTTP 403` re-harvest path.

## Known limits

- `Secretaries`/`Owners`/`BeneficialOwners`/`Mortgages`/`Documents` were
  empty on the one entity tested for anonymous access (see above) — passed
  through as-is.
- No pagination beyond `PaginationPageSize`/`PaginationCurrentPage`
  (server-honored) — `maxResultsPerTerm` (default 20, max 200) caps how
  many are pulled per term.
- The registry also hosts a Personal Property Securities Registry, and
  separate Name Availability / Name Reservation search pages on the same
  public/no-login/`PA-Token` pattern (`/namesearch.aspx`,
  `/namereservations/search.aspx`) — out of scope for this actor, a
  plausible target for a future one.

## Diff cadence

Quarterly smoke test recommended — same maintained commercial platform
family as `png-ipa-scraper` / `tonga-mcctil-scraper` / `fiji-roc-scraper` /
`solomonislands-sbr-scraper` in this portfolio; a version upgrade could
change the API shape or the `PA-Token` mechanism, though neither has shown
signs of changing frequently across this portfolio's other entries on this
platform. Palau's registry is also new (went live January 2025), so it may
see more active development/fixes than the longer-established peers.
