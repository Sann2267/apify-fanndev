# Crawling Method — Saint Lucia ROCIP

**Last verified:** 2026-08-27

ROCIP (Registry of Companies and Intellectual Property) is Saint Lucia's
official business/company registry, established by the Companies &
Intellectual Property (Registry) Act (No. 12 of 2000, Cap 13.02) and run
under the Attorney General's Chambers within the Ministry of Justice. It's
linked from the Attorney General's Chambers site
(`attorneygeneralchambers.com/p/search-for-a-company-or-business-name`) and
from `rocip.gov.lc` itself.

## Finding the real portal

Search results surfaced several ROCIP-branded hosts:
- `rocip.gov.lc` / `www.rocip.gov.lc` — informational site, redirects its
  `/robots.txt` request to `eregistry.rocip.gov.lc` (also 404, no file).
- `eregistry.rocip.gov.lc` — reachable over plain HTTP but not the search UI
  itself.
- **`efiling.rocip.gov.lc`** — the actual "E-Filing" Angular SPA
  (`ng-app="app"`, `<title>E-Filing</title>`) that hosts the "Search for a
  company or business name" flow linked from the AG Chambers page. This is
  the target this actor uses.

## Is this a public search, or filer-only?

The portal is primarily a filer/registration e-filing system (it ships full
`UserManagement` login/registration/password-reset modules and an
`angular-recaptcha` integration for those flows), but the **Entity/
Director/Shareholder search is a separate, genuinely anonymous guest flow**
(`app_custom/ocrs/Views/search/search-controller.js` /
`search-directive.js`) that never touches login or the CAPTCHA. Confirmed
with a completely fresh, cookie-less `curl` POST returning real data with no
auth header of any kind.

## Robots.txt

None of the three hosts checked serve a robots.txt at all:

```
http://efiling.rocip.gov.lc/robots.txt   -> 404 (IIS generic 404 page)
http://eregistry.rocip.gov.lc/robots.txt -> 404 (IIS generic 404 page)
http://rocip.gov.lc/robots.txt           -> 302 -> eregistry.rocip.gov.lc/robots.txt -> 404
```

No blanket `Disallow: /`, no Claude/ClaudeBot/Claude-Web/Claude-User/
Claude-SearchBot/anthropic-ai mention anywhere — there's simply no file to
restrict anything.

## HTTPS does not work on this host

`https://efiling.rocip.gov.lc/` fails the TLS handshake outright:

```
$ curl -v https://efiling.rocip.gov.lc/
* Trying 24.92.151.139:443...
* schannel: failed to receive handshake, SSL/TLS connection failed
```

Port 443 accepts the TCP connection but never completes a TLS handshake —
this is a site configuration fact (the server apparently isn't listening
with TLS on that port at all), not a WAF or IP block. Every request in this
actor uses plain `http://`.

## No WAF, no CAPTCHA for search

Plain `Microsoft-IIS/7.5` / `X-Powered-By: ASP.NET`. No Cloudflare/Akamai/
DataDome/PerimeterX markers, no `cf-ray`, no JS challenge page, no rate
limiting observed across ~30 recon requests. A bare `curl` POST with no
impersonation, no cookies, and no session token returns clean JSON every
time.

One incidental finding: the response's own
`X-Frame-Options: ALLOW-FROM http://dominicaef.ocrs.alfa.local/` header
leaks another tenant's internal hostname, confirming this "OCRS" (Online
Company Registration System) codebase is a shared, multi-country e-filing
platform — `selectCountryCompany-controller.js` on the same page lists
Antigua & Barbuda, Barbados, Belize, Dominica, Grenada, Guyana, Jamaica,
Saint Lucia, St Vincent & the Grenadines, Suriname, Saint Kitts, Nevis, and
Trinidad & Tobago as tenants. This actor only targets the `stlucia` tenant
(the default/only tenant reachable at `efiling.rocip.gov.lc`).

## The public search API

Found by reading `app/FM/Dataservice/services-data-service.js` (the
Angular `servicesDataService.loadInfoProc` factory) for the call wired up
by the search-results grid directive,
`app_custom/ocrs/Directives/searchpagedgrid/searchpagedgrid-directive.js`
(`reLoadPageContent` -> `servicesDataService.loadInfoProc({input: "key="+option+",query="+query, name: "EntitySearch"})`):

```
POST http://efiling.rocip.gov.lc/api/1.0/services/loadInfoProc
Content-Type: application/json

{"input": "key=0,query=Bank of Saint Lucia", "name": "EntitySearch"}
```

Response — a plain `{"rows": [...]}` list of full objects (not a columnar
map+records shape):

```json
{
  "rows": [
    {
      "EntityID": "c1060220-36b1-467c-908a-d0915ffc6a75",
      "EntityName": "Bank of Saint Lucia Limited",
      "EntityNumber": "2001/C135",
      "DateOfIncorporation": "2001-06-30T00:00:00",
      "TypeName": "Private Ordinary Company",
      "ApplicationId": "10000000-0000-0000-0000-000000000001",
      "LoweredApplicationName": "stlucia",
      "PrincipalOfficeAddress": " SAINT LUCIA",
      "Email": null,
      "StatusName": "Amalgamated",
      "Directors": "Stewart Haynes,Frank V. Myers, ...",
      "Shareholders": null,
      "Secretaries": null,
      "ProfitStatus": null
    }
  ]
}
```

`key` selects the search mode, matching the three radio options
(`Entities`/`Directors`/`Shareholders`) on the real search page
(`app_custom/ocrs/Directives/search/search-directive.js`):

| `key` | Mode | Confirmed behavior |
|---|---|---|
| `0` | Entities | Matches company/business name OR registration number — plain substring match. Searching `2001/C135` also surfaced an unrelated entity whose free-text amalgamation note happened to mention that number, confirming it's a `LIKE '%...%'`-style match, not a starts-with/exact match. |
| `1` | Directors | Matches a director's surname across every entity that director is/was listed on. Returns full entity rows, identical shape to `key=0`. Confirmed working (e.g. `query=Charles` -> 50 rows capped, real director names embedded in each `Directors` field). |
| `2` | Shareholders | Reachable, returns a well-formed `{"rows": []}`, but **every query tried returned zero rows** — common Saint Lucian surnames (Smith, Charles, Joseph), and generic words. `Shareholders` is also `null` on essentially every `key=0`/`key=1` result observed. This looks like shareholder data simply isn't populated/indexed for search in this system (possibly a disclosure policy choice), not a bug in this actor. |

### Confirmed quirks

- **No pagination.** The front-end directive never sends a page number, and
  probing with extra `PageSize=`/`PageNumber=` tokens appended to the
  `input` string (e.g. `"key=0,query=a,PageSize=10,PageNumber=2"`) made no
  observable difference — a broad one-letter query (`query=a`) reliably
  returns exactly **50** rows regardless. This looks like a hard
  `SELECT TOP 50` in the underlying stored procedure. There is no way to
  retrieve more than 50 rows for a broad query through this endpoint;
  narrowing the search text is the only lever available.
- **Zero matches is a clean `{"rows": []}`, HTTP 200.** No error page.
- **A separate `EntityInfo` proc exists but adds nothing.**
  `{"input": "entityId=<guid>", "name": "EntityInfo"}` is reachable and
  returns `{"rows": [{"Directors": "...", "Secretaries": null,
  "Schareholders": null}]}` (note the upstream typo, "Schareholders") —
  strictly a subset of what the search row already carries (no address, no
  status, no incorporation date). This actor does not call it; the search
  response IS the full public detail record.
- Response headers: `Server: Microsoft-IIS/7.5`, `X-Powered-By: ASP.NET`,
  `Content-Type: application/json; charset=utf-8`, a fresh
  `ASP.NET_SessionId` cookie is set but never required on subsequent calls
  (confirmed: repeat calls with no cookie jar at all still succeed).

## TLS profile

`curl_cffi` `chrome124`, for portfolio-wide consistency. Since the
connection is plain HTTP (no TLS handshake occurs at all — see above), the
impersonation profile only affects HTTP header shape/ordering, not any
TLS-layer fingerprint; it costs nothing to keep for consistency with the
rest of this project's actors.
