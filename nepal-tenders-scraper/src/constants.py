"""Endpoints, headers, enum mappings, and recon summary -- all in one place.

Recon summary (2026-08-27): Nepal's national e-Government Procurement (e-GP)
system is operated by the Public Procurement Monitoring Office (PPMO) at
**bolpatra.gov.np** (context path `/egp`) -- verified live and current via
web search cross-referenced against `ppmo.gov.np` (PPMO's own info site,
which explicitly documents `www.bolpatra.gov.np` as "the e-GP system"). A
separate historical open-data initiative (PPTIN, `ppip.gov.np`) published
OCDS bulk exports but stopped updating in 2018 and its domain no longer
resolves -- **not used by this actor**; all data here comes live from
bolpatra.gov.np itself.

`bolpatra.gov.np` is an older JBoss/Struts2 server (no dedicated
`robots.txt` file at all -- every path 404s to a generic JBoss error page,
which is the SAME behavior confirmed for `ghana-tenders-scraper`'s GHANEPS,
also European-Dynamics-adjacent Struts tooling). No Disallow, no AI-bot
mention. `ppmo.gov.np` (not used for data, only cross-referenced during
recon) has a plain `User-agent: * / Crawl-delay: 10`.

**No login wall for viewing.** The public "Search Opportunities" page
(`/egp/searchOpportunity`) and its two AJAX result endpoints, plus the
per-tender detail popup, are all reachable with zero cookies/auth from a
cold client. Login is required only to submit a bid or register as a
vendor -- never to browse or read tender notices, confirming the
transparency-law hypothesis from this vertical's first actor
(`ghana-tenders-scraper`).

**Two listing endpoints, both POST, both server-rendered HTML fragments:**

- `searchBidDashboardHomePage` -- the homepage's "recent opportunities"
  widget. Ignores all filters, always returns the 30 most-recently
  published tenders, sorted freshest-first. Works fully cold (no session
  needed). Used for this actor's `latest` listing (no filters given).
- `SearchOpportunitiesResultHomePage` -- the real filtered search, taking
  `bidSearchTO.title` (keyword), `bidSearchTO.procurementCategory`,
  `bidSearchTO.procurementMethod`, `bidSearchTO.publicEntity` (a numeric
  ID, NOT the free-text name -- see `getSimilarPENames` below),
  `bidSearchTO.contractType`, and two `dd-mm-yyyy` date-text fields. Used
  whenever any filter is supplied.

**Quirk confirmed during recon: page size is inconsistent, non-deterministic,
and NOT controllable via `pageSizeInput`.** Repeated identical requests to
both `SearchOpportunitiesResultHomePage` and `searchBidDashboardHomePage`
(same filters, same fresh-session priming, minutes apart) were observed
returning 10 rows on some calls and 30 on others with no request-side
variable that reliably predicted which -- `pageSizeInput` itself made no
observed difference in any combination tried. This is most likely
server-side (a load-balanced cluster with inconsistent node config/cache,
not uncommon on older government infrastructure) rather than anything
this client controls. This actor does NOT pretend a stable row count
exists -- it parses however many rows a given response actually contains
and reports that as `_totalReturned` on every record, so downstream
consumers can see the real count per run rather than assume one.

**No reliable stateless pagination beyond page 1.** Resending
`currentPageIndexInput`/`pageActionInput=next` with a full round-trip of
every hidden field (tried extensively, including exact JS-observed field
names from `pager.js`) reliably resets to page 1 every time in a scripted
client -- the real "Next" button's client-side state likely depends on
in-page JS execution this actor does not reproduce. This actor therefore
returns one page (10-30 rows, whatever the site gives back for the
supplied filters) per run rather than claiming exhaustive pagination it
cannot actually deliver -- narrow your filters (keyword / category /
method / entity / dates) for a more targeted result set, same guidance as
other per-query-capped actors in this collection.

**Public entity name resolution**: `getSimilarPENames?term=<text>` is a
clean public JSON autocomplete endpoint (no auth) returning
`[{"id": "...", "name": "..."}, ...]`. Filtering by
`bidSearchTO.publicEntityTitle` (the free-text name) alone with no ID set
matches ZERO records (confirmed) -- the actual filter field is
`bidSearchTO.publicEntity`, a numeric ID. This actor resolves a
user-supplied entity name to its ID via this endpoint (first match) before
searching.

**Tender detail** (`getTenderDetails?tenderId=<id>`, GET, no auth) returns
a small HTML fragment of label/value table cells across several sections
(basic info, bid information, funding, bid schedule, fee, contact) plus up
to four document-download tables (Bid Document / Addendum / Bid Query
Response / LOI). An unknown/invalid `tenderId` returns HTTP 200 with the
exact same template but every value blank (confirmed on a deliberately
out-of-range id) -- this actor treats a blank "Public Entity Name" field as
the not-found signal, the same shape of gotcha as several other actors in
this collection (HTTP 200 "empty template" instead of 404).
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://bolpatra.gov.np/egp"
SEARCH_PAGE_URL = f"{BASE_URL}/searchOpportunity"
DASHBOARD_URL = f"{BASE_URL}/searchBidDashboardHomePage"
SEARCH_RESULT_URL = f"{BASE_URL}/SearchOpportunitiesResultHomePage"
ENTITY_AUTOCOMPLETE_URL = f"{BASE_URL}/getSimilarPENames"
DETAIL_URL = f"{BASE_URL}/getTenderDetails"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": SEARCH_PAGE_URL,
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
REQUEST_TIMEOUT = 45

# bidSearchTO.procurementCategory option values, from the search form's own <select>.
PROCUREMENT_CATEGORY_MAP = {
    "all": "-1",
    "goods": "1",
    "works": "2",
    "consultancy": "3",
    "otherServices": "4",
}

# bidSearchTO.procurementMethod option values, from the search form's own <select>.
PROCUREMENT_METHOD_MAP = {
    "all": "-1",
    "ncb": "1",
    "icb": "2",
    "sealedQuotation": "3",
    "directPurchase": "4",
    "qcbs": "5",
    "qbs": "6",
    "fbs": "9",
    "commodityPurchase": "11",
    "ration": "12",
    "userCommittee": "13",
    "forceAccount": "14",
    "leastCostSelection": "15",
}
