"""Shared constants for Samoa's Ministry of Finance (MOF) tender pages,
`www.mof.gov.ws`.

See CRAWLING_METHOD.md for the full recon writeup. Short version: MOF Samoa
runs a Webflow-built site with two relevant CMS-collection pages, both
fully server-rendered (no client-side fetch needed):

1. **current** -- `/tender-adverisements` (note: upstream's own spelling
   typo, kept verbatim since it's the real path): currently open tenders,
   ~101 cards at recon time, each with title, closing date, agency, contact
   details, and 1+ document links (advertisement/notice, tender document,
   annexes -- filenames vary per tender).
2. **awards** -- `/tender-awards`: contract award records, ~40 cards at
   recon time, each with contract name, approval date, implementing
   agency, winning bidder(s) + contract amounts (free text, sometimes
   multiple lines for multi-lot contracts), and the full list of all
   bidders who competed.

The two pages use different Webflow CMS collections (different CSS class
namespacing) and have genuinely different fields, so they're parsed by two
separate functions rather than forced into one shared shape (same pattern
already used elsewhere in this portfolio, e.g. `suriname-tenders-scraper`'s
tenders vs. notices, `stvincent-tenders-scraper`'s bids vs. awards).

No pagination controls observed on either page -- each GET already returns
every card for that list in one (large, ~150KB-2.7MB) response; Webflow
renders every CMS collection item server-side rather than paging server-
side, unlike the Joomla sites elsewhere in this portfolio.

`https://www.mof.gov.ws/robots.txt` is a minimal, informal file (not even
valid `User-agent`/`Disallow` syntax -- just a keyword comment line and a
`Sitemap:` pointer) with no restriction of any kind, no Claude/AI-crawler
mention.
"""

BASE = "https://www.mof.gov.ws"

CURRENT_TENDERS_URL = f"{BASE}/tender-adverisements"
AWARDS_URL = f"{BASE}/tender-awards"

VALID_LIST_TYPES = ("current", "awards")

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
