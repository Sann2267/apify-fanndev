"""Shared constants for Uruguay's ARCE (Agencia Reguladora de Compras
Estatales) native OCDS API at comprasestatales.gub.uy.

See CRAWLING_METHOD.md for how these endpoints were discovered and verified.
This is a genuinely public, purpose-built OCDS (Open Contracting Data
Standard) service -- documented on ARCE's own "datos y estadisticas" page --
not a reverse-engineered internal admin grid. No login, no API key, for any
endpoint this actor uses.
"""

BASE = "https://www.comprasestatales.gub.uy/ocds"

# Most recent 500 releases across the whole platform, newest first. Confirmed
# live: exactly 500 <item> entries on every fetch during recon.
RSS_LATEST = f"{BASE}/rss"

# Every release published in one calendar month, newest first, NOT capped at
# 500 (a single month observed during recon carried 11,000+ releases) -- see
# CRAWLING_METHOD.md. `{year}` is 4-digit, `{month}` is zero-padded 1-12.
# Year alone (no month) 404s upstream -- both or neither, never just year.
RSS_MONTH = BASE + "/rss/{year}/{month:02d}"

# Purchase-level "record package" (OCDS spec): returns *links* to each
# release event for one id_compra, not the full release content inline --
# see CRAWLING_METHOD.md ("linked" vs Ecuador SERCOP's "compiled" record).
RECORD_ENDPOINT = BASE + "/record/{id_compra}"

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    # Deliberately generic -- an explicit "application/json" Accept header
    # was observed to 406 the XML-only /rss endpoints during recon (content
    # negotiation quirk, not a block). See CRAWLING_METHOD.md.
    "Accept": "*/*",
    "Accept-Language": "es-UY,es;q=0.9,en;q=0.8",
}

MAX_RETRIES = 4
RETRY_DELAY_BASE = 2.0  # seconds, exponential backoff

MAX_LIST_RESULTS = 5000
MIN_YEAR = 2014  # ARCE's own historical-data claim: "232,000+ bids from 2014 onward"

# Politeness delay between the sequential per-release-link fetches inside one
# id_compra's detail build (usually 1-5 links; never large).
DETAIL_LINK_DELAY = 0.3
