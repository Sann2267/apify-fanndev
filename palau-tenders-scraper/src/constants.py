"""Shared constants for the Republic of Palau's ROP Procurement page,
`www.palaugov.pw/rfp-bids/`.

See CRAWLING_METHOD.md for the full recon writeup. Short version: unlike
every other tender actor built in this portfolio's session, Palau has no
separate current/closed/results view -- ROP Procurement is a single
WordPress page with three plain HTML `<table>`s, one per procurement
category, each preceded by an `<h3>` heading used as the category label:

1. **BHR** -- routine goods/services procurement run through the Bureau of
   Human Resources' procurement office.
2. **CIP** -- Capital Improvement Projects (construction/design-build).
3. **Other Organizations** -- procurement run by other government bodies
   (frequently empty -- a placeholder row with no data is upstream's own
   normal "nothing posted right now" state for this section, not a
   scraping bug).

Each table shares the same 5-column shape (header wording varies slightly
per table -- "Items/Services" vs. "Projects" vs. "Items/Services/Summary",
"Bid or RFP Number" vs. "Announcement/Reference #" -- normalized here to
one field set): Ministry/Department, Description, Bid/RFP Number (linked
to the PDF notice), Opening Date, Closing Date.

No pagination, no separate archive page found on this site for past/closed
tenders or contract awards -- this page reflects "what's open right now"
only, reported honestly as such rather than fabricating a historical view
that doesn't exist upstream (same honesty convention already used by
`suriname-tenders-scraper` for its `notices` list type).

`https://www.palaugov.pw/robots.txt` is a stock WordPress robots.txt
(`Disallow: /wp-admin/`, `Allow: /wp-admin/admin-ajax.php`) with no
Claude/AI-crawler-specific group.
"""

BASE = "https://www.palaugov.pw"

RFP_BIDS_URL = f"{BASE}/rfp-bids/"

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
