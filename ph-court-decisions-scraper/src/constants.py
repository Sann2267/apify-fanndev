"""Endpoints, headers, constants -- all in one place.

Recon summary (2026-09-07): elibrary.judiciary.gov.ph is the Philippine
Supreme Court's official E-Library -- the free, public full-text archive of
Supreme Court decisions and signed resolutions. It is a CodeIgniter/PHP app
on Microsoft-IIS with a bolted-on dtSearch full-text engine. No WAF, no
challenge, no login, no cookie gate; `curl_cffi` `chrome124` gets clean 200s
everywhere. Six rapid sequential document fetches all returned 200 in
0.27-0.32s each with no rate-limit response.

`robots.txt` returns **404** (IIS "File or directory not found") -- the site
declares no crawler restrictions at all, so there is no AI-bot directive to
honour or violate. Note separately that the document pages themselves carry
`<meta name="robots" content="noindex,nofollow">`; that is an *indexing*
directive aimed at search engines (both the canonical and the
printer-friendly variant of every document carry it, the classic
duplicate-content reason), not an access directive, and the site's own
dtSearch document view serves the identical text with no robots meta at all.
Defaults here stay deliberately gentle regardless -- see MAX_CONCURRENCY_*.

Three endpoints matter:

- `GET /thebookshelf/docmonth/<Mon>/<Year>/<page>` -- the decision listing for
  one month. Each `<li>` carries the case number, the party line and the
  decision date, and links the document as `/thebookshelf/showdocs/1/<docId>`.
  **Paginated**: Aug 2025 returned 85 items on page 1, 23 on page 2, 0 on
  page 3. There are no next-page links in the HTML, so an empty page is the
  only stop condition. Archive spans **1996 to present** (31 years).

- `GET /thebookshelf/showdocs/1/<docId>` -- one decision's full text inside
  `div.single_content`. Carries the Philippine Reports citation when the
  decision has been reported (e.g. "930 Phil. 215"), the division, the
  bracketed case-number/date line, the party line, the ponente and the
  complete opinion.

- `POST /assets/dtSearch/dtSearch_system_files/dtisapi6.dll` -- the dtSearch
  full-text engine behind the portal's own search iframe. `cmd=search` with
  `request=<query>` and `index=<token>`. **`pageSize=100` is honoured**
  (confirmed live: 100 result anchors in a single response), so search paging
  costs a tenth of what the portal's own 10-per-page UI does.

Two document id spaces exist and they are NOT interchangeable: dtSearch's
`DocId` is its own internal numbering, unrelated to the portal's `showdocs`
id. Confirmed live: G.R. No. 241587 (6 Aug 2025) is dtSearch `DocId=69244`
but portal `showdocs/1/70008`, while `showdocs/1/69244` is an entirely
different case (G.R. No. 235790, Sep 2022). Search results therefore carry
their own `documentUrl` (the dtSearch document view) and never a fabricated
showdocs link.

See CRAWLING_METHOD.md for the full recon log and captured examples.
"""

TLS_PROFILE = "chrome124"

# The server presents an incomplete certificate chain (it omits the
# intermediate), so a strict verify fails with "unable to get local issuer
# certificate" on every TLS profile. Verification is disabled for this host
# only. The data is public court records and nothing is ever sent upstream,
# so the exposure is limited to trusting the transport for read-only fetches.
VERIFY_TLS = False

BASE_URL = "https://elibrary.judiciary.gov.ph"
DOCMONTH_URL = f"{BASE_URL}/thebookshelf/docmonth"
# The trailing "1" is the portal's document-category id for
# "Decisions / Signed Resolutions" -- the corpus this actor covers.
SHOWDOCS_URL = f"{BASE_URL}/thebookshelf/showdocs/1"
SEARCH_FORM_URL = f"{BASE_URL}/search/search_form"
DTSEARCH_URL = f"{BASE_URL}/assets/dtSearch/dtSearch_system_files/dtisapi6.dll"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-PH,en;q=0.9",
}

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

MONTH_TO_NUMBER = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Earliest year the docmonth listing actually serves (confirmed live: the
# homepage's own year links start at 1996 and Jan 1996 returns 58 decisions).
ARCHIVE_FIRST_YEAR = 1996

# dtSearch index tokens as harvested from the live search form on
# 2026-09-07. The `*{hash}` part is a content hash that changes whenever the
# judiciary rebuilds an index, so these are a *fallback* only -- the client
# re-harvests them from SEARCH_FORM_URL at run time (trust-but-verify).
FALLBACK_SEARCH_INDEXES = {
    "sc_all": "*{1b34d74f9bb121cc1c90c69b6ed99f05} sc_all",
    "sc_decision": "*{81aab6aa66450ae68a1f722f505a17c7} sc_decision",
    "case_index": "*{13de3ac54c13e1aa07ffd30d188cf3f0} case_index",
    "sc_resolution": "*{25228a3adcb6fca12c8ef9e582ab0310} sc_resolution",
    "administrative_matter": "*{e3de1f36a8ce1b669b68e04d6d8ba537} administrative_matter",
    "bar_matter": "*{89c660891bb415c07ef7377635fc9d1e} bar_matter",
    "circular": "*{c5cc64bdd2b89dc064a17679aadd16eb} circular",
    "manual": "*{88f81c81db3b6eae2ee4bfda231fa6b6} manual",
}

# Corpora the judiciary lists in its own search form but whose dtSearch index
# files the server cannot open -- every query against them returns HTTP 200
# with "0 result(s)" plus the engine's own error string
# "$E 0001 Unable to access index C:\el...". Confirmed live for all three on
# 2026-09-07 with a query ("contract") that returns 5,000 hits on sc_all.
# Kept selectable, because the breakage is upstream and may be repaired, but
# a run against one emits an explicit diagnostic instead of a silent zero.
KNOWN_BROKEN_INDEXES = ("sc_resolution", "administrative_matter", "bar_matter")

DTSEARCH_INDEX_ERROR_MARKER = "Unable to access index"

SEARCH_CORPORA = tuple(FALLBACK_SEARCH_INDEXES)

# dtSearch's own request modes, straight from the form's <select name="searchType">.
SEARCH_TYPES = ("anywords", "allwords", "phrase", "bool")

# Confirmed live: dtSearch honours pageSize=100 (100 result anchors in one
# response) even though the portal's own UI only ever asks for 10.
SEARCH_PAGE_SIZE = 100

# dtSearch stops counting at this many matches and reports it as the total.
SEARCH_AUTO_STOP_LIMIT = 5000

# Sanity stops so a pagination bug can never spin forever.
MAX_SEARCH_PAGES = 200
MAX_LISTING_PAGES = 50

REQUEST_TIMEOUT = 60

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.0
