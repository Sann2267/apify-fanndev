"""Shared constants for Fiji's Ministry of Finance e-tendering site,
hosted on the third-party TenderLink platform at
`portal.tenderlink.com/financefiji`.

See CRAWLING_METHOD.md for the full recon writeup. Short version: unlike
this session's Saint Lucia recon (a different TenderLink deployment that
renders its tender table client-side via a jQuery template, harder to
scrape), Fiji's TenderLink instance renders both of its public list pages
as plain server-rendered HTML tables -- no login required to *view* the
list (only to see full details/documents or respond, which this actor
does not attempt):

1. **current** -- `/financefiji/alltenders/`: currently open tenders, ~17
   at recon time. Columns: Notice (reference number), Summary (title,
   sometimes embedding the procuring entity name inline), Close Date/Time.
2. **awards** -- `/financefiji/tenderfunction/?tenderaward=&allawards=`:
   tenders awarded within the past 36 months, ~369 at recon time. Same
   3-column shape, but the Summary cell for an awarded tender embeds
   "Awarded to: <company name>" at the end -- split out into a separate
   `awardedTo` field by this actor rather than left buried in free text.

No pagination on either page -- each GET already returns every row for
that list in one response. `https://portal.tenderlink.com/robots.txt`
doesn't exist (the platform's bare domain serves its own marketing
homepage instead of a robots.txt file at that path) -- treated as
unrestricted, same convention already used elsewhere in this portfolio for
a missing robots.txt.
"""

BASE = "https://portal.tenderlink.com/financefiji"

CURRENT_TENDERS_URL = f"{BASE}/alltenders/"
AWARDS_URL = f"{BASE}/tenderfunction/?tenderaward=&allawards="

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
