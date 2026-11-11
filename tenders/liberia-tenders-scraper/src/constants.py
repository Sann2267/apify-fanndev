"""Shared constants for the Liberia e-GP (eprocurement.ppcc.gov.lr) scraper.

See CRAWLING_METHOD.md for how these URLs / TLS profile were discovered and
verified. The site is Liberia's official electronic Government Procurement
(e-GP) platform, run by the Public Procurement and Concessions Commission
(PPCC) -- a server-rendered Struts/JSP-era Java webapp built by "European
Dynamics", the same vendor confirmed behind Ghana's GHANEPS, Zambia's
eprocure.zppa.org.zm, and Jamaica's GOJEP ("ePPS" platform family). No JSON
API, no WAF/CDN fingerprint observed. Liberia's deployment runs a newer
Bootstrap-themed UI than Ghana's, but the same `.do`-action URL scheme and
`<table id="T01">` DisplayTag-style listing shell.
"""

BASE = "https://eprocurement.ppcc.gov.lr/epps"

# Each entry is a public listing view reachable with a plain GET, no login.
# "path": the .do action URL (no query string).
# "query": a fixed query string this view always needs -- empty string if none.
LIST_CONFIGS = {
    "current": {
        "path": f"{BASE}/prepareCurrentOpportunities.do",
        "query": "currentType=cft",
        "title": "Current Opportunities (open for bidding)",
    },
    "opened": {
        "path": f"{BASE}/common/viewOpenedTenders.do",
        "query": "",
        "title": "Opened Bids (submission closed, in evaluation/awarding)",
    },
    "awarded": {
        "path": f"{BASE}/viewAllAwardedContracts.do",
        "query": "",
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
