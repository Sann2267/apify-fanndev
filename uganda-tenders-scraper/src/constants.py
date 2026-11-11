"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): Uganda's public procurement transparency portal
is the PPDA (Public Procurement and Disposal of Public Assets Authority)
e-Government Procurement system, branded "EGP Uganda", at
`https://egpuganda.go.ug`. This is a **different** system from
`www.ppda.go.ug` (PPDA's own WordPress marketing/policy site -- law text,
guidelines, press releases, no notice data) and from `gpp.ppda.go.ug` (an
older "Government Procurement Portal" that no longer resolves -- connection
timeout on every attempt during recon, likely decommissioned in favour of
the new e-GP Phase II rollout referenced in PPDA's own April 2026 press
statement announcing e-GP going live for ALL procuring entities from
1 July 2026).

## robots.txt

```
User-agent: *
Disallow:
```

Blanket-allow, no Claude/AI-crawler mention, no Crawl-delay. Nothing on this
site is disallowed for any crawler.

## No WAF / no TLS-fingerprint gate at all

Unlike `uganda-ursb-scraper`'s `obrs-api.ursb.go.ug` (TLS-fingerprint-gated,
plain `curl` gets 403, `curl_cffi` clears it), **every endpoint used by this
actor returns HTTP 200 with real content on a plain default-TLS `curl`
request, no impersonation needed at all.** The server is plain Apache
running a Laravel app (cookies named `XSRF-TOKEN` / `egp_uganda_session`,
standard Laravel CSRF pattern) -- no Cloudflare/Akamai/DataDome markers in
any response header. `curl_cffi` with `chrome124` is still used here (for
portfolio consistency and because a residential proxy in front of it will
still terminate TLS with some fingerprint), but it is not load-bearing for
this specific target.

## No login wall for viewing

Browsing every notice-listing and notice-detail page used by this actor
requires **no account and no login**. Uganda's Public Procurement Act
requires open publication of procurement notices, and the portal explicitly
states members of the public can view notices without registering. A
"Supplier Login" / "Register as Supplier" flow exists, but it gates only
*participating* (submitting a bid/quotation) -- confirmed by the notice
detail page's own "Click here To Apply" button linking to `/login`, while
the notice's full title, reference number, procuring entity, and
description body are rendered in the page's plain HTML with no auth check.

## Site structure

The homepage (`/`) shows a small (~4-per-category) live preview of current
Bid Notices / Disposal Notices / Announcements, each linking to a universal
notice-detail page:

    GET /index/<notice_id>_egp

This detail page works for **any** notice ID regardless of whether it is
still open for bidding or long closed (confirmed both on a live 2026-2027
notice and on a 2024 archived one) -- it renders the notice type heading
(e.g. "Request for Quotation Notice"), the procurement reference number,
the full (untruncated) subject of procurement, and a boilerplate-wrapped
description body. It does **not** carry the published/deadline dates --
those come from whichever listing surfaced the notice ID in the first
place.

`/bid-notices` is the full listing page and actually contains **six**
tab-panes (easy to miss -- three "current" + three "archived", all sharing
similarly-named CSS ids):

| Tab id | Content | Rendering |
|---|---|---|
| `procurement` | **Currently open Bid Notices** (small, real list -- as of recon, single digits: Uganda's FY2026-2027 had just started) | Fully server-rendered `<table>`, no AJAX |
| `disposal` | Currently open Disposal (asset-sale) Notices | Fully server-rendered `<table>`, no AJAX |
| `opening` | Currently pending Bid Opening records | Fully server-rendered `<table>`, no AJAX |
| `bid_archives` | **Archived (closed) Bid Notices** -- 500+ records | Empty `<tbody>` in HTML; populated by a `POST` AJAX call (below) |
| `disposal_archives` | Archived Disposal Notices | Same AJAX pattern |
| `opening_archives` | Archived Bid Opening records (full solicitation row incl. `estimated_amount`, dates, etc.) | Same AJAX pattern |

This actor's "latest" mode scrapes the `procurement` tab's live HTML table
directly. Its "archived" mode drives the `bid_archives` AJAX endpoint:

    POST /public-bids/api-archived-notices/ajax
    Content-Type: application/x-www-form-urlencoded
    Body: _token=<csrf>&draw=1&start=<offset>&length=<page size>[&is_category=<financial year, e.g. "2025-2026">]

`_token` is a standard Laravel CSRF token -- obtained by GETting any page
first (e.g. `/bid-notices`) and reading the session cookie
(`egp_uganda_session`, auto-managed by keeping requests on one
`curl_cffi.AsyncSession`) plus the `<input name="_token" value="...">`
hidden field in that page's HTML. No login needed to obtain or use it --
it's CSRF protection, not authentication.

## Response shape (archived AJAX)

```json
{"draw":1,"recordsTotal":500,"recordsFiltered":500,"data":[{ ...record... }]}
```

Each record carries a mix of clean upstream fields (passed through as-is:
`procurement_ref`, `procurement_name` [upstream's own field name for the
**procuring entity**, not a typo in this actor], `subject_procurement`,
`bid_security`, `bid_opening_time`, `bid_opening_date`,
`submission_deadline`, `body`, `financial_year`, `procurement_method`,
`procurement_type`, `notice_type`, `created_at`, `updated_at`, `status`,
plus internal ids `id`/`bid_id`/`pde_entity_id`/`requisition_id`) AND six
redundant fields that are pre-rendered HTML fragments for the site's own
DataTables UI (`procuring_entity`, `type`, `procurement_subject`,
`published_date`, `deadline_date`, `action_links`) -- these duplicate data
already present cleanly elsewhere in the same record, just wrapped in
`<div>`/`<span>`/`<a>` markup. See "Gotcha: dropped HTML-rendering fields"
in `CRAWLING_METHOD.md` for why this actor drops those six and replaces
them with one derived `notice_id` (parsed from the embedded `<a href>`).

## `/bid/notice/<notice_id>/opening/details` -- opportunistic enrichment

A second, richer detail page exists for notices that have already had a
recorded bid-opening event: "RECORD OF BID OPENING" -- procurement method,
bid-opening date/time, number of bids received, and (genuinely valuable
transparency data) a table of every bidder's name, address, submission
timestamp, and bid amount. Confirmed this page returns **HTTP 500** (not
404) for a notice ID that hasn't reached that stage yet (e.g. a currently
open notice) -- treated as "no opening record available yet", not an error,
when used as opportunistic enrichment.
"""

BASE_URL = "https://egpuganda.go.ug"
TLS_PROFILE = "chrome124"

BID_NOTICES_PATH = "/bid-notices"
ARCHIVED_BID_NOTICES_AJAX = "/public-bids/api-archived-notices/ajax"
NOTICE_DETAIL_PATH = "/index/{notice_id}_egp"
BID_OPENING_DETAIL_PATH = "/bid/notice/{notice_id}/opening/details"

DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

AJAX_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{BASE_URL}{BID_NOTICES_PATH}",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.0

# Page size sent to the archived-notices AJAX endpoint. DataTables server-
# side processing accepts arbitrary `length` values; kept modest to avoid an
# unnecessarily large single response.
ARCHIVED_PAGE_LIMIT = 50
