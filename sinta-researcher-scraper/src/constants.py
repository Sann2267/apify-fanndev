"""URLs, routes, headers -- all in one place.

Recon summary (2026-09-08): SINTA (Science and Technology Index) is the
Indonesian government's national research portal, run by the Ministry of
Higher Education, Science and Technology. Everything used here is plain
server-rendered HTML on Apache -- no client-side rendering, no login, no
WAF challenge.

Scale at build time: **335,591 researchers** across 33,560 listing pages,
and **5,567 affiliations** across 557 pages.

What makes this dataset distinctive is the part Google Scholar does not
have: SINTA's own national scores (SINTA Score Overall / 3Yr, Affil Score)
plus per-source publication metrics (Scopus, Google Scholar, Web of
Science) side by side on one record, with affiliation and department
attached.

**Domain gotcha:** the portal used to live on `sinta.kemdikbud.go.id`.
That host now fails DNS resolution outright -- which reads like a dead
site, and nearly got this target written off during Babak 43 research.
The ministry was split and the portal moved to
`sinta.kemdiktisaintek.go.id` (200, live). Always look for a successor
domain before declaring a `.go.id` / `.gov.*` portal dead.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://sinta.kemdiktisaintek.go.id"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
}

# --- routes ------------------------------------------------------------
PATH_AUTHORS = "/authors"
PATH_AUTHOR_PROFILE = "/authors/profile/{sinta_id}"
PATH_AFFILIATIONS = "/affiliations"
PATH_AFFILIATION_PROFILE = "/affiliations/profile/{affil_id}"

MODES = ["authors", "author", "affiliations"]

# 10 records per listing page on both /authors and /affiliations.
PAGE_SIZE = 10

# Query params confirmed working over GET:
#   page=<n>   pagination
#   q=<text>   free-text author search ("zainul" -> 153 records / 16 pages,
#              down from the unfiltered 335,591 / 33,560)
#
# NOT exposed as an input: `sort`. The sort control is part of a POST form
# and passing `sort=3` over GET returned the *same* first page as the
# default, i.e. it is ignored rather than honoured -- the exact
# "silently-ignored param" trap this portfolio hit on Blibli and DJKN. It is
# left out instead of shipping a knob that does nothing.
PARAM_PAGE = "page"
PARAM_QUERY = "q"

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
