"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): Antigua and Barbuda's company/business-name/
friendly-society register is run by **ABIPCO** -- the Antigua and Barbuda
Intellectual Property and Commerce Office (`abipco.gov.ag`, WordPress
marketing site, plain `nginx` + PHP-FPM, no WAF/CAPTCHA observed). ABIPCO
describes its own online search as a "Limited Internet Search Facility ...
offered ... as a free service to the public in ascertaining whether or not a
company, business name, charity or society could possibly be registered".

`robots.txt` on `abipco.gov.ag` is a stock WordPress block (`Disallow:
/wp-admin/`, `Allow: /wp-admin/admin-ajax.php`) -- no Claude/AI-crawler
mention, no disallow anywhere near the search/efiler paths.

## Finding the real backend (three redirect hops from the marketing site)

1. `abipco.gov.ag/searchtheregister/` -- a WordPress page with a "Search The
   Register" button gated behind a click-through Terms & Conditions
   checkbox. The button's `onclick` (inline `<script>`, not a plain `href`)
   does `window.location.href =
   'https://ocrsagefiling.azureedge.net/#/ep/clientcontrol/search'`.
2. `ocrsagefiling.azureedge.net` is an Angular SPA ("e-Services", meta
   description "ABIPCO E-services") served from an Azure CDN endpoint.
   `robots.txt` there is `User-agent: * / (no Disallow)` -- allow-all. The
   bundled `main.<hash>.js` has a build-time `apiUrl` of
   `"https:/abipco.gov.ag/api/"` (note: malformed, single slash) which turns
   out to be dead -- `abipco.gov.ag/api/` 404s (WordPress's own catch-all,
   there is no reverse-proxy rule for `/api/` on that host at all).
3. The SPA's REAL runtime config lives at
   `ocrsagefiling.azureedge.net/assets/appsettings.json` (fetched by an
   Angular `APP_INITIALIZER`, not visible in the static bundle's build-time
   default): `{"apiUrl": "https://eservicesapi.abipco.gov.ag/", ...}`. This
   is the actual, live API host.

`eservicesapi.abipco.gov.ag` has no `robots.txt` at all (plain 404 -- no
restriction of any kind). It's a "DotGovServer" (a shared, multi-tenant
government e-services API framework -- the same platform also serves
passport/permit services for Antigua's Ministry of Justice, per the
`/passport/data/*` and `/AntiguaPayment/*` paths visible in its own Swagger
spec at `/swagger/docs/V1`) hosted on IIS/ASP.NET (Azure App Service:
`X-Powered-By: ASP.NET`, `ARRAffinity` cookies).

**Confirmed multi-tenant/shared-template artifact during recon:** one
early fetch of `abipco.gov.ag/searchtheregister/` transiently returned a
completely different country's e-filing app HTML (`apiUrl:
"http://efiling.rocip.gov.lc"`, `portalName: "stlucia"`) -- almost
certainly a shared/generic build artifact or CDN edge-cache anomaly across
this vendor's Caribbean deployments, not something reproducible on demand.
Re-fetching cleanly (fresh temp file, no shared cache) consistently returns
Antigua's own WordPress content, so this is noted here as a curiosity, not
relied upon or worked around in the client.

## What's genuinely public (no login, no CAPTCHA, no payment)

The SPA's entire "Search" feature (component `app-search`, template
"Entity search by Name or Number") is exactly ONE API call, reverse-engineered
directly from the shipped Angular bundle (lazy chunk `8.<hash>.js`):

```
GET https://eservicesapi.abipco.gov.ag/NameSearchPage/search?query=<text>&app=70000000-0000-0000-0000-000000000007
```

`app` is a fixed GUID (`70000000-0000-0000-0000-000000000007`) hardcoded in
the Angular component as `this.islandId` -- it identifies the Antigua
"island"/tenant on this shared multi-country platform (explains the St
Lucia artifact above: same codebase, different `islandId` per country).
This is NOT a secret or a per-session token -- it's a static, public,
build-time constant baked into the publicly served JS bundle, safe to hardcode
here the same way.

No cookies, no session, no auth header, no CAPTCHA -- confirmed with dozens
of stateless one-shot `curl` requests during recon (no persisted cookie jar
needed between calls). The Swagger spec at `eservicesapi.abipco.gov.ag`
lists `/NameSearchPage/search` with `"security":[{"oauth2":[]}]`, which
looks like it should require a token -- in practice the endpoint answers
fully and correctly with zero auth, exactly as the public SPA itself calls
it. (The sibling `/NameSearch/search?name=&pov=&formId=` endpoint, also
visible in Swagger with a `pov` "Service" string parameter, was tried first
and never found a `pov` value that returned anything but `0` -- it isn't
used anywhere in the shipped SPA code, so it wasn't pursued further and
isn't used by this actor.)

### Response shape

A bare JSON array (max 50 items -- confirmed with a single-letter query
`"a"` and the word `"bank"`, both server-capped at exactly 50), each item:

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

Confirmed against real, current data: `EntityNumber` formats vary by entity
type (`C222/08` / `C4619` for companies, `B1414/2022` for business names,
`FS8/2017` for friendly societies); `TypeName` observed values include
"Private Ordinary Company", "Private Ordinary Foreign Company",
"Business By Individual", "Business By Corporation", "Friendly society";
`StatusName` observed as "Active" and "Inactive" (with `StatusReason`
populated, e.g. "Ceased/Struck-off/Removed", only for non-Active entities).

**The match algorithm is a genuine case-insensitive SUBSTRING search on the
entity name** (confirmed: query `"LIAT"` matches `"Italiatelle Limited"`,
which contains the substring "…ITALIATELLE…" -> positions 4-7 spell
"LIAT") -- unlike some sibling registries on other Foster-Moore-family
platforms in this portfolio (e.g. Fiji ROC) where the equivalent field is a
loose fuzzy/phonetic match. `EntityNumber` also matches via the same `query` field (confirmed:
`query=C8093` against this exact endpoint returns exactly the one entity
with that registration number).

A genuinely non-matching query returns a clean empty array `[]` (HTTP 200)
-- reliable, unambiguous "no results" signal, no special-casing needed.

## What's NOT public / not used

- A blank or whitespace-only `query` returns **HTTP 500**
  (`System.Data.SqlClient.SqlException` / "DGS Error. Please contact your
  administrator.") -- guarded against client-side (empty/whitespace queries
  are rejected before making the request, surfaced as `_error:
  "invalid_query"`).
- Omitting the `app` parameter entirely returns **HTTP 404** ("No HTTP
  resource was found...") -- always sent.
- There is no separate "detail" endpoint reachable from the public SPA for
  an individual `EntityID` -- the search result row IS the full public
  record ABIPCO's own free search tool exposes. Directors, shareholders,
  and certified extracts are the USD 50 paid/certified-extract tier
  mentioned on ABIPCO's own site, and are out of scope for this actor (no
  login, no payment, per this project's constraints).
- No entity-type filter exists in the search UI (single text box + Search
  button, nothing else) -- `TypeName` in each result row is the only way to
  distinguish companies from business names from friendly societies, and
  this actor does not attempt to fabricate a filter parameter the real UI
  doesn't have.

## Diff cadence

Quarterly smoke test recommended -- this is a government e-services
platform shared across multiple Caribbean jurisdictions (the St Lucia
artifact above shows active cross-deployment churn); a future redesign
could change the `islandId` GUID, close the currently-unauthenticated
`/NameSearchPage/search` path, or move the runtime `apiUrl` config again.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://eservicesapi.abipco.gov.ag"
SEARCH_URL = f"{BASE_URL}/NameSearchPage/search"

# Fixed, public, build-time tenant GUID for Antigua & Barbuda on this shared
# multi-country "DotGovServer" e-services platform -- see constants.py
# module docstring for how this was found and confirmed not-secret.
ISLAND_ID = "70000000-0000-0000-0000-000000000007"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Confirmed empirically: the server always returns at most this many rows
# regardless of how broad the query is (tested with a single-letter query).
SERVER_RESULT_CAP = 50

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
