"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): ROCIP -- the Registry of Companies and
Intellectual Property, under Saint Lucia's Attorney General's Chambers --
runs its public search at `efiling.rocip.gov.lc` (an "OCRS" / Online Company
Registration System e-filing portal; the shared regional platform also
serves several other OECS/CARICOM registries -- the search results carry an
`ApplicationId`/`LoweredApplicationName` field confirming this, and
`selectCountryCompany-controller.js` lists Antigua & Barbuda, Barbados,
Belize, Dominica, Grenada, Guyana, Jamaica, Saint Lucia, St Vincent & the
Grenadines, Suriname, Saint Kitts, Nevis, and Trinidad & Tobago as tenants
of the same codebase). This actor only targets the `stlucia` tenant.

**HTTPS is not available at all** -- `https://efiling.rocip.gov.lc` fails the
TLS handshake outright (`SSL/TLS connection failed`, confirmed with `curl -v`
and independently with a plain socket connect -- port 443 accepts the TCP
connection but the server never completes a handshake). Everything must go
over plain `http://`. This is unusual for a government portal in 2026 but is
a straightforward site fact, not a WAF or blocking mechanism.

`robots.txt` does not exist on `efiling.rocip.gov.lc`, `eregistry.rocip.gov.lc`,
or `rocip.gov.lc` (all return HTTP 404 for `/robots.txt`, i.e. IIS's own
generic 404 page, not a custom disallow-everything file). No blanket
`Disallow: /`, no Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/
anthropic-ai mention anywhere -- there is simply no robots.txt to restrict
anything.

**No login, no CAPTCHA for search.** The portal is an Angular SPA
(`ng-app="app"`) that also supports filer registration/e-filing (that part
uses `angular-recaptcha` with a real site key) but the guest "Search for a
company or business name" flow -- linked directly from the Attorney
General's Chambers site (attorneygeneralchambers.com) and from
`rocip.gov.lc` -- never touches the CAPTCHA or any auth token. Confirmed:
a completely fresh, cookie-less `curl` POST to the search API below returns
a clean 200 with real data.

**The underlying JSON endpoint** (found by reading
`app/FM/Dataservice/services-data-service.js` for the Angular
`servicesDataService.loadInfoProc` call wired to the search results grid
directive, `app_custom/ocrs/Directives/searchpagedgrid/searchpagedgrid-directive.js`):

```
POST http://efiling.rocip.gov.lc/api/1.0/services/loadInfoProc
Content-Type: application/json

{"input": "key=0,query=<text>", "name": "EntitySearch"}
```

`key` selects the search mode, matching the three radio options on the real
search page (`app_custom/ocrs/Directives/search/search.html` /
`search-directive.js`):
- `key=0` -- Entities: company/business name OR registration number (both
  match the same field; a plain substring match, not a starts-with match --
  confirmed searching `2001/C135` also surfaced an unrelated entity whose
  free-text amalgamation note happened to mention that same number).
- `key=1` -- Directors: matches a director's surname across all entities
  that director is/was listed on. Confirmed working (returns full entity
  rows, exactly like `key=0`).
- `key=2` -- Shareholders: matches a shareholder's surname or a corporate
  shareholder's name. Confirmed reachable (HTTP 200, well-formed empty
  response) but **every query tried during recon returned zero rows**
  (common Saint Lucian surnames, "Limited", generic words) -- shareholder
  data does not appear to be populated in this search index at all
  (`Shareholders` is also `null` on essentially every `key=0`/`key=1` result
  row observed). This may be a privacy/non-disclosure choice rather than a
  bug; this actor exposes the option as-is and documents the empty-result
  reality rather than hiding it.

### Confirmed quirks

- **No pagination support.** The client-side directive never sends a page
  parameter, and probing the server with extra `PageSize=`/`PageNumber=`
  tokens appended to the `input` string made no difference. A broad query
  (`key=0,query=a`) reliably returns exactly 50 rows and stops -- this looks
  like a hard server-side `TOP 50` in the underlying stored procedure, not a
  page boundary. There is no way to page past it with this endpoint; this
  actor's `maxResultsPerQuery` cap is informational only above 50 -- it
  cannot retrieve more than the ~50 rows the server itself returns for a
  broad query. Narrowing the query text is the only way to see more of a
  large result set.
- **Zero matches is a clean `{"rows": []}`, HTTP 200.** No error page, no
  empty string body.
- **Search results already carry full detail** -- `EntityName`,
  `EntityNumber`, `DateOfIncorporation`, `TypeName` (legal form),
  `StatusName`, `PrincipalOfficeAddress`, `Email`, `Directors`,
  `Shareholders`, `Secretaries`, `ProfitStatus` all come back on the search
  row itself. A separate `name: "EntityInfo"` proc
  (`{"input": "entityId=<guid>", "name": "EntityInfo"}`) exists and is
  reachable, but it only echoes back `Directors`/`Secretaries`/a
  misspelled `Schareholders` field -- strictly less than the search row
  already has -- so this actor does not call it; the search response IS the
  detail record.
- Response `Server: Microsoft-IIS/7.5`, `X-Powered-By: ASP.NET`. No
  Cloudflare/Akamai/DataDome/PerimeterX markers anywhere, no `cf-ray`, no JS
  challenge. `X-Frame-Options: ALLOW-FROM http://dominicaef.ocrs.alfa.local/`
  incidentally confirms the shared multi-tenant platform theory (leaks
  Dominica's internal e-filing hostname on the *Saint Lucia* tenant's
  response headers).

`curl_cffi` `chrome124` is used for portfolio-wide consistency; a plain
`requests`/`httpx`-shaped baseline was not separately re-verified since
recon confirmed zero anti-bot measures of any kind on this target -- there
was nothing to bypass.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "http://efiling.rocip.gov.lc"
SEARCH_URL = f"{BASE_URL}/api/1.0/services/loadInfoProc"
SEARCH_PAGE_URL = f"{BASE_URL}/#/ocrs/search//0"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Referer": SEARCH_PAGE_URL,
    "X-Requested-With": "XMLHttpRequest",
}

# `key` values accepted by the search API, matching the real search page's
# radio options (Entities / Directors / Shareholders).
SEARCH_MODE_MAP = {
    "entities": "0",
    "directors": "1",
    "shareholders": "2",
}

# Server-side hard cap observed on broad queries -- there is no way to page
# past this with the public API (see recon summary above).
SERVER_ROW_CAP = 50

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
REQUEST_TIMEOUT = 40
