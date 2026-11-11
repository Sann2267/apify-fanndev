# Crawling Method — Kingdom of Tonga Business Registry (MCCTIL)

**Last verified:** 2026-08-27

## Target discovery

Search confirmed the real, current official portal: **businessregistries.gov.to**,
"Kingdom of Tonga Registry Service", operated by the **Ministry of Commerce,
Consumer, Trade, Innovation and Labour (MCCTIL)** — the successor name for
the Ministry of Trade and Economic Development (MTED), which commissioned
the platform upgrade with Asian Development Bank / Pacific Private Sector
Development Initiative support (went live 11 December 2024). The site's own
meta description states outright: *"The Tonga Registry Services system is a
single, fully electronic solution hosting both the Personal Property
Securities Registry and Business Entities Registry. Both registries are
searchable by the general public free of charge. It is accessible 24/7."*
Sources: [ADB press release](https://www.adb.org/news/tonga-s-innovative-online-business-registry-goes-live-adb),
the site itself.

## Robots.txt

`https://businessregistries.gov.to/robots.txt` returns a plain **HTTP 404**
— the file does not exist. No restriction of any kind, and therefore no
`ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/`anthropic-ai`
mention either (there's nothing to mention).

## WAF / anti-bot

**None observed.** Plain IIS/ASP.NET responses, no Cloudflare/`cf-ray`, no
CAPTCHA, no bot-challenge HTML across ~40 requests during recon with bare
`curl_cffi` `chrome124` (no warmup-then-retry dance needed, first try
worked). A short burst of rapid same-session requests produced one
transient HTTP 403 (`{"Message":"Search page has expired. Please refresh
the page."}`) and, separately, one HTTP 429 — both self-resolved on a fresh
token re-harvest / short backoff and are treated as ordinary
small-government-system rate limiting, not an anti-bot wall (matches the
same pattern already documented for `png-ipa-scraper` on this identical
platform).

## Same platform as PNG IPA — Foster-Moore-derived, `/Api/Corp/*` JSON REST

`/corp/search.aspx` is a classic ASP.NET WebForms page shell
(`__VIEWSTATE`/`aspnetForm` postback scaffolding present, unused for the
real data) embedding `<vue-entity-search>`, the exact same Vue component
already reverse-engineered for `png-ipa-scraper`. `/Corp/EntityProfile.aspx?id=<guid>`
is the equivalent profile page. Both call a clean JSON REST API directly:

```
GET /Api/Corp/SearchCorp?Term=<name>&PaginationPageSize=<n>&PaginationCurrentPage=<n>&ExcludePending=true&OrderBy=&OrderAscending=true
GET /Api/Corp/GetCorpProfile?id=<CorpId guid>
```

Confirmed live (not just by JS reading) against real, current data — see
"Sample entities tested" below.

### The `PA-Token` header — identical rotating anti-CSRF mechanism

Every request under `/Api/` must carry a `PA-Token` request header, sourced
from a hidden `<input id="paToken" value="...">` embedded in the search
page's HTML, and rotating on every API response (the fresh value comes back
in the response's own `PA-Token` header and must be threaded into the next
call). A stale/missing token gets `HTTP 401`/`403`. `client.py`'s
`TongaRegistryClient` reproduces this exactly like `png-ipa-scraper`'s
`IpaClient`: harvest once from `/corp/search.aspx`, thread the rotating
value, re-harvest once on a 401/403 before giving up.

Token harvest is always done via the search page, never via
`EntityProfile.aspx?id=<corp_id>` — confirmed live that an invalid/
nonexistent `corp_id` still renders that page with `<input type="hidden"
name="ctl00$paToken" id="paToken" />` (no `value=` attribute at all), same
quirk as PNG IPA. The token is session-bound, not page-bound, so harvesting
from the always-available search page works uniformly.

### Search results — real, immediately public, no login

`SearchCorp` returns `{"records": [...], "totalRecordCount": <int>,
"warningMessage": null}`. Each record: `CorpId` (GUID), `Name`, `AltName`,
`RegistrationNumber(Formatted)`, `Type`/`TypeId` (Company/Overseas
Company/Business Name/Business Licence/Foreign Certificate variants),
`Status`/`StatusId`, `RegistrationDateFormatted`, `PriorNames`,
`BusinessActivities`, `RegisteredOfficerAddress`. An empty-result term gets
a clean `200` with `records: []`. `GetSearchConfiguration` (no auth issue)
exposes the full `CorpTypes` enum (8 entity-type codes, fewer than PNG's 13
— no separate Associations/Business Groups categories on this registry) —
hardcoded into `constants.CORP_TYPE_IDS` since it's small and stable.

### Profile lookup — notably MORE public than PNG IPA on the same platform

`GetCorpProfile?id=<guid>` returns a large JSON object. Unlike PNG IPA
(where the ownership/control layer is fully gated), **this registry's
`Directors`, `Members` (shareholders), `ShareAllotments`, `Addresses`
(including each individual officer's own residential address), and
`CorpFilings` arrays come back POPULATED for anonymous access** —
confirmed on `A & A CONSULTANTS (TONGA) LIMITED` (`LC9005612`): 2 real
directors and 2 real shareholders with full names, nationality, appointment
dates, and residential addresses, plus 16 filings on record, all while
`IsAuthorized: false` and `IsLoggedin: false`.

`Officers`, `Secretaries`, `Owners`, and `BeneficialOwners` were empty on
every entity tested (a handful of companies and business licences) — could
reflect a stricter server-side gate specific to those role types, or simply
no data on file for the sample tested; not distinguishable without a login
this actor deliberately never attempts. All arrays (empty or populated) are
passed through as raw passthrough, not hidden or special-cased.

A `GetCorpProfile` call for a nonexistent/invalid CorpId does **not** 404 —
it returns `HTTP 200` with a placeholder `Corp` object where both
`CompanyName` and `RegistrationNumber` are the literal string `"N/A"`,
confirmed live against the all-zero GUID. `extractor.is_not_found_profile()`
detects this and emits `_error: "not_found"`.

## Sample entities tested

- **"Bank"** search term (5+ matches) — ANZ (Australia and New Zealand
  Banking Group Limited) appears three times under three different entity
  types (`Business Licence` BL612, `Foreign Certificate - Overseas Company`
  FI2858, `Overseas Company` OC9000008), confirming one real-world business
  can hold multiple registry entries of different types.
- **"A & A CONSULTANTS"** (exact match, `LC9005612` / company, `BL2313` /
  business licence) — full profile with 2 directors, 2 shareholders (same
  individual, `Lafitani 'inoke AFU`), residential address, 16 filings.
- Deliberately-invalid all-zero GUID — confirms the clean `_error:
  "not_found"` path, not a crash or a false match.
- Deliberately-invented garbage search term
  (`zzzznonexistentxyz999`) — confirms the clean `_error: "no_results"` path.

## Known limits

- `Officers`/`Secretaries`/`Owners`/`BeneficialOwners` were empty on every
  entity tested for anonymous access (see above) — passed through as-is.
- No pagination beyond `PaginationPageSize`/`PaginationCurrentPage`
  (server-honored, same as PNG IPA) — `maxResultsPerTerm` (default 20, max
  200) caps how many are pulled per term.
- The registry also hosts a Personal Property Securities Registry (`/str/*`,
  "PPSA Search") and separate Name Availability / Name Reservation search
  pages on the same public/no-login/`PA-Token` pattern — out of scope for
  this actor, a plausible target for a future one.

## Diff cadence

Quarterly smoke test recommended — same maintained commercial platform
family as `png-ipa-scraper`; a version upgrade could change the API shape
or the `PA-Token` mechanism, though neither has shown signs of changing
frequently across this portfolio's other entries on this platform.
