"""Endpoints, per-notice-type config, and recon summary -- all in one place.

Recon summary (2026-08-27): Trinidad and Tobago's official public-procurement
notice board is **ProcureTT** (`procurett.oprtt.org`), run by the Office of
Procurement Regulation (OPR, `oprtt.org`) under the Public Procurement and
Disposal of Public Property Act, 2015. It is a WordPress site using the
**GravityView** plugin (Gravity Forms submissions rendered as searchable/
sortable public tables) -- NOT the "European Dynamics/ePPS" e-GP platform
seen in Ghana/Zambia/Jamaica; a different vendor family for this vertical.

## No login wall anywhere -- confirmed on every notice type, including detail

Unlike GOJEP (Jamaica) or ZPPA (Zambia), where a single-tender "full detail"
page is login-gated, **every ProcureTT page returned full content to a
plain, cookie-less request** -- both the five listing pages and their
per-entry detail pages (`{path}entry/<id>/`) for the three notice types that
have one. A "Log In" link exists in the site header (WordPress/Ultimate
Member account system) but is for public bodies submitting new notices, not
for browsing -- never encountered on any read path during recon.

## robots.txt: clean, no blanket block, no Claude/anthropic mention

```
User-agent: *
Disallow: /wp-content/uploads/wpo/wpo-plugins-tables-list.json

# START YOAST BLOCK
User-agent: *
Disallow:
Sitemap: https://procurett.oprtt.org/sitemap_index.xml
# END YOAST BLOCK
```
Default WordPress/Yoast robots.txt -- one disallowed static JSON asset, then
an explicit blanket *allow* from the Yoast block. No `Claude`/`ClaudeBot`/
`Claude-Web`/`Claude-User`/`Claude-SearchBot`/`anthropic-ai` mention anywhere.
(`oprtt.org`, the parent OPR site, is also clean but not used by this actor
-- it's policy/contact pages, not the notice board.)

## TLS profile: chrome124/safari17_0/edge101 all fine; chrome131 gets a 403

`curl_cffi impersonate="chrome131"` gets a plain nginx-level 403 (no
Cloudflare/Akamai/etc challenge headers -- looks like a blocklisted-fingerprint
rule, not a real WAF/bot-check) while chrome124, safari17_0, and edge101 all
return normal 200s with full content. This matches the portfolio-wide "chrome131
is widely blocklisted in 2026" note -- `chrome124` is used here as the default.

## Five notice types, all public, all GravityView table views

| Notice type | Path | View ID | Rows at recon | Per-entry detail page? |
|---|---|---|---|---|
| Tenders | `/tenders/` | 330 | ~400 | Yes -- richer fields (Notice Type, Date of Issuance, Lines of Business Level 4, Submission Deadline Time) |
| Awards | `/awards/` | 871 | ~290 | No -- listing row is the only data; long descriptions can be `...`-truncated with no way to recover the full text |
| ASPPA (Annual Schedule of Planned Procurement Activities) | `/annual-schedule-of-planned-procurement-activities/` | 363 | ~150 | No |
| Pre-qualification notices | `/pre-qualification-notices/` | 268 | ~40, no pagination widget rendered (view shows all rows on one page) | Yes |
| Disposals | `/disposals/` | 350 | ~10 | Yes -- richer fields (Means of Disposal Method, Property Description) |

## Pagination: plain stateless `?pagenum=N`, no session/table-id discovery needed

Much simpler than the ePPS platforms (Ghana/Zambia/Jamaica), which need a
per-run `d-<digits>` table-instance id extracted from page 1 first. Here,
`GET {path}?pagenum=2` just works standalone -- confirmed combinable with
`sort[...]` on the same request, and confirmed each page fetch is fully
independent (no cookie needed), so concurrent multi-page fetching is safe.

Page size is inferred at runtime from the "Displaying `X - Y` of `Z`" banner
(`Y - X + 1`) rather than hardcoded -- it differs per view (50 for
tenders/ASPPA, 25 for awards, 10 for disposals) and the banner is absent
entirely when a view has no pagination widget (pre-qualification notices --
in that case all returned rows ARE the total, no further pages exist).

## Sorting: `?sort[<fieldId>]=asc|desc` -- direct, not a toggle

Confirmed empirically (unlike GOJEP's reversed `o=1`/`o=2`): `sort[10]=asc`
returns oldest-first, `sort[10]=desc` returns newest-first, both readable
straight off the rendered dates. Field ids are per-view internal Gravity
Forms field ids (see `SORT_FIELDS` below), scraped from each view's own
column-header sort links during recon -- not guaranteed stable forever, but
have no self-discovery mechanism on this platform (no equivalent of GOJEP's
`d-<id>` embedded in the page), so they're pinned here and would need a
recon refresh if OPR redesigns a view.

## Row parsing: by `data-label` attribute, not fixed column index

Every `<td>` in every listing table carries a `data-label="<Column Name>"`
attribute (used by GravityView's own responsive/mobile CSS) -- `extractor.py`
builds each row as `{data-label text: cell value}` rather than assuming a
fixed column order, which is more resilient to a future column reorder than
position-based parsing. It still validates that a minimum expected label set
is present on the first row of every notice type, raising `UnexpectedShape`
if a column is missing entirely (real layout change) rather than silently
emitting a partial record.

## Known limits

- **Awards descriptions can be truncated with `...` and no detail page to
  recover the full text** -- confirmed on live data (2 of ~290 award rows at
  recon time). This is a genuine upstream limitation of the `/awards/` view,
  not a parsing gap.
- **No full-text/keyword search exposed without extra params this actor
  doesn't reverse-engineer** -- GravityView's own `?gv_search=` box was not
  probed for a stable public query contract; `sortBy`/`sortOrder` plus
  client-side post-filtering of fetched rows is the supported approach here.
- **Currency is stated in the column header, not per-row** -- Award Value is
  labelled "(TTD)" in the column header itself (Trinidad and Tobago Dollars),
  not repeated per value.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://procurett.oprtt.org"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE_SECS = 5.0

# Safety cap on page depth per job.
MAX_PAGES_PER_JOB = 200

# Per-notice-type config: URL path, GravityView view id (informational --
# not needed to build requests, just documented for traceability), whether a
# richer per-entry detail page exists, the minimum column labels expected on
# a listing row (shape-change guard), and the sort-field-id map exposed to
# actor input (scraped from each view's own header sort links).
NOTICE_TYPES = {
    "tenders": {
        "path": "/tenders/",
        "view_id": 330,
        "title": "Tender Notices",
        "has_detail": True,
        "expected_labels": {
            "Public Body",
            "Tender Reference No.",
            "Status",
            "Submission Deadline Date",
            "Description",
        },
        "sort_fields": {
            "publicBody": 4,
            "referenceNumber": 2,
            "status": 20,
            "submissionDeadlineDate": 10,
            "description": 5,
            "linesOfBusiness": 22,
        },
    },
    "awards": {
        "path": "/awards/",
        "view_id": 871,
        "title": "Award Notices",
        "has_detail": False,
        "expected_labels": {
            "Public Body",
            "Reference No.",
            "Description",
            "Supplier or Contractor Awarded",
            "Award Value (TTD)",
            "Award Date",
        },
        "sort_fields": {
            "publicBody": 9,
            "referenceNumber": 8,
            "description": 10,
            "supplier": 7,
            "awardValue": 3,
        },
    },
    "asppa": {
        "path": "/annual-schedule-of-planned-procurement-activities/",
        "view_id": 363,
        "title": "Annual Schedule of Planned Procurement Activities",
        "has_detail": False,
        "expected_labels": {
            "Public Body",
            "Fiscal Year",
            "Posted Date",
            "ASPPA Document",
        },
        "sort_fields": {
            "publicBody": 7,
            "fiscalYear": 10,
            "postedDate": 3,
        },
    },
    "prequalification": {
        "path": "/pre-qualification-notices/",
        "view_id": 268,
        "title": "Pre-Qualification Notices",
        "has_detail": True,
        "expected_labels": {
            "Public Body",
            "Posted Date",
            "Deadline Date",
        },
        "sort_fields": {
            "publicBody": 7,
            "postedDate": 3,
            "linesOfBusiness": 9,
            "deadlineDate": 4,
        },
    },
    "disposals": {
        "path": "/disposals/",
        "view_id": 350,
        "title": "Disposal Notices",
        "has_detail": True,
        "expected_labels": {
            "Public Body",
            "Disposal Reference No.",
            "Posted Date",
            "Closing Deadline Date",
        },
        "sort_fields": {
            "publicBody": 16,
            "referenceNumber": 17,
            "postedDate": 4,
            "closingDeadlineDate": 5,
            "categories": 19,
        },
    },
}
