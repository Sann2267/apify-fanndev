"""Shared constants for the GHANEPS (Ghana Electronic Procurement System) scraper.

See CRAWLING_METHOD.md for how these URLs / TLS profile were discovered and
verified. The site is a server-rendered Struts/JSP-era Java webapp (vendor:
"European Dynamics", the same company behind several EU-model e-procurement
platforms) -- no JSON API, no WAF/CDN fingerprint observed.
"""

BASE = "https://www.ghaneps.gov.gh/epps"

# Each entry is a public listing view reachable with a plain GET, no login.
# "path": the .do action URL (no query string).
# "query": a fixed query string this view always needs (e.g. selecting the
#   "Tenders" quick-search category) -- empty string if none.
# "table_uid": the value of the page's `<input type="hidden" name="tableUid">`
#   marker -- used to sanity-check we parsed the view we think we did.
LIST_CONFIGS = {
    "current": {
        "path": f"{BASE}/quickSearchAction.do",
        "query": "searchSelect=6",
        "table_uid": "searchCft",
        "title": "Current Tenders (open for bidding)",
    },
    "opened": {
        "path": f"{BASE}/common/viewOpenedTenders.do",
        "query": "",
        "table_uid": "searchOTD",
        "title": "Opened Bids (submission closed, in evaluation/awarding)",
    },
    "awarded": {
        "path": f"{BASE}/viewAllAwardedContracts.do",
        "query": "",
        "table_uid": "contract",
        "title": "Awarded Contracts",
    },
}

VALID_LIST_TYPES = tuple(LIST_CONFIGS.keys())

DETAIL_PATH = f"{BASE}/cft/prepareViewCfTWS.do"

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

RESULTS_PER_PAGE = 10  # server-fixed; no page-size query param was found to change this
