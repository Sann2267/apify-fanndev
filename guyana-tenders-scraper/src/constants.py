"""Endpoints and recon summary for Guyana's official Government Procurement
Opportunities Website.

Recon summary (2026-08-27): Guyana's public tender/procurement notice board
is **eprocure.gov.gy**, launched February 2026 by the National Procurement
and Tender Administration Board (NPTAB, under the Ministry of Finance) as a
"centralized Procurement Opportunities Website to enhance transparency and
access" (see Department of Public Information press release and Stabroek
News, both 2026-02-25). It replaces piecemeal PDF postings on individual
ministry sites and the older `npta.gov.gy` WordPress site as the single
authoritative source for current bid opportunities.

## Two portals exist -- only one is used by this actor

- `www.npta.gov.gy` -- the legacy NPTA WordPress site (still online, has a
  "Tenders Awarded" page). Its `robots.txt` carries an explicit Cloudflare
  Managed-Content block group naming `ClaudeBot` (`Disallow: /`), alongside
  `GPTBot`, `CCBot`, `Google-Extended`, `Bytespider`, `Amazonbot`,
  `Applebot-Extended`, `meta-externalagent`, and
  `CloudflareBrowserRenderingCrawler`. **Not used by this actor at all** --
  avoided entirely per this portfolio's stop-condition policy for any
  Claude-named disallow, even though the site the task actually asked to
  scrape (the *current* NPTAB tender portal) is a different host.
- `eprocure.gov.gy` -- the new centralized portal this actor scrapes.
  `robots.txt` returns `200 OK` with an **empty body** (`Content-Length: 0`)
  -- no restrictions of any kind, no Claude/anthropic mention (there's
  nothing to mention).

## No login wall -- confirmed on every path used

The homepage sets an anonymous `sid=Guest` / `system_user=no` session cookie
automatically (standard Frappe framework behavior, see below) on every
request, logged-out or not. Both API methods this actor calls return full
data to a plain, cookie-less request with no authentication of any kind. A
staff login likely exists elsewhere in the app (for agencies publishing
notices) but was never encountered on any public read path.

## Backend: Frappe framework, custom app "doctracker"

Response headers (`X-Page-Name`, the `sid`/`system_user`/`full_name`/
`user_id` cookie set) and the `/api/method/<app>.<module>.<method>` URL
shape are textbook **Frappe** (the framework behind ERPNext) conventions.
The custom app is named `doctracker`; the two whitelisted public methods
used here live in its `powerbi` module -- likely built to also feed an
internal Power BI dashboard, repurposed for this public-facing page.

Frappe's own error envelope (`{"exc_type": "...", "_server_messages": "..."}`,
HTTP 417) is used directly as this actor's `_errorDetail` when the detail
endpoint 417s on an unknown/unpublished `project_id` -- confirmed live:
`{"exc_type": "ValidationError", ...\"message\":\"Project not found or not
published\"...}`.

## TLS profile: no WAF at all -- every profile tested returns 200

Tested `chrome124`, `chrome131`, `safari17_0`, `edge101` via `curl_cffi`,
and also plain `curl` with no TLS impersonation at all -- **all return a
plain 200 with identical JSON**. No Cloudflare/Akamai/DataDome/etc headers
anywhere in the response. `chrome124` is used here purely for portfolio
consistency (see `.ai/CLAUDE.md` default stack), not because it was
required to unblock anything.

## Two public JSON API methods, no pagination

| Method | Purpose | Params | Notes |
|---|---|---|---|
| `doctracker.api.powerbi.get_public_bid_opportunities` | List **currently advertised** bid opportunities | none (extra query params are silently ignored -- confirmed `?status=Awarded` returns byte-identical output to no params at all) | Small live list (4 records at recon time) -- this is a "what's open right now" bulletin board, not a historical archive. No pagination exists because there is nothing to paginate: one call returns the complete current list. |
| `doctracker.api.powerbi.get_public_project_advertisement` | Full rich-text advertisement for one project | `project_id` (required) | Returns the full formatted notice (scope, instructions, footer with contact addresses) as HTML fragments, plus the complete document list (the list endpoint only surfaces the *first* document per project in some UI contexts, but the raw list response already includes the full `advertisement_documents` array -- detail adds no additional documents, but does add the full-text HTML body). 417 with a Frappe `ValidationError` envelope on an unknown/closed `project_id`. |

## Known limits

- **No historical/awarded-contracts archive on this platform.** This is a
  young (Feb 2026), purpose-built "currently open opportunities" board --
  it does not expose closed/awarded/cancelled notices via any endpoint
  found during recon (no query param changes the result, no other
  `doctracker.api.powerbi.*` method guessed -- `get_public_awarded_contracts`,
  `get_public_contract_awards`, `get_public_awards`, `get_public_results`,
  `get_public_procurement_plan`, `get_public_bid_results`, and
  `get_public_no_objection` all 417 as unrecognized methods -- reported
  honestly rather than fabricated). The legacy `npta.gov.gy` site does
  publish a "Tenders Awarded" page, but that host is out of scope (Claude
  named in its robots.txt, see above).
- **List size is small and genuinely volatile** -- it reflects only
  currently-open opportunities, so record count naturally shrinks to zero
  between advertisement waves and grows again as NPTAB posts new notices.
  `maxItems` is a safety cap, not a meaningful pagination control.
- **Document URLs are relative** (`/files/<name>.pdf`) and can contain
  literal (unencoded) spaces -- this actor joins them with `BASE_URL` and
  percent-encodes via `urllib.parse.quote` before exposing `document_url`,
  since a raw relative path with an embedded space is not directly usable
  by a downstream HTTP client.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://eprocure.gov.gy"
LIST_ENDPOINT = f"{BASE_URL}/api/method/doctracker.api.powerbi.get_public_bid_opportunities"
DETAIL_ENDPOINT = f"{BASE_URL}/api/method/doctracker.api.powerbi.get_public_project_advertisement"

DEFAULT_HEADERS = {
    "Accept": "application/json",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE_SECS = 5.0
