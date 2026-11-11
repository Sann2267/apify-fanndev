"""Shared constants for the Tunisia TUNEPS (Tunisia National e-Procurement System) tenders scraper.

See CRAWLING_METHOD.md for how this API was discovered and verified. TUNEPS
(`www.tuneps.tn`, run by the Haute Instance de la Commande Publique / HAICOP,
Presidency of Government) is a client-rendered Angular SPA whose bundled
JavaScript hard-codes a genuinely public, unauthenticated JSON API for the
"Appel d'offres" (tender) listing and detail pages of its public portal --
no login, no API key, no session cookie required.
"""

BASE = "https://www.tuneps.tn/api2/portail"

LIST_PATH = f"{BASE}/bid/master/data"
DETAIL_PATH = f"{BASE}/bid/master/{{bid_id}}"

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8,ar;q=0.7",
    "Content-Type": "application/json",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0  # seconds

# The list endpoint's own page size is caller-controlled (unlike some peer
# targets in this project) -- limit=100 was confirmed to work cleanly during
# recon, so pagination advances by page (offSet += limit) rather than by date.
RESULTS_PER_PAGE = 100

# Minimum pause between sequential list-page requests.
LIST_PAGE_DELAY = 1.0

MAX_LIST_PAGES_SAFETY_CAP = 200  # hard stop even if maxResults implies more pages

# Every list query always applies this filter -- TUNEPS's own public portal
# component does the same (publicYn == "Y" means "published to the public
# portal", as opposed to a tender still in an internal drafting/review state
# that a logged-in buyer might see in the "acheteur" workspace but the public
# never does).
PUBLIC_YN_FILTER = {"key": "publicYn", "value": "Y", "specificSearch": "="}
