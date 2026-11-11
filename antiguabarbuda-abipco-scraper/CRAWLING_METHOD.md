# Crawling Method — Antigua and Barbuda ABIPCO Business Registry

**Last verified:** 2026-08-27

Antigua and Barbuda's company, business-name, and friendly-society register
is run by **ABIPCO** — the Antigua and Barbuda Intellectual Property and
Commerce Office (`abipco.gov.ag`). ABIPCO's own site describes its online
search as a *"Limited Internet Search Facility ... offered ... as a free
service to the public in ascertaining whether or not a company, business
name, charity or society could possibly be registered."*

## Robots.txt

`https://abipco.gov.ag/robots.txt` is a stock WordPress block (`Disallow:
/wp-admin/`, `Allow: /wp-admin/admin-ajax.php`) — no Claude/AI-crawler
mention, and nothing near the search/efiler paths. The Angular SPA host,
`https://ocrsagefiling.azureedge.net/robots.txt`, is `User-agent: *` with no
`Disallow` at all — allow-all. The real API host,
`https://eservicesapi.abipco.gov.ag/robots.txt`, doesn't exist (plain HTTP
404) — no restriction of any kind.

## WAF / anti-bot

None observed. `abipco.gov.ag` is plain `nginx` + PHP-FPM (WordPress).
`eservicesapi.abipco.gov.ag` is IIS/ASP.NET on what looks like Azure App
Service (`ARRAffinity` cookies, `X-Powered-By: ASP.NET`) — no Cloudflare, no
CAPTCHA, no TLS-fingerprint gate across ~30 recon requests made with bare
`curl`. The shipped client still impersonates a common browser TLS profile
(`curl_cffi` `chrome124`) for portfolio-wide consistency, not because a bare
baseline was observed to fail.

## Finding the real backend — three hops from the marketing site

The public-facing `abipco.gov.ag` is a WordPress brochure site; the actual
search tool lives elsewhere, found by following the site's own click-through
flow instead of guessing at API paths:

1. **`abipco.gov.ag/searchtheregister/`** — a WordPress page with a
   disclaimer checkbox ("I ACCEPT THE TERMS AND CONDITIONS") that reveals a
   "Search The Register" button. The button's handler is an inline
   `<script>`, not a plain link:
   ```js
   acceptButton.addEventListener("click", function (event) {
       event.preventDefault();
       window.location.href = 'https://ocrsagefiling.azureedge.net/#/ep/clientcontrol/search';
   });
   ```
2. **`ocrsagefiling.azureedge.net`** — an Angular SPA (`<title>e-Services`,
   meta description "ABIPCO E-services") served from an Azure CDN endpoint.
   Its main JS bundle has a build-time default `apiUrl` of
   `"https:/abipco.gov.ag/api/"` (note: malformed, single slash) — this
   turned out to be a dead end: `abipco.gov.ag/api/` 404s as a normal
   WordPress "page not found" (there is no reverse-proxy rule for `/api/`
   on that host at all).
3. The SPA's REAL runtime config isn't in the bundle — it's fetched at
   startup from **`ocrsagefiling.azureedge.net/assets/appsettings.json`**:
   ```json
   {"apiUrl": "https://eservicesapi.abipco.gov.ag/", "reCaptchaSiteKey": "...", ...}
   ```
   This is the actual, live API host used by the deployed app.

`eservicesapi.abipco.gov.ag` runs a generic government API framework
("DotGovServer" per its own Swagger `info.title`) shared across multiple
Antigua government e-services (its Swagger spec at `/swagger/docs/V1` also
lists `/passport/data/*` and `/AntiguaPayment/*` paths — this is a
whole-of-government API, not a registry-specific one).

### A shared-platform artifact worth noting (not relied upon)

One early recon fetch of `abipco.gov.ag/searchtheregister/` transiently
returned a *different country's* e-filing app HTML entirely — an AngularJS
app configured with `apiUrl: "http://efiling.rocip.gov.lc"` and
`portalName: "stlucia"` (Saint Lucia's Registry of Companies & Intellectual
Property). Re-fetching cleanly (fresh output file, no shared local cache)
consistently returned Antigua's own WordPress content on every subsequent
try. Most likely explanation: this vendor's platform is deployed per-country
from a shared codebase/template, and the one anomalous fetch hit stale
local tooling state, not ABIPCO's live server. Documented here in case a
future maintainer sees the same thing and wonders if it's real.

## What's genuinely public (no login, no CAPTCHA, no payment)

The SPA's entire "Search" feature — component `app-search`, on-page title
"Entity search by Name or Number", just one text box and one Search button —
is exactly ONE API call, reverse-engineered directly from the shipped
Angular bundle (lazy-loaded chunk, found by fetching every chunk file listed
in `runtime.<hash>.js`'s webpack chunk map and grepping for `NameSearch`):

```
GET https://eservicesapi.abipco.gov.ag/NameSearchPage/search?query=<text>&app=70000000-0000-0000-0000-000000000007
```

`app` is a **fixed GUID hardcoded in the Angular component** as
`this.islandId = "70000000-0000-0000-0000-000000000007"`. It identifies the
Antigua "island"/tenant on this shared multi-country platform (this explains
the Saint Lucia artifact above — same codebase, different `islandId` per
deployed country). It is not a secret or a per-session token: it's a static
constant baked into the publicly served JS bundle, and is hardcoded the same
way in this actor's `src/constants.py`.

No cookies, no session, no auth header, no CAPTCHA required — confirmed with
dozens of independent, stateless `curl` requests (no persisted cookie jar
needed between calls). Curiously, the endpoint's own Swagger listing shows
`"security":[{"oauth2":[]}]`, which looks like it should require a bearer
token; in practice it answers fully and correctly with zero authentication,
exactly as the public SPA itself calls it — the security annotation appears
to be a leftover from a shared controller base class, not enforced here.

A sibling endpoint, `/NameSearch/search?name=&pov=&formId=` (the `pov`
parameter is documented in Swagger only as `"Service"`, a string), was tried
first — no `pov` value tried during recon returned anything but a literal
`0`, and it is never called anywhere in the shipped SPA code. It was not
pursued further and is not used by this actor.

### Response shape

A bare JSON array — max 50 items, confirmed server-capped (a single-letter
query `"a"` and the word `"bank"` both returned exactly 50 rows) — each item
shaped like:

```json
{
  "EntityID": "ed8373de-c2bb-4f23-81a8-abea215c08b0",
  "EntityName": "Sandals Foundation Incorporated",
  "EntityNumber": "C222/08",
  "DateOfIncorporation": "2008-12-10T00:00:00",
  "LoweredApplicationName": "antigua",
  "StatusName": "Inactive",
  "TypeName": "Private Ordinary Company",
  "PrincipalOfficeAddress": "Hill & Hill Chambers, Long Street, St. John's, ANTIGUA AND BARBUDA",
  "registry": "Intellectual Property & Commerce Office",
  "CaricomStatus": "non-Antigua and Barbuda",
  "StatusReason": "Ceased/Struck-off/Removed"
}
```

Confirmed against real, current data — `EntityNumber` formats vary by entity
type (`C222/08` / `C4619` for companies, `B1414/2022` for business names,
`FS8/2017` for friendly societies); `TypeName` values observed: "Private
Ordinary Company", "Private Ordinary Foreign Company", "Business By
Individual", "Business By Corporation", "Friendly society"; `StatusName`
observed as "Active" and "Inactive" (with `StatusReason` populated, e.g.
"Ceased/Struck-off/Removed", only on non-Active rows).

**The name match is a genuine case-insensitive substring search**, not a
fuzzy/phonetic one like some sibling Foster-Moore-family registries in this
portfolio (e.g. Fiji ROC): querying `"LIAT"` matches `"Italiatelle
Limited"` because "…ITAL**IAT**ELLE…" genuinely contains the substring
"LIAT" — confirmed by inspection, not a false positive. `EntityNumber` also
matches through the same `query` field: `query=C8093` returns exactly the
one entity with that registration number.

A genuinely non-matching query returns a clean empty array `[]` (HTTP 200)
— unambiguous, no special-casing required.

## What's NOT public / not used

- **Blank or whitespace-only `query` → HTTP 500**
  (`System.Data.SqlClient.SqlException`, `"DGS Error. Please contact your
  administrator."`). Guarded client-side: this actor rejects empty/
  whitespace queries before making the request and emits `_error:
  "invalid_query"` instead of hitting the API.
- **Omitting `app` → HTTP 404** ("No HTTP resource was found..."). Always
  sent by this actor.
- **No detail endpoint.** There is no click-through from a search result to
  a fuller profile anywhere in the public SPA — the search row IS the full
  free-tier record. Directors, shareholders, and certified extracts sit
  behind ABIPCO's separate USD 50 paid certified-extract service (mentioned
  on ABIPCO's own site), which requires payment and is out of scope for
  this actor (no login, no payment, per this project's HTTP-only/
  public-data constraints).
- **No entity-type filter.** The search UI is a single text box + button,
  nothing else — `TypeName` in each result row is the only way to
  distinguish companies from business names from friendly societies. This
  actor does not fabricate a filter parameter the real UI doesn't expose.

## Sample entities tested

- `"Sandals"` → 2 matches: `Sandals Foundation Incorporated` (`C222/08`,
  Private Ordinary Company, **Inactive** / "Ceased/Struck-off/Removed") and
  `M.G Sandals Nation` (`B1414/2022`, Business By Individual, Active).
- `"LIAT"` → 10 matches spanning real substring hits (`Italiatelle
  Limited`), the defunct airline's pension/provident-fund shell companies
  (`LIAT (1974) PENSION PLAN LTD`, `LIAT (1974) PROVIDENT FUND LTD`), and a
  2025-incorporated `LIAT AIR` business.
- `"bank"` → 50 matches (server cap), including `Caribbean Commercial Bank
  (Antigua) Limited` (`C8093`) and `Eastern Caribbean Amalgamated Bank
  Limited` (`C84/09`).
- `"C8093"` (exact registration number) → exactly 1 match, confirming
  number-lookup works through the same `query` parameter.
- `"zzzznonexistentxyz999qqq"` (nonsense) → `[]`, confirms the clean
  `not_found` path.
- `"   "` (whitespace only) → HTTP 500 from upstream, confirms the client's
  `invalid_query` guard is necessary and correctly triggered.

## Diff cadence

Quarterly smoke test recommended — this is a government e-services platform
actively shared across multiple Caribbean jurisdictions (see the Saint Lucia
artifact above); a future redesign could rotate the `islandId` GUID, close
the currently-unauthenticated `/NameSearchPage/search` path, or move the
runtime `apiUrl` config to a different discovery mechanism.
