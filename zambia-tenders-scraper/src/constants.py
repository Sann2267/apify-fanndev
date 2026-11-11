"""Endpoints, headers, profile choices -- all in one place.

Target: Zambia Public Procurement Authority (ZPPA) e-Government Procurement
(e-GP) portal, built on the "European Dynamics" e-GP platform (same vendor
family used by many countries' government procurement systems -- confirmed
via the `<meta name="Creator" content="European Dynamics"/>` tag present on
every page). See CRAWLING_METHOD.md for the full recon writeup.
"""

BASE_URL = "https://eprocure.zppa.org.zm/epps"
HOME_URL = f"{BASE_URL}/home.do"
OPENED_TENDERS_URL = f"{BASE_URL}/common/viewOpenedTenders.do"
DETAIL_URL = f"{BASE_URL}/cft/prepareViewCfTWS.do"

TLS_PROFILE = "chrome124"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.5

# The "Opened Bid Details" grid always renders exactly 10 rows per page --
# the results-per-page dropdown values advertised in the page's own JS
# (["10","20","50","100"]) are a client-side option list only; passing
# `d-<gridId>-n=100` on the GET request was tested live and made no
# difference to the row count returned. Pagination therefore always walks
# in steps of 10 (`d-<gridId>-p=<pageNum>`).
PAGE_SIZE = 10

# Safety cap on pages walked in "list" mode regardless of maxItems, so a
# parsing regression (e.g. grid id extraction silently failing) can't spin
# the actor into thousands of requests against a government server.
MAX_PAGES_HARD_CAP = 500
