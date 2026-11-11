"""Shared constants for Djibouti's public procurement portal,
`marchespublics.gouv.dj` (Commission Nationale des Marches Publics /
Autorite de Regulation des Marches Publics).

See CRAWLING_METHOD.md for the full recon writeup. Short version: a
Laravel + Livewire site with two relevant pages:

1. **current** -- `/marches`: currently listed tenders (Livewire
   component, server-rendered on first GET). Only the first page's ~7
   cards are reachable via a plain HTTP GET -- Livewire's own pagination
   beyond page 1 requires its AJAX update protocol (a POST with a
   component snapshot/checksum), which this actor does not implement;
   `?page=N` in the URL does NOT change the server-rendered result (
   verified empirically, not assumed). Reported honestly as "what's
   listed on the site's first page right now", not a fabricated full
   archive.
2. **awards** -- `/attribution`: the current week's contract-award
   notices as a plain HTML table (NOT a Livewire component -- no
   `?page=` limitation observed), with supplier name and the awarded
   amount in Djibouti Francs (DJF). ~9 rows at recon time, dated to a
   specific announcement week ("Attributions du <date>"); no historical
   archive/date-picker was found for past weeks.

`https://marchespublics.gouv.dj/robots.txt` is a blanket allow
(`User-agent: * / Disallow:` -- the Disallow directive is present but
empty, meaning nothing is disallowed) with no Claude/AI-crawler-specific
group.
"""

BASE = "https://marchespublics.gouv.dj"

CURRENT_TENDERS_URL = f"{BASE}/marches"
AWARDS_URL = f"{BASE}/attribution"

VALID_LIST_TYPES = ("current", "awards")

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0
