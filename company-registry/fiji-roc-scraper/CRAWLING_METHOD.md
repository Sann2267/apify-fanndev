# Crawling Method — Fiji Registrar of Companies (ROC)

**Last verified:** 2026-08-26/27

Fiji's company and business-name register is run by the **Registrar of
Companies (ROC)**. Correct agency confirmed via web search + on-site copy:
not the Reserve Bank of Fiji, not FRCS directly (ROC sits administratively
under the Fiji Financial Intelligence Unit, but the site itself is part of
Fiji's whole-of-government **Digital Transformation Programme**,
`digital.gov.fj`). The public marketing/menu pages live at
`mobile.digital.gov.fj`; the actual transactional application is a separate
ASP.NET Core MVC + Kendo UI site at `roc.digital.gov.fj` (cookies
`CL.Fiji.Roc.Web.Public`, `.AspNetCore.Antiforgery.*`) — a from-scratch .NET
Core build, not the Verne/Foster Moore platform seen on Botswana CIPA in this
portfolio.

## Robots.txt

Both `https://roc.digital.gov.fj/robots.txt` and
`https://mobile.digital.gov.fj/robots.txt` return a plain **HTTP 404** — the
file does not exist on either host. No restriction of any kind, and
therefore no `ClaudeBot`/`Claude-Web`/`Claude-User`/`Claude-SearchBot`/
`anthropic-ai` mention either (there's nothing to mention).

## WAF / anti-bot

Cloudflare fronts both domains (`Server: cloudflare`, `CF-RAY` response
header on every request) but **no challenge was ever issued** across ~40
requests during recon, using plain `curl` with no TLS-fingerprint
impersonation at all. The shipped client still impersonates a common browser
profile for portfolio-wide consistency, not because a bare baseline was
observed to fail.

## What's genuinely public (no login)

`https://roc.digital.gov.fj/BuyInformation/Search` — despite the name ("Buy
Information"), *searching* requires no login and no payment. The page's own
copy says so directly: "To use this service, no login is required but a
valid email address is needed" (email is only collected at the paid
purchase step, never reached by this actor).

### Step-by-step

1. `GET /BuyInformation/Search` (plain navigation) — sets the session
   cookies (`CL.Fiji.Roc.Web.Public`, `.AspNetCore.Antiforgery.*`) and
   embeds a fresh `__RequestVerificationToken` in the form HTML
   (`<input name="__RequestVerificationToken" type="hidden" value="...">`).
2. `POST /BuyInformation/Search` (`application/x-www-form-urlencoded`,
   header `X-Requested-With: XMLHttpRequest`) with body
   `SearchNumber=<value>&SearchName=<value>&__RequestVerificationToken=<token>`,
   using the SAME cookies as step 1. The response body is a **bare integer**
   (e.g. `10`) — nothing else, not JSON-wrapped.
3. `GET /BuyInformation/GetSearchResults?take=<n>&skip=<n>&page=<n>&pageSize=<n>`
   (same cookies, same `X-Requested-With` header) — returns the real Kendo
   grid JSON:
   ```json
   {"Data": [{"Id": null, "EntityName": "VODAFONE FIJI", "EntityNumber": "10658",
     "Type": "COMPANY", "Status": "ACTIVE",
     "Url": "BuyInformation/Application?entityNumber=10658&isAuthChallenged=false",
     "LegalElement": "PTE LIMITED", "FilteredFields": [...]}],
    "TotalRecords": 10}
   ```
   `FilteredFields` is internal Kendo grid filter metadata (repeats the same
   field names twice) and is dropped by `extractor.build_search_record`.

This was verified against real, current data — `EntityNumber=10658` ->
`VODAFONE FIJI`, `Type: COMPANY`, `Status: ACTIVE`, and dozens of other
spot-checked numbers/names during recon, including a mix of `ACTIVE`,
`CEASED`, and `DE-REGISTERED` companies and business names.

## What's NOT public: the full entity profile

Each row's `Url` (e.g. `BuyInformation/Application?entityNumber=10658&isAuthChallenged=false`)
is the "view / buy this record" step. Fetching it — even with the exact same
cookies used for the search — returns **HTTP 302** to:

```
https://auth.digital.gov.fj/connect/authorize?client_id=...&redirect_uri=https%3A%2F%2Froc.digital.gov.fj%2Fsignin-oidc&response_type=code%20id_token&...
```

A full OIDC login wall (a "ROC Pass" account). This matches the paid
"purchase of entity information" feature advertised on
`mobile.digital.gov.fj/EServices/Index`: *"The section allows the search of
entity records and purchase of entity information."* Directors,
shareholders, registered address, filing history, incorporation date, and
certificate downloads all sit behind this login+payment wall. Per this
project's no-login constraint, this actor stops at the search step and does
not attempt to authenticate or pay for the detail view. The row's `Url` is
passed through as `entityDetailUrl` purely as a reference pointer.

### A second, narrower public endpoint (not used)

`/NameSearch/Search` (reachable from `RocEServices/LocalCompanyMenu`, the
"Application for registration as a company" flow) is a name-availability
checker for people about to register a brand-new company. Same
GET-token-then-POST-then-GET-grid shape, but the grid
(`/NameSearch/GetNameSearchList`) returns only `{Name, Status,
SubmissionDate, SubmissionDateString, LegalElement, ItemCount}` — no entity
number, no entity type. Strictly less useful than `/BuyInformation/Search`
for the same public-access tier, so it was not built on.

## Two confirmed upstream gotchas

### 1. `SearchName` is not a substring/"contains" filter

`/BuyInformation/Search`'s HTML form has only two inputs, `SearchNumber` and
`SearchName` — no `SearchType` field (unlike the sibling `/NameSearch/Search`
form, which has CONTAINS/SIMILAR/COMBINE radio buttons). Posting an explicit
`SearchType` value anyway makes no observable difference — the server simply
ignores it on this endpoint.

`SearchName` instead performs some loose, undocumented fuzzy/phonetic-style
match. Reproduced across multiple fresh sessions:

| Query | Result count |
|---|---|
| `"VODAFONE FIJI"` (exact, real company name) | 12,413 |
| `"ZEBRACORP123UNIQUE"` (nonsense) | 1,489 |
| `"qqqqqqqqqqqqqq"` (nonsense) | 1,311 |
| `"A"` (single letter) | 239,507 |
| `"zzzznonexistentxyz999"` (nonsense) | 2 — real, unrelated companies `SENNUNG` and `SINONGKEN` |

None of this is substring matching by name. `SearchNumber`, by contrast, IS
a reliable substring match on `EntityNumber` — a genuinely nonexistent
number (`999999999`) correctly returns count `0`, and `"10658"` correctly
returns exactly the entities whose number contains that substring.

**Combining both fields in one POST behaves as an AND filter** and can cut
through the `SearchName` noise: `SearchNumber=10658&SearchName=VODAFONE`
returns exactly 1 result, versus thousands for `SearchName=VODAFONE` alone.
This actor doesn't expose that combination as a separate input (it only
sends one field per query, chosen by `searchBy`), but it's worth knowing if
extending this actor later.

### 2. Very large result sets silently return an empty grid

When the `/BuyInformation/Search` POST count is small-to-moderate (confirmed
working up to 30,653), `/BuyInformation/GetSearchResults` returns the real
paged data. Once the count reaches roughly six figures (confirmed failing at
245,549 and 275,463), the SAME grid endpoint returns **HTTP 200** with
`{"Data": [], "TotalRecords": 0}` — indistinguishable from a genuine
zero-match response by shape alone, but the POST step's own count was very
much nonzero.

This actor treats "nonzero POST count, but the grid page comes back empty"
as a distinct `_error: "result_set_too_broad"` outcome (see
`extractor.ResultSetTooBroad`, raised in `main.search_one_query`) rather
than silently reporting `not_found` or silently returning zero rows for a
query that upstream says has plenty of matches.

## Sample entities tested

- `10658` (entity number) — `VODAFONE FIJI`, `COMPANY`, `ACTIVE`, plus 9
  other entities whose number contains that substring (business names and a
  de-registered company).
- `999999999` (entity number, deliberately nonexistent) — count `0`,
  confirms the clean `not_found` path.
- `"Vodafone"` (entity name) — 6 matches spanning both `COMPANY` and
  `BUSINESS NAME` types, `ACTIVE`/`CEASED` statuses.
- `"A"` (entity name, deliberately broad) — count 239,507, confirms the
  `result_set_too_broad` path fires instead of returning an empty/misleading
  result.

## Diff cadence

Quarterly smoke test recommended — this is a live, actively-developed
government .NET Core application (part of an ongoing "Digital FIJI"
programme); a future redesign could close off the currently-open
`/BuyInformation/Search` search-without-login path, or change the
antiforgery/session mechanics.
