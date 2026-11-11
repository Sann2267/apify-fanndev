"""Shared constants for Nigeria's NOCOPO (Nigeria Open Contracting Portal)
tenders scraper.

See CRAWLING_METHOD.md for how these endpoints were discovered and verified.
NOCOPO (`nocopo.bpp.gov.ng`) is run by the Bureau of Public Procurement (BPP)
under Section 5(r) of the Public Procurement Act, 2007, and is modelled on
the Open Contracting Data Standard (OCDS) -- no login, no API key for any of
the endpoints this actor uses.
"""

BASE = "https://nocopo.bpp.gov.ng"

# Legacy (pre-1.10) jQuery DataTables server-side listing endpoint behind
# NOCOPO's own "Open Data" page table.
LIST_ENDPOINT = f"{BASE}/PublishedRecordHandler.ashx"

# Returns a small zip containing one OCDS release package for a single ocid
# (the same endpoint NOCOPO's own "Download" button in that table calls).
DETAIL_ENDPOINT = f"{BASE}/ocdsjson.ashx"

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0  # seconds, exponential backoff

# Rows per PublishedRecordHandler.ashx request. The handler ignores the
# requested column list and always returns the full ~250-column legacy
# internal row regardless -- larger pages get noticeably slower purely from
# payload size (100 rows measured at ~17s / ~1MB during recon). 25 is a
# reasonable balance; MAX_LIST_PAGES_SAFETY_CAP still bounds worst case.
LIST_PAGE_SIZE = 25
LIST_PAGE_DELAY = 1.0  # pause between sequential list-page requests
MAX_LIST_PAGES_SAFETY_CAP = 200
