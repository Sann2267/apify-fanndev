# Crawling Method — Guyana Government Tenders Scraper (NPTAB eProcure)

**Last verified:** 2026-08-27

## What eprocure.gov.gy is

Guyana's official public-procurement notice board is **eprocure.gov.gy**,
launched **February 2026** by the National Procurement and Tender
Administration Board (NPTAB, under the Ministry of Finance) as a
"centralized Procurement Opportunities Website to enhance transparency and
access" — confirmed via the Department of Public Information press release
and Stabroek News, both dated 2026-02-25. It centralizes what used to be
piecemeal PDF postings scattered across individual ministry sites into one
official host.

## Two Guyana procurement domains were found — only one is used here

| Domain | Role | Used? |
|---|---|---|
| `www.npta.gov.gy` | Legacy NPTA WordPress site (has a "Tenders Awarded" archive page) | **No.** Its `robots.txt` carries a Cloudflare Managed-Content block group that explicitly names `ClaudeBot` (`Disallow: /`), alongside `GPTBot`, `CCBot`, `Google-Extended`, `Bytespider`, `Amazonbot`, `Applebot-Extended`, `meta-externalagent`, `CloudflareBrowserRenderingCrawler`. Per this portfolio's policy, any Claude-named disallow is a hard stop for that host — avoided entirely, even though it's a *different* host from the one actually launched as the current official portal. |
| `eprocure.gov.gy` | The new (Feb 2026) centralized NPTAB portal — the task's actual target | **Yes.** `robots.txt` returns `200 OK` with an **empty body** (`Content-Length: 0`) — no restrictions of any kind, nothing to block. |

## No login wall — confirmed on both API methods used

The site auto-sets an anonymous `sid=Guest` / `system_user=no` /
`full_name=Guest` / `user_id=Guest` cookie set on *every* request, logged in
or not (standard Frappe framework session behavior — see below). Both
public API methods this actor calls return full data to a plain,
cookie-less request with zero authentication. No login prompt, paywall, or
CAPTCHA was ever encountered on any read path.

## Backend: Frappe framework, custom app "doctracker"

Response headers (`X-Page-Name`) and the session-cookie set
(`sid`/`system_user`/`full_name`/`user_id`) are textbook **Frappe**
(the open-source framework underlying ERPNext) conventions, confirmed
further by the URL shape `/api/method/<app>.<module>.<method>`. The custom
app here is named **`doctracker`**; the two public methods used live in its
`powerbi` submodule — likely originally built to feed an internal Power BI
dashboard and then whitelisted for this public-facing page too.

## TLS profile: genuinely no WAF — every profile tested returns 200

```
curl (no TLS impersonation at all) -> 200
chrome124   -> 200
chrome131   -> 200
safari17_0  -> 200
edge101     -> 200
```

No Cloudflare/Akamai/DataDome/PerimeterX response headers anywhere. This is
about as clean as this portfolio's targets get — `curl_cffi` with
`chrome124` is used purely for consistency with the rest of the portfolio's
default stack, not because anything required it.

## Two public JSON API methods — no HTML scraping needed at all

Both were found by reading the homepage's inline `<script>` directly
(`fetch(...)` calls), not by reverse-engineering a bundled JS SPA framework
— the page itself is plain server-delivered HTML/CSS/vanilla-JS, no
React/Angular/Vue build step to unpack.

### `doctracker.api.powerbi.get_public_bid_opportunities` (list mode)

```
GET https://eprocure.gov.gy/api/method/doctracker.api.powerbi.get_public_bid_opportunities
Accept: application/json
```

Returns `{"message": [ {...}, {...} ]}` — the **complete current list** of
publicly advertised bid opportunities. Confirmed **no pagination exists**:
adding `?status=Awarded` (a guess at a filter param) returned a
byte-identical response to no params at all, and the frontend itself calls
this with no query string. It's a "what's open right now" bulletin board —
4 records at recon time (2026-08-27), all `current_state: "Bid Advertised"`.

Fields observed on every record: `project_id`, `project_name`, `agency`,
`agency_logo` (always null at recon), `procurement_method`,
`procurement_nature`, `procurement_sub_nature`, `estimated_value` (always
`0.0` at recon — not populated for these notices), `current_state`,
`advertisement_date`, `actual_bid_opening_date`,
`projected_bid_opening_date`, `regions` (array), `advertisement_documents`
(array of `{document_name, document_file}`).

### `doctracker.api.powerbi.get_public_project_advertisement` (detail mode)

```
GET https://eprocure.gov.gy/api/method/doctracker.api.powerbi.get_public_project_advertisement?project_id=PROC-2026-00425
Accept: application/json
```

Returns `{"message": {...}}` — the full rich-text advertisement for one
project: `project_id`, `project_name`, `agency`, `procurement_method`,
`actual_bid_opening_date`, `projected_bid_opening_date`, `ad_header`,
`ad_scope`, `ad_instruction`, `ad_footer` (each an HTML fragment — notice
title block, project background, bidding instructions/qualification
criteria, and contact-address footer respectively), and
`advertisement_documents`.

**Not a strict superset of the list record** — detail drops
`procurement_nature`/`estimated_value`/`current_state`/`regions` but adds
the four rich-text HTML fields. Documented explicitly in the output schema
and README rather than assumed.

On an unknown or unpublished `project_id`, this method returns **HTTP 417**
with a Frappe `ValidationError` envelope:

```json
{"exc_type": "ValidationError", "_server_messages": "[\"{...\\\"message\\\":\\\"Project not found or not published\\\"...}\"]"}
```

`extractor.unwrap_frappe_response` detects this (`exc_type`/`exc` present
instead of `message`) and raises `FrappeApiError`; `main.py` treats it as a
terminal `not_found`, not a transient failure worth retrying.

## Documents: relative paths, need percent-encoding

`document_file` values are relative (`/files/<name>.pdf`) and can contain
**literal, unencoded spaces** — confirmed live
(`/files/SPN- P501759-CW-1.pdf`). A raw relative path with an embedded
space is not directly usable by a downstream HTTP client, so
`extractor._resolve_documents` joins each with `BASE_URL` and
percent-encodes via `urllib.parse.quote(path, safe="/")`, exposing the
result as a new `document_url` field alongside the untouched original
`document_name`/`document_file` (raw passthrough preserved, not replaced).
Confirmed downloadable with no auth after encoding
(`SPN-%20P501759-CW-1.pdf` → `200 application/pdf`).

## Known limits

- **No historical/awarded-contracts archive on this platform.** This is a
  young (Feb 2026), purpose-built "currently open opportunities" board — it
  surfaces only what's presently advertised. Guessed alternate method names
  (`get_public_awarded_contracts`, `get_public_contract_awards`,
  `get_public_awards`, `get_public_results`, `get_public_procurement_plan`,
  `get_public_bid_results`, `get_public_no_objection`) all returned HTTP
  417 "method not whitelisted" — reported honestly rather than fabricated.
  The legacy `npta.gov.gy` site does publish a "Tenders Awarded" page, but
  that host is out of scope for this actor (see the robots.txt finding
  above).
- **List size is small and genuinely volatile by design** — it reflects
  only currently-open opportunities, so record count naturally shrinks to
  zero between NPTAB advertisement waves and grows again as new notices are
  posted. `maxItems` in the input schema is a safety cap, not a meaningful
  pagination control — there is nothing to paginate.
- **`estimated_value` and `agency_logo` were `0.0`/`null` on every record
  seen during recon** — passed through verbatim rather than dropped, since
  a future notice might populate them; not a parsing gap.

## Diff cadence

Monthly smoke test recommended, given how young and actively-developed this
platform is (launched only ~6 months before this actor was built). Watch
in particular for: the `doctracker.api.powerbi.*` method names changing (a
Frappe app upgrade could rename/relocate them), and for NPTAB eventually
adding a historical/awarded-notices method now that the platform has had
time to accumulate closed records.
