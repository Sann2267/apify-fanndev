"""Shared constants for the Central Procurement Board of Namibia (CPBN) scraper.

See CRAWLING_METHOD.md for how the real data source was found and verified.
`www.cpbn.com.na` is CPBN's own corporate site (custom PHP/CodeIgniter-style
MVC app, `index/<controller>/<method>` routing, LiteSpeed server) -- it is a
DIFFERENT, more actively-maintained system than the Liferay-based
`eprocurement.gov.na` portal that the CPBN Act also references (that portal
turned out to be a mostly-static policy/legislation document repository with
no live tender listing at all; see CRAWLING_METHOD.md for how that was ruled
out). Every "Bids" listing view below is server-rendered HTML with every row
embedded in a single response -- the page's own DataTables plugin only
paginates client-side (JS), so no pagination logic is needed on our side.
"""

BASE = "https://www.cpbn.com.na"

# Each entry is a public "Bids" listing view (site's own "Bids" nav dropdown),
# reachable with a plain GET, no login. All rows for that category are
# embedded in the single HTML response.
LIST_CONFIGS = {
    "open": {
        "path": f"{BASE}/index/external/2",
        "title": "Bids: Open",
    },
    "underEvaluation": {
        "path": f"{BASE}/index/external/3",
        "title": "Bids: Closed & under evaluation",
    },
    "cancelled": {
        "path": f"{BASE}/index/external/5",
        "title": "Bids: Cancelled",
    },
    "awarded": {
        "path": f"{BASE}/index/external/6",
        "title": "Bids: Notice for Selection of Awards",
    },
    "clarifications": {
        "path": f"{BASE}/index/external/7",
        "title": "Bids: Clarifications",
    },
    "openingRegister": {
        "path": f"{BASE}/index/external/9",
        "title": "Bids: Opening register",
    },
    "notices": {
        "path": f"{BASE}/index/external/99",
        "title": "Bids: Notices",
    },
    "all": {
        "path": f"{BASE}/index/external/98",
        "title": "Bids: All bids",
    },
}

VALID_LIST_TYPES = tuple(LIST_CONFIGS.keys())

DETAIL_PATH = f"{BASE}/index/bid"

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0
