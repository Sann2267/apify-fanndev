"""Shared constants for Ecuador's SERCOP "Contrataciones Abiertas Ecuador"
OCDS open-data API.

See CRAWLING_METHOD.md for how these endpoints were discovered and verified.
This is SERCOP's (Servicio Nacional de Contratacion Publica) *separate*
public open-data platform at `datosabiertos.compraspublicas.gob.ec` -- not
the login-walled SOCE bidding portal at `www.compraspublicas.gob.ec`. It was
built with the Open Contracting Partnership (OCP) and CAF (Banco de
Desarrollo de America Latina) specifically so third parties can query and
download procurement data without an account. No login, no API key for
either endpoint this actor uses.
"""

BASE = "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/api"

# Keyword + year search over procurement processes. `year` and `search` are
# both mandatory upstream (search needs >= 3 characters) -- there is no
# "browse everything" mode, see CRAWLING_METHOD.md.
SEARCH_ENDPOINT = f"{BASE}/search_ocds"

# Full OCDS release history for one ocid (from a search_ocds row, or a URL
# path segment on the platform's own "Procedimiento" viewer pages).
RECORD_ENDPOINT = f"{BASE}/record"

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-EC,es;q=0.9,en;q=0.8",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0  # seconds, exponential backoff

# SERCOP's own search_ocds page size (observed, not configurable via params).
LIST_PAGE_DELAY = 1.0  # pause between sequential list-page requests
MAX_LIST_PAGES_SAFETY_CAP = 200

MIN_YEAR = 2015
MIN_SEARCH_LEN = 3
