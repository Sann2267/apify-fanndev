"""Shared constants for the Tanzania NeST (National e-Procurement System) tenders scraper.

See CRAWLING_METHOD.md for how this API was discovered and verified. NeST
(`nest.go.tz`, run by the Public Procurement Regulatory Authority / PPRA) ships
a genuinely public, OCDS-compliant (Open Contracting Data Standard) JSON API
behind its "NeST Data Portal" (`data.nest.go.tz`) -- no login, no API key.
"""

BASE = "https://nest.go.tz/gateway/nest-data-portal-api/api"

RECORDS_PATH = f"{BASE}/records"
RECORD_DETAIL_PATH = f"{BASE}/records/{{ocid}}"

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 3.0  # seconds -- this host rate-limits fairly aggressively, see CRAWLING_METHOD.md

# The API's own page size is fixed server-side at 5 records per call; no
# query parameter was found that changes it (limit/pageSize/size all trigger
# a 500). The "cursor" query parameter is accepted but NOT actually honoured
# by the server -- every value returns the same first 5 records for a given
# "since" value. Real pagination is done by advancing "since" past the
# latest date seen in each batch (see client.py / CRAWLING_METHOD.md).
RESULTS_PER_PAGE = 5

# Minimum pause between sequential list-page requests, on top of retry
# backoff, to stay under this host's rate limiter.
LIST_PAGE_DELAY = 2.5

MAX_LIST_PAGES_SAFETY_CAP = 400  # hard stop even if maxResults implies more pages
