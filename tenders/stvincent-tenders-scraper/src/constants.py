"""Shared constants for the St. Vincent and the Grenadines Central
Procurement Board's eProcurement portal (`procurement.gov.vc/eprocure`).

See CRAWLING_METHOD.md for the full recon writeup. Short version: SVG runs a
dedicated Joomla-based eProcurement microsite, distinct from the general
government portal (`gov.vc`). Its three relevant listing pages are plain
server-rendered HTML tables -- no JS framework, no API, no pagination
controls (each page already returns every row for that list in one response):

1. **current** -- `/eprocure/index.php/current-bids`: currently open
   solicitations (Invitation to Bid, Request for Expressions of Interest,
   Request for Quotation, etc.) across all ministries/projects. ~21 rows at
   recon time. Each row's Description cell links directly to the bid/ToR PDF.
2. **closed** -- `/eprocure/index.php/recently-closed-bids`: historical
   archive of the same table shape. ~400+ rows at recon time.
3. **awards** -- `/eprocure/index.php/contract-award-notices`: one row per
   calendar year (2017-2025), each linking to one or more quarterly "Award
   of Contracts" PDF documents (not individual contract-level records --
   SVG only publishes these as periodic PDF bundles).

No login, no CSRF handshake, no WAF challenge encountered -- plain GETs
returned 200 on the first try with `curl_cffi` default headers.
`https://procurement.gov.vc/eprocure/robots.txt` is a stock Joomla robots.txt
(`Disallow` limited to `/administrator/`, `/cache/`, `/components/`, etc. --
none of which cover `/index.php/current-bids` and friends) with no
Claude/AI-crawler-specific group of any kind.
"""

BASE = "https://procurement.gov.vc"
EPROCURE = f"{BASE}/eprocure"

CURRENT_BIDS_URL = f"{EPROCURE}/index.php/current-bids"
CLOSED_BIDS_URL = f"{EPROCURE}/index.php/recently-closed-bids"
AWARDS_URL = f"{EPROCURE}/index.php/contract-award-notices"

VALID_LIST_TYPES = ("current", "closed", "awards")

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0
