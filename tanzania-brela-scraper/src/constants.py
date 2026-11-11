"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): BRELA -- Tanzania's Business Registrations and
Licensing Agency -- runs its public-facing "Online Registration System"
(ORS) at `ors.brela.go.tz` (separate from the marketing/services site
`www.brela.go.tz`). The ORS is primarily a filer/applicant transactional
portal (needs an account to register a business or file returns), BUT it
also ships a genuinely public, anonymous, no-login search page:
`GET https://ors.brela.go.tz/orsreg/searchbusinesspublic`. The page's own
banner text confirms this: "this service is available only for those
companies and business names which are registered in the ORS or which
already completed data update / filing of annual return... For information
about other business names and companies please use 'Request for a custom
search result' e-service (available for registered users)." -- i.e. the free
public search only covers ORS-migrated records, and full profile detail
(directors/shareholders/etc.) is explicitly gated behind a paid, registered-
user e-service. This actor only touches the free, public, anonymous path.

`robots.txt` on `ors.brela.go.tz` is a single flat `User-agent: *` group:
`Disallow: /dontVisitMe/` -- no blanket block, no Claude/ClaudeBot/Claude-Web/
Claude-User/Claude-SearchBot/anthropic-ai mention anywhere, and the one path
touched by this actor (`/orsreg/...`) is not disallowed. `www.brela.go.tz`'s
robots.txt is also wide open (`Disallow:` empty).

**WAF found, but it's a false-positive-prone signature filter, not a real
bot gate.** `ors.brela.go.tz` fronts requests with a generic "Web
Application Firewall" appliance (vendor unidentified from the block page;
plain HTML with an `Event ID` / `Event Type: signature` table, no
Cloudflare/Akamai/DataDome/PerimeterX markers). It returns HTTP 403 with
that block page for ANY request -- GET or POST, with or without a session
cookie -- where the parameter named `object_type` is sent as a URL-encoded
query string or form-urlencoded body, REGARDLESS of its value (even
`object_type=ET` triggers it; a completely unrelated made-up param name like
`object_type` seems to itself be the signature match, not the value).
**This is a total dead end if you copy typical requests-library query-param
habits.** The fix: the real front-end JS (`js/lib.js`'s `core.form.jcall`)
never sends form-urlencoded data at all -- every AJAX call is
`Content-Type: application/json` with a `JSON.stringify`-d body
(`contentType: "application/json", data: $.toJSON(e)`). Sending the exact
same shape -- a JSON POST body, not query-string/form params -- sails
through the WAF with a clean 200 every time. This was found by reading
`js/lib.js` for the AJAX call the search page's `jtable`-style list widget
actually issues, not by trial and error on header names.

**The underlying JSON endpoint (found in the page's inline `listUrl`
config):**

```
POST https://ors.brela.go.tz/orsreg/list/search/businesspublic.json
Content-Type: application/json

{"object_type": "ET-BUSINESS" | "ET-COMPANY", "bn_name": "<text>",
 "PageSize": 50, "PageNumber": 1}
```

Confirmed quirks:
- No cookies/session needed at all -- works from a completely fresh,
  cookie-less client. This is a genuinely stateless, public, anonymous
  JSON API, not a session-scoped SPA transaction protocol.
- `object_type` is optional -- omitting it searches BOTH business names and
  companies in one call.
- The parameter NAME you use for the query text/number does not actually
  gate which entity type it matches server-side: `bn_number`, `cm_number`,
  `bn_name`, and `cm_name` were all confirmed to search the exact same
  underlying `cert_number`/`legal_name` columns regardless of `object_type`
  (e.g. `{"bn_number": "<a company's cert_number>"}` with no `object_type`
  still finds that company). The front-end only ever sends one field at a
  time because its form UI hides/shows fields based on the `object_type`
  radio button, not because the backend requires field/type matching. This
  actor exploits that: it always sends the query under `bn_name` (text) or
  `bn_number` (all-digits), never needs to duplicate into cm_name/cm_number.
- Zero matches returns a clean `{"Records": [], "TotalRecordCount": 0}` --
  no error, easy to detect.
- A broad, single-character query (`bn_name: "a"`) with a large `PageSize`
  (500) reliably times out server-side (30s+, no response at all) -- this
  looks like the backend doing an unindexed/expensive LIKE scan, not a
  block. `PageSize` is capped at 100 per request by this actor for exactly
  this reason; `maxResultsPerQuery` above 100 pages through `PageNumber`.
- Every field observed in the response `Map` (`id`,
  `last_change_tracking_no`, `cert_number`, `reg_date`,
  `incorporation_date`, `legal_name`, `subtype_name`, `company_subtype`,
  `object_type`, `ba_category`, `reg_status`, `reg_status_name`, `address`,
  `cess_date`, `update_date`, `has_charges`) is passed straight into the
  output record -- this response shape IS the complete public data BRELA
  exposes for free; there is no separate/richer "detail" endpoint reachable
  without an ORS login (confirmed: the search-results jtable widget on the
  page has no `rowclick` handler wired up at all -- clicking a result row is
  a dead click in the real UI too, not just for this actor).

`curl_cffi` `chrome124` is used for portfolio-wide consistency; a plain
`requests`/`httpx` baseline was not separately re-verified (recon started
directly with `curl_cffi` per this project's default stack), and the WAF
signature issue above was confirmed to be about payload shape, not TLS
fingerprint (the same client/profile passes cleanly once the JSON body
format matches the real front-end).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://ors.brela.go.tz"
SEARCH_URL = f"{BASE_URL}/orsreg/list/search/businesspublic.json"
SEARCH_PAGE_URL = f"{BASE_URL}/orsreg/searchbusinesspublic"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Referer": SEARCH_PAGE_URL,
    "X-Requested-With": "XMLHttpRequest",
}

# object_type values accepted by the search form.
ENTITY_TYPE_MAP = {
    "any": None,
    "business": "ET-BUSINESS",
    "company": "ET-COMPANY",
}

PAGE_SIZE = 100
MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
REQUEST_TIMEOUT = 40
