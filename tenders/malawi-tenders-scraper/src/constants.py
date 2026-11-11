"""Endpoints, notice-type map, headers, profile choice -- all in one place.

Recon summary (2026-08-27): Malawi's public procurement regulator is the
**Public Procurement and Disposal of Assets Authority (PPDA)**, whose own
corporate website is `ppda.mw`. PPDA also operates a modern e-GP (electronic
Government Procurement) transactional platform, **MANEPS**, at `maneps.mw`
-- a Next.js single-page app. Static strings on `maneps.mw`'s own homepage
link directly to `peragosystems.com/home`, confirming the same vendor,
**Perago Systems**, that also built Sierra Leone's `egp.nppa.gov.sl` (the
first Malawi<->Sierra Leone shared-vendor confirmation in this vertical,
per Babak 25's tender-vertical writeup).

`maneps.mw/procurement-notice` is, like Sierra Leone's equivalent page,
**100% client-rendered** -- its initial HTML response (~53KB) is just
`<head>` boilerplate plus Next.js script tags; the literal word "tender"
never appears server-side. Unlike Sierra Leone's case, there is no evidence
of a backend *outage* here (no 502s observed on the pages actually probed)
-- the page is simply architected to require a JS engine to populate, which
this portfolio's HTTP-only constraint cannot execute.

Fortunately, PPDA's *own* corporate site (`ppda.mw`, a separate
Laravel/Blade + Bootstrap app -- NOT WordPress, unlike Sierra Leone's
fallback) publishes the exact same categories of procurement notice as
plain, fully server-rendered HTML pages, each with a DataTables-enhanced
`<table>` where **every row is already present in the initial response**
(DataTables' JS only adds client-side sort/search/paginate sugar -- the
same "all rows server-rendered, JS pagination is cosmetic" pattern already
seen for Ghana ORC, Sierra Leone NPPA, and others in this portfolio).
Confirmed via a plain `curl` with no session/cookies on the first try, and
across all four `curl_cffi` impersonation profiles below with byte-identical
200 responses -- no WAF, no CDN challenge, no rate limiting observed.

## robots.txt

`ppda.mw/robots.txt`:

    User-agent: *
    Disallow:

An empty `Disallow` directive under a wildcard user-agent = allow
everything. No `Claude`/`ClaudeBot`/`Claude-Web`/`Claude-User`/
`Claude-SearchBot`/`anthropic-ai`/`GPTBot` mention anywhere in the file, no
blanket disallow. (`maneps.mw/robots.txt` is also wide open --
`Allow: /` with only `/api/`, `/_next/`, `/manage/`, `/_app/` disallowed --
moot for this actor since it never touches that host.)

## No login wall for viewing notices

Every notice-board page listed below (`/tenders`, `/award-notices`,
`/intentions-to-award`, `/debarments`, `/admin-review-notices`) returns a
`200` directly with real, current data (`/tenders` freshest row dated
2026-08-26, the day before this actor was built) -- no redirect to a login
page, no session cookie required. PPDA's site does have `/supplier-registration`
and vendor-portal-style flows elsewhere, but those are for *bidding*, not
for *viewing* the public notice boards this actor reads.

## Notice-type table map

Five notice categories share the same page template (Bootstrap +
DataTables), each with its own `<table id="...">`:

| Key | URL path | Table id | Columns (raw header text) |
|---|---|---|---|
| `tenders` | `/tenders` | `tenderstable` | Title, Institution, Reference No., Publish Date, Closing Date, Attachment |
| `awards` | `/award-notices` | `awardstable` | Title, Institution, Reference No., Publish Date, Attachment |
| `intentions` | `/intentions-to-award` | `intentionstable` | Title, Institution, Reference No., Financial Year, Publish Date, Attachment |
| `debarments` | `/debarments` | `debarmentstable` | Title, Publish Date, Attachment |
| `admin_reviews` | `/admin-review-notices` | `adminreviewstable` | (never observed populated -- see below) |

`admin_reviews` was genuinely empty at recon time -- the page renders
"No publications available at the moment" instead of a table. The site's
own shared DataTables-init script (present on every page) still calls
`$('#adminreviewstable').DataTable()`, confirming the table id the page
would use if/when PPDA publishes an administrative review notice; this
actor treats the "No publications available" state as a valid empty
result (0 rows), not an error, and would parse a populated table
generically (same header-driven mapping used for the other four types)
if one ever appears.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. No blocking of any kind was observed on this target -- pinned
for consistency, not because a bypass was needed.
"""

TLS_PROFILE = "chrome124"

BASE_HOST = "https://ppda.mw"

# Header text -> canonical field name. Applied case-insensitively with
# trailing punctuation stripped. Any header not in this map is still kept,
# under a slugified key, so a genuinely new column added upstream shows up
# in the output rather than being silently dropped.
HEADER_FIELD_MAP = {
    "title": "title",
    "institution": "institution",
    "reference no": "referenceNo",
    "financial year": "financialYear",
    "publish date": "publishDate",
    "closing date": "closingDate",
    "date published": "publishDate",
}

# Header labels that only ever contain a download button/icon, never real
# text -- their value is represented via the separately-extracted
# attachmentUrl field instead, not duplicated as text.
ATTACHMENT_HEADERS = {"attachment", "downloads", "file asset"}

NOTICE_TYPES: dict[str, dict] = {
    "tenders": {
        "path": "tenders",
        "table_id": "tenderstable",
        "label": "Open Tenders",
    },
    "awards": {
        "path": "award-notices",
        "table_id": "awardstable",
        "label": "Award Notices",
    },
    "intentions": {
        "path": "intentions-to-award",
        "table_id": "intentionstable",
        "label": "Intentions to Award",
    },
    "debarments": {
        "path": "debarments",
        "table_id": "debarmentstable",
        "label": "Debarred Suppliers",
    },
    "admin_reviews": {
        "path": "admin-review-notices",
        "table_id": "adminreviewstable",
        "label": "Administrative Review Notices",
    },
}

EMPTY_STATE_MARKER = "no publications available"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5
