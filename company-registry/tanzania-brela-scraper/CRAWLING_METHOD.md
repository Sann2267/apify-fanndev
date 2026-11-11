# Crawling Method — Tanzania BRELA

**Last verified:** 2026-08-27

BRELA (Business Registrations and Licensing Agency, `brela.go.tz`) is
Tanzania's official business/company registry. Its transactional "Online
Registration System" (ORS) lives at `ors.brela.go.tz`, separate from the
marketing/services site `www.brela.go.tz`.

## Is this a public search, or filer-only?

Real risk flagged before starting: ORS systems in this project's registry
cluster have sometimes turned out to be filer-portal-first with no public
search (Rwanda's RDB was skipped for exactly this in the previous session).
BRELA is **not** that case: `GET
https://ors.brela.go.tz/orsreg/searchbusinesspublic` is a genuinely public,
anonymous search page — confirmed reachable and functional from a
completely fresh, cookie-less HTTP client. The page's own banner text is
explicit about the free/paid boundary:

> "IMPORTANT: this service is available only for those companies and
> business names which are registered in the Online Registration System
> (ORS) or which already completed data update / filing of annual return
> service to be transferred to the electronic Registry. For information
> about other business names and companies please use 'Request for a custom
> search result' e-service (available for registered users) or use current
> search procedures in BRELA office."

So: free anonymous search covers ORS-migrated records and returns
registration status/dates/address/subtype (see Output above) — full detail
(directors, shareholders) is explicitly paid/registered-user-only. This
actor only touches the free anonymous path.

## Robots.txt

`ors.brela.go.tz/robots.txt`:

```
User-agent: *
Disallow: /dontVisitMe/
```

One flat group, no Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/
anthropic-ai mention anywhere, and `/orsreg/...` (the only path this actor
touches) is not disallowed. `www.brela.go.tz/robots.txt` is also wide open
(`Disallow:` empty) — not used by this actor, but checked for completeness
since it's the same registrant/agency.

## WAF: real, but a payload-shape signature filter, not a bot gate

`ors.brela.go.tz` fronts requests with a generic "Web Application Firewall"
appliance (vendor unidentified from the block page itself — plain HTML,
`Event ID` / `Event Type: signature` table, no Cloudflare/Akamai/DataDome/
PerimeterX markers). During recon it returned **HTTP 403 for every single
request** — GET or POST, `curl_cffi` `chrome124`, with or without cookies —
where the query string or form-urlencoded body contained a parameter
literally named `object_type`, regardless of its value:

```
GET .../businesspublic.json?object_type=ET-BUSINESS&bn_name=Kilimanjaro  -> 403 WAF block page
GET .../businesspublic.json?object_type=ET                               -> 403 WAF block page
GET .../businesspublic.json?bn_name=Kilimanjaro   (no object_type)       -> 405 Method Not Allowed (reaches real endpoint)
```

This looked like a dead end (typical `requests`/`httpx` query-param or
form-encoded POST habits both hit it). The fix was reading the site's own
`js/lib.js` for how its search-results widget actually issues its AJAX call
(`core.form.jcall`):

```js
jcall: function(url, data, cb) {
  ...
  $.ajax($.extend({
    url: url, type: "POST",
    data: $.toJSON(data), dataType: "json",
    contentType: "application/json",
    ...
  }));
}
```

**The real front-end never sends form-urlencoded/query-string params at
all** — every call is `Content-Type: application/json` with a
`JSON.stringify`-d body. Switching to that exact shape (same `curl_cffi`
`chrome124` client, no other changes) made the WAF block vanish completely —
clean `200` on every subsequent call, no cookies needed. This confirms the
403 was a payload-shape signature match, not a TLS/JA3 or IP-based bot gate.

## The public search API

Found via the inline `listCtrl` config on the search page
(`table.actions.listUrl: "list/search/businesspublic.json"`):

```
POST https://ors.brela.go.tz/orsreg/list/search/businesspublic.json
Content-Type: application/json

{"bn_name": "Kilimanjaro", "PageSize": 50, "PageNumber": 1}
```

Response (columnar "map + rows" shape, presumably to save bandwidth):

```json
{
  "Map": ["id", "last_change_tracking_no", "cert_number", "reg_date",
           "incorporation_date", "legal_name", "subtype_name",
           "company_subtype", "object_type", "ba_category", "reg_status",
           "reg_status_name", "address", "cess_date", "update_date",
           "has_charges"],
  "Records": [[59664, "G180828-5513", "224344", "2011-07-27", null,
               "HYATT REGENCY DAR ES SALAAM THE KILIMANJARO", "Corporation",
               "BNT-CORP", "ET-BUSINESS", "BA1-473", "LES-RGC", "Registered",
               "Dar Es Salaam, ...", null, null, null], ...],
  "Result": "OK",
  "TotalRecordCount": 50
}
```

`extractor.py`'s `parse_search_response` zips `Map` with each `Records` row
using the response's OWN field list (not a hardcoded one), so an upstream
field addition/removal/reorder is handled automatically instead of silently
misaligning columns.

### Confirmed quirks

- **No session/cookies needed at all.** Every call in recon (~30+) worked
  from a fresh, cookie-less client — this is a real stateless public JSON
  API, unlike the session/transaction-based Verne protocol seen on some
  other registries in this project (e.g. Botswana CIPA).
- **`object_type` is optional.** Omitting it searches business names AND
  companies in one call. Passing `"ET-BUSINESS"` or `"ET-COMPANY"` filters
  to just one.
- **Field names are not actually type-gated server-side**, despite the
  front-end form having 4 separate fields (`bn_number`, `cm_number`,
  `bn_name`, `cm_name`) that show/hide based on the `object_type` radio
  button. Confirmed: sending a company's `cert_number` under `bn_number`
  with no `object_type` still finds that company; sending a business name
  under `bn_name` with no `object_type` finds it regardless of type. All
  four field names appear to query the exact same underlying
  `cert_number`/`legal_name` columns. This actor exploits that directly —
  it always sends the query under `bn_name` (non-numeric input) or
  `bn_number` (all-digits input), and never needs to duplicate the call
  under `cm_name`/`cm_number`.
- **Zero matches is clean and unambiguous**: `{"Records": [],
  "TotalRecordCount": 0}`, HTTP 200 — no error page, no empty-string body.
- **A broad, short query with a large page size reliably times out
  server-side** (confirmed: `{"bn_name": "a", "PageSize": 500}` — no
  response at all after 30s). This looks like an unindexed/expensive `LIKE`
  scan on the backend, not a block (it's not a WAF page, just a dead
  connection). `client.py` caps `PageSize` at 100 per request and pages
  through `PageNumber` for larger `maxResultsPerQuery` values, specifically
  to avoid tripping this.
- **No detail/drill-down endpoint reachable without login.** The search
  page's own `listCtrl` config has no `rowclick` handler wired to its
  results table (confirmed by reading `js/lib.js`'s row-click wiring logic:
  it's only invoked if the list config passes a `rowclick` callback, and
  this page's config doesn't) — clicking a result row does nothing in the
  real browser UI either, not just for this actor. This matches the page's
  own stated free/paid boundary (see above).

## TLS profile

`curl_cffi` `chrome124`, for portfolio-wide consistency. A plain
`requests`/`httpx` baseline was not separately re-verified (recon started
directly with `curl_cffi` per this project's default stack) — the WAF
signature issue above was confirmed to be about payload shape (JSON vs.
form/query-string), not TLS fingerprint, since the exact same client/profile
passes cleanly once the body format matches the real front-end's.
