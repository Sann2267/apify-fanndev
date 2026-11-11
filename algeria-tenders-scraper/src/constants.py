"""Shared constants for the Algerian Ministry of National Defense (MDN)
tenders scraper.

See CRAWLING_METHOD.md for the full recon writeup. Short version: Algeria's
central procurement bulletin (BOMOP, published by ANEP) was independently
verified UNREACHABLE at recon time -- the modern public WordPress portal
(`bomop.anep.dz`, Google-indexed with real per-sector tender pages) failed
TLS handshake from three independent networks (this sandbox, the Claude
Code WebFetch tool, and Jina AI's reader proxy), all with a bare connection
close during the TLS handshake -- not a 403/WAF challenge, a genuine outage.
The only reachable ANEP-adjacent site (`bomopclassic.anep.dz`) is reachable
but requires a *paid subscription + login* to view the actual bulletin
content -- a stop condition for that source. The national e-procurement
portal (`marches-publics.gov.dz`, launched 2021) is dead (connection
timeout, no Wayback Machine crawl since April 2023). The energy-sector
bulletin (BAOSEM, a Sonatrach/Sonelgaz subsidiary, `baosem.com`) is live but
its tender-access page is itself a login/subscription gate.

Per the portfolio's established "decentralized ministry sites" pattern
(seen with Botswana/Namibia when their central portals failed), several
individual Algerian ministries publish their own tenders directly and
publicly on their own `.gov.dz`/`.dz` sites. Of the candidates checked
(Ministry of Commerce, Ministry of Environment, Ministry of Justice --
WAF-blocked, SAFQATIC telecom-sector portal), the **Ministry of National
Defense (MDN)** was the clear best fit: genuinely live (newest item dated
3 days before recon), zero login wall, a clean `robots.txt` that only
blocks `/logs/` and CSS/JS asset directories, and by far the richest/most
active feed (over 2,200 tender notices across a 10-month rolling window on
the "current" page alone). Despite the name, MDN's own procurement covers
ordinary public-works, hospital-equipment, and catering/logistics tenders
for military regions, garrisons, and affiliated public hospitals -- not
classified defense material.
"""

BASE = "https://www.mdn.dz/site_principal/sommaire/appels"

LATEST_URL = f"{BASE}/appels_fr.php"
ARCHIVED_URL = f"{BASE}/archives_appels_fr.php"

VALID_MODES = ("latest", "archived")

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0

# mdn.dz serves a certificate chain missing its intermediate CA (the exact
# same class of bug documented for Nepal/Eswatini in this portfolio) --
# `verify=False` is required; plain httpx/requests with default cert
# checking fails with "unable to get local issuer certificate".
VERIFY_TLS = False

FRENCH_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}
