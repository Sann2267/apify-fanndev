"""Shared constants for Vanuatu's Central Tender Board (CTB) e-tendering
site, `ctb.gov.vu`.

See CRAWLING_METHOD.md for the full recon writeup. Short version: CTB (an
Act of Parliament parastatal under the Ministry of Finance and Economic
Management) publishes tenders through Joomla's built-in "Smart Search"
(`com_finder`) component -- a server-rendered card list, not a custom table,
with standard Joomla `?start=N` offset pagination (20 cards/page):

1. **current** -- `/en/tenders/actual-tenders`: currently open tenders,
   ~41-60 at recon time (3 pages).
2. **results** -- `/en/tenders/tenders-results`: the historical archive of
   the same card shape, ~140 at recon time (7 pages, last page
   `?start=120`).

Both list types share one card schema: reference number, title, purchaser
(procuring ministry/agency), category, submission date, expiry date, and a
full free-text description -- already richer inline than most other
countries' tender listings in this portfolio, so no per-item detail-page
fetch is needed for the core fields (a detail page does exist per tender,
e.g. `/en/tenders-category/<slug>`, with a few extra fields -- Date Issued,
Completion Date, Opening date/time, Contact Person/Email -- but is not
fetched by this actor to keep it to one request per page of results;
`detailUrl` is included so a user can open it themselves).

No JS rendering needed, no API. `https://ctb.gov.vu/robots.txt` is a stock
Joomla robots.txt (`Disallow` limited to internal system paths) with no
Claude/AI-crawler-specific group. Note: `ctb.gov.vu`'s TLS certificate chain
is incomplete (`unable to get local issuer certificate` under strict
verification) -- a server misconfiguration, not a WAF signal; this actor
disables certificate verification for this host only, same pattern already
used elsewhere in this portfolio for small-government-site cert issues
(e.g. `tendersboard.gov.ag` in the Saint Vincent recon pass).
"""

BASE = "https://ctb.gov.vu"

CURRENT_TENDERS_URL = f"{BASE}/en/tenders/actual-tenders"
RESULTS_URL = f"{BASE}/en/tenders/tenders-results"

VALID_LIST_TYPES = ("current", "results")

PAGE_SIZE = 20  # Joomla com_finder's fixed page size, observed at recon time

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0
