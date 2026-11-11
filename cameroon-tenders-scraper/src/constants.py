"""Shared constants for the ARMP Cameroon (Agence de Regulation des Marches
Publics) tenders scraper.

See CRAWLING_METHOD.md for how these URLs / TLS profile were discovered and
verified. The site (armp.cm) is a server-rendered PHP/Laravel webapp (footer
sessions/cookies: XSRF-TOKEN, armp_session -- standard Laravel), no JSON API,
no WAF/CDN fingerprint observed. UI toggles French/English (`/lang?val=fr|en`)
but the underlying publication content itself is authored by the procuring
entity, usually in French.
"""

BASE = "https://armp.cm"

# Each entry is a public "Journal des Marches Publics" (JDM) listing view,
# reachable with a plain GET, no login. "path"/"query" build the page-1 URL;
# page N>1 appends "&page=N" (confirmed identical whether page=1 is present
# explicitly or omitted). "val" is armp.cm's own internal category id, kept
# here for building the sidebar-badge lookup that gives an honest
# _totalAvailable count fresh per run (see extractor.find_category_total).
LIST_CONFIGS = {
    "latest": {
        "path": BASE + "/",
        "query": "",
        "val": None,
        "title": "Latest publications (all types mixed: notices, addenda, award decisions, award communiques)",
    },
    "national": {
        "path": f"{BASE}/filtres",
        "query": "type=avis&val=1",
        "val": "1",
        "title": "National Call for Tenders (Appel d'Offres National)",
    },
    "international": {
        "path": f"{BASE}/filtres",
        "query": "type=avis&val=4",
        "val": "4",
        "title": "International Call for Tenders (Appel d'Offres International)",
    },
    "quotation": {
        "path": f"{BASE}/filtres",
        "query": "type=avis&val=5",
        "val": "5",
        "title": "Request for Quotation (Demande de Cotation)",
    },
    "proposal": {
        "path": f"{BASE}/filtres",
        "query": "type=avis&val=7",
        "val": "7",
        "title": "Request for Proposal",
    },
    "expression_of_interest": {
        "path": f"{BASE}/filtres",
        "query": "type=avis&val=12",
        "val": "12",
        "title": "Call for Expression of Interest (Appel a Manifestation d'Interet)",
    },
    "restricted": {
        "path": f"{BASE}/filtres",
        "query": "type=avis&val=21",
        "val": "21",
        "title": "Restricted Call for Tenders (Appel d'Offres Restreint)",
    },
    "agreement": {
        "path": f"{BASE}/filtres",
        "query": "type=avis&val=6",
        "val": "6",
        "title": "Agreement (Accord-cadre)",
    },
}

VALID_LIST_TYPES = tuple(LIST_CONFIGS.keys())

DETAIL_PATH = f"{BASE}/details"

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0

RESULTS_PER_PAGE = 10  # server-fixed; no page-size query param was found to change this
