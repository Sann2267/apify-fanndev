# Crawling Method — Zambia PACRA Business Registry

**Last verified:** 2026-08-26

PACRA (Patents and Companies Registration Agency) is Zambia's official
government registrar for companies, business names, foreign companies, and
intellectual property. The main site (`pacra.org.zm`) is an informational
Next.js site; the actual "Business Search" feature this actor uses lives on
a separate subdomain, `search.pacra.org.zm`.

## Robots.txt

`GET https://pacra.org.zm/robots.txt` → **HTTP 404** (file does not exist —
Next.js's default 404 page is served instead, confirmed by content: 12,375
bytes of HTML, not an empty response). Same result on
`search.pacra.org.zm/robots.txt`. No `Disallow` directives, no
Claude/AI-scraping prohibition text anywhere — there is simply no
robots.txt on this domain at all.

## WAF / anti-bot

**None found anywhere in the search flow.** The actual data API,
`https://xatu.pacra.org.zm:8344`, is a plain ASP.NET Web API
(`server: Microsoft-IIS/10.0`, `x-powered-by: ASP.NET`,
`api-supported-versions: 1.0`) with:

- No API key or auth header of any kind — the frontend sends only generic
  `Cache-Control: no-store, no-cache, max-age=0` / `Pragma: no-cache` /
  `Expires: 0` headers (cache-busting, not auth).
- No session cookie, CSRF token, or ASP.NET viewstate — this is a modern
  ASP.NET Web API endpoint, not legacy WebForms.
- No CAPTCHA, no Cloudflare/DataDome/Akamai/etc. markers in headers or body.
- Confirmed working with a **bare `curl_cffi` GET carrying none of the
  frontend's own headers** — status 200 with real data every time.
- No rate limiting observed on 5 rapid back-to-back identical requests.

`curl_cffi` (`chrome124`) impersonation is still used in `client.py` as this
portfolio's default posture (per `.ai/CLAUDE.md` principle #2), not because
any block was ever observed. `proxyConfiguration` in the input schema
defaults to **off** (direct connection) for the same reason — there is
nothing here for a residential proxy to route around.

## Data source — reverse-engineering path

`search.pacra.org.zm` is a statically-exported Next.js SPA titled "PACRA |
Business Search" (`<meta name="description">`: *"Business Search is an
online service for The Patents and Companies Registration Agency of the
Republic of Zambia, that is used to search for registered companies in
Zambia."*). Its single search box says *"Enter Registered Name or
Registration Number"*.

Downloaded and read the SPA's own webpack chunks
(`/_next/static/chunks/pages/_app-*.js` — the file containing the Redux
action creators) to find the real API call, rather than guessing at
endpoints:

```js
s().get(
  "https://xatu.pacra.org.zm:8344/api/v1/Search/registrysearch?Searchtext="
    .concat(e, "&SortyBy=entity%20name&Direction=ASC"),
  { headers: { "Cache-Control": "no-store, no-cache, max-age=0",
               "Pragma": "no-cache", "Expires": "0" } }
)
```

`GET https://xatu.pacra.org.zm:8344/api/v1/Search/registrysearch?Searchtext=<query>&SortyBy=entity%20name&Direction=ASC`
→ 200, JSON array of entity objects. This is the **only** API call the
search flow makes — clicking a result in the UI does not fetch further
detail, it just opens a client-side modal populated from the same array
already in Redux state (confirmed by reading the `selectEntities` action
creator: it does `state.search.filter(e => e.entityID === id)[0]`, no
network call). **One HTTP request returns everything this actor needs.**

Verified live with real company names (`Zanaco`, `MTN`, `Airtel`, `Puma`,
`Zambia Sugar Plc`) — every field below is a genuine field observed in a
real response, not inferred from the JS source alone:

```json
{
  "entityID": "AE3059AB-91CC-47B4-8491-3BB99208E5DE",
  "entityTypeId": 1,
  "entityName": "ZAMBIA SUGAR PLC",
  "entityNumber": "119640002880",
  "registrationDate": "26/03/1964",
  "natureofBusiness": "Manufacture of sugar",
  "parValueStatus": "1",
  "annualReturnStatus": 1,
  "nominalCapitalStatus": 1,
  "entityStatus": "Active",
  "companyType": "Local Company - Public",
  "entityLimit": "Ordinary Company",
  "annualReturnReason": "Annual returns have been prepared and lodged in accordance with section 270 of the Companies Act. The next annual return will be due on 31/08/2026. ",
  "nominalCapitalReason": "The current nominal capital is within the legal limit.",
  "parValueReason": "The share structure is upto date.",
  "isicClasification": "3290. Other manufacturing n.e.c.",
  "isicDescription": "Other manufacturing n.e.c. ...",
  "beneficialOwnerStatus": 0,
  "beneficialOwnerReason": "Your company has not complied with the requirement to disclose information on the beneficial ownership of all the shares held by shareholders in your company as per sections 21 and 123 of the Companies Act. "
}
```

`entityTypeId` values observed live: `1` (Local Company) and `2` (Business
Name). `4` (Foreign Company) is named in the frontend's own tab-filter
logic (`entityTypeId === 4` → "Foreign Companies" tab) but never appeared
in any sample query run during this build — mapped defensively in
`constants.ENTITY_TYPE_LABELS` regardless.

## Known limits

- **Registration-number search does not work**, despite the site's own
  placeholder text claiming "Enter Registered Name or Registration
  Number". Tested with several confirmed-real registration numbers pulled
  straight out of live name-search results (`119640002880`,
  `120100086809`, `119970039548`), in full and in partial/substring form —
  every one returned zero matches. The endpoint appears to index/match
  `entityName` only. This actor therefore only supports **name-based**
  search (`companyName`/`companyNames`) — passing a registration number as
  input will simply return a zero-match record, not an error, since from
  the API's point of view it's just a query string that doesn't match any
  name.
- **50-result cap per query, no pagination.** Broad queries (`"Zambia"`,
  `"Limited"`, `"Trading"`) all returned exactly 50 results; no `page`,
  `limit`, `top`, or `skip` parameter is referenced anywhere in the
  frontend bundle. Use more specific company-name queries to stay under
  the cap.
- **No director/shareholder/full-certificate data.** This search endpoint
  returns registration + compliance-status data only. The site's own "Get
  Printout" button opens a *separate* portal (`portal.pacra.org.zm`), which
  requires an account and a paid certificate purchase for the full company
  record — out of scope per this project's no-login/no-paywall constraint,
  and not accessed by this actor.
- Minimum query length: the UI enforces "at least 4 characters" client-side
  only. The API itself has no consistent minimum — a 2-character query
  (`"MT"`) returned 50 results, but a 1-character query (`"M"`) returned 0
  (likely a full-text-index token-length quirk on PACRA's side, not a hard
  rule). No client-side minimum-length validation is enforced by this
  actor; queries are sent to the API as-is.
- `parValueStatus` is sent by the upstream API as a **string** (`"0"`/
  `"1"`), while `annualReturnStatus`, `nominalCapitalStatus`, and
  `beneficialOwnerStatus` are sent as **integers** (`0`/`1`) — an upstream
  inconsistency, passed through as-is rather than normalized (per this
  portfolio's raw-passthrough convention).
- `registrationDate` is passed through as PACRA's own `dd/mm/yyyy` string,
  not reformatted to ISO 8601.

## Diff cadence

Quarterly smoke test recommended (government sites change infrequently,
but a backend migration or new anti-bot layer is always possible).
