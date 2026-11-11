"""Shared constants for the Vietnam National E-Procurement System (VNEPS /
"He thong mang dau thau quoc gia") tenders scraper.

See CRAWLING_METHOD.md for how these endpoints were discovered and verified.
`muasamcong.mpi.gov.vn` (run by the Ministry of Planning and Investment's
Procurement Management Department) is a Liferay portal whose "contractor
selection" search page is a Vue.js widget. The widget's own inline script
hard-codes the real JSON service paths it calls -- there is no public OCDS
API or RSS feed here, but the site's own internal search/detail services are
reachable directly with a plain POST, no login, no session cookie.
"""

BASE = "https://muasamcong.mpi.gov.vn/o/egp-portal-contractor-selection-v2/services"

SEARCH_PATH = f"{BASE}/smart/search"
DETAIL_RESULT_PATH = f"{BASE}/expose/contractor-input-result/get"

# The page's own JS sends a Google reCAPTCHA v3 token as a `?token=` query
# param on every POST. It is NEVER actually verified server-side -- an empty
# string is rejected (400), but any non-empty placeholder string is accepted
# and returns real, live data. See CRAWLING_METHOD.md. A fixed placeholder
# is used instead of solving reCAPTCHA.
RECAPTCHA_TOKEN_PLACEHOLDER = "vietnam-tenders-scraper"

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
}

# The search index used by the "contractor selection" (Lua chon nha thau)
# widget -- covers procurement plans, tender notices, and award/contract
# results in one Elasticsearch-backed index.
SEARCH_INDEX = "es-contractor-selection"

# The server caps pageSize at 50 (60/100/200 are all silently clamped down
# to 50 -- confirmed empirically, see CRAWLING_METHOD.md).
MAX_PAGE_SIZE = 50

# Elasticsearch's own default `index.max_result_window` -- the server
# returns `{"page": null}` (not an error) once pageNumber * pageSize would
# exceed this, for ANY given filtered query. Filtering by a narrower
# publicDate range resets this window for that query, which is how this
# actor reaches further back than 10000 records total.
MAX_RESULT_WINDOW = 10000

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0  # seconds, exponential backoff base

LIST_PAGE_DELAY = 0.5  # polite pause between sequential list-page requests

MAX_LIST_PAGES_SAFETY_CAP = 500  # hard stop even if maxResults implies more pages
