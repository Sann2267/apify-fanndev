"""Constants for the Clutch.co agency-directory Actor.

Everything here was measured against the live site on 2026-09-18, not assumed.
The numbers in ``EXPECTED`` are what the ``reference`` mode re-tests on every
run, so a silent change upstream shows up as a failed expectation rather than
as a dataset that is quietly half the size it should be.
"""

BASE = "https://clutch.co"
SITEMAP_INDEX = f"{BASE}/sitemap.xml"

# -- TLS -------------------------------------------------------------------
#
# Cloudflare sits in front of clutch.co and gates on the TLS fingerprint before
# it reads a single header -- and **which profiles pass depends on the IP**.
#
#   profile            local (residential ID)   Apify datacenter
#   safari17_0         200 / 1.45 MB            200 / 2.70 MB      <- leads
#   firefox133         200 / 1.45 MB            200 / 2.70 MB
#   chrome124          200 / 1.46 MB            403 / 5.9 KB       <- flips
#   chrome110          403 / 5.9 KB             403 / 5.9 KB
#   edge101            403 / 6.0 KB             403 / 6.0 KB
#   chrome99_android   403 / 6.0 KB             403 / 5.9 KB
#
# chrome124 led during local recon and is challenged outright from the platform:
# the gate is per fingerprint AND per IP, so a recon matrix is a starting point,
# not a verdict (the "second gate only appears on the platform" pattern). The
# ladder therefore leads with the two profiles that answer from BOTH, and the
# client remembers whichever one wins at runtime.
#
# chrome131 is deliberately absent, being widely blocklisted in 2026.
TLS_LADDER = ("safari17_0", "firefox133", "chrome124")

# Profiles challenged everywhere tried. Kept only so the reference mode can
# re-test them: if these start answering 200, the gate has been relaxed.
TLS_CHALLENGED = ("chrome110", "edge101", "chrome99_android")

DEFAULT_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "upgrade-insecure-requests": "1",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0

# A challenge and a timeout are different failures and get different budgets.
# A timeout says "try again"; a challenge says "this fingerprint is wrong from
# this IP", and the cheapest answer is the next profile, not a third rejection.
CHALLENGE_RETRIES = 2
CHALLENGE_DELAY = 1.0

# ...but a refusal is often just a moment, not a verdict about the profile. If
# the whole ladder is refused, the run waits and walks it again before giving up:
# a 0.0.1 run survived 8 refusals in 10 requests by being stubborn, and a 0.0.2
# run with one tight pass failed after 6.
LADDER_ROUNDS = 3
LADDER_ROUND_DELAY = 6.0
REQUEST_TIMEOUT = 90

MODES = ("directory", "profile", "reviews", "categories", "reference")

# -- robots.txt ------------------------------------------------------------
#
# https://clutch.co/robots.txt, fetched 2026-09-18. Plain category paths and
# `?page=` are allowed; every filter parameter below is disallowed for every
# user agent, so this Actor strips them from user-supplied URLs instead of
# quietly sending a request the site asked nobody to send.
ROBOTS_DISALLOWED_PARAMS = (
    "sort_by",
    "project_cost",
    "service_provided",
    "industry",
    "location",
    "verified",
    "geona_id",
    "client_budget",
    "industries",
    "hourly_rate",
    "related_services",
    "reviews",
)
ROBOTS_DISALLOWED_PREFIXES = ("/lp/", "/claim-profile")

# -- directory rows --------------------------------------------------------
#
# A category page mixes four kinds of row, and only one of them is the ranked
# list the page claims to be:
#
#   Directory      -- the ranked result set, 50 per page, different every page
#   Leaders Matrix -- 30 rows, byte-identical on EVERY page of the category
#   Sponsor        -- paid placement, 43 rows, page 1 only
#   featured       -- paid placement, 6 rows on page 1, 14 on every later page
#
# Rows whose type is in PINNED_ROW_TYPES repeat across pages. A scraper that
# does not dedupe emits 44 duplicates for every page it walks.
ROW_TYPE_DIRECTORY = "Directory"
PINNED_ROW_TYPES = ("Leaders Matrix", "featured")
PAID_ROW_TYPES = ("Sponsor", "featured")

# `?page=1` does NOT return page 1 -- it returns page 2, byte-for-byte the same
# as `?page=2`. Page 1 is the bare URL with no query at all. Looping 1..N would
# therefore skip page 1 entirely and emit page 2 twice.
FIRST_PAGE_HAS_NO_PARAM = True

DEFAULT_MAX_PAGES = 3
DEFAULT_MAX_ITEMS = 0  # 0 = no cap beyond maxPages
DEFAULT_REVIEW_PAGES = 3

# Categories used by the reference mode and offered as input hints.
SAMPLE_CATEGORIES = (
    "web-developers",
    "developers",
    "web-designers",
    "seo-firms",
    "hr",
    "pr-firms",
    "agencies/digital",
    "it-services",
)

# -- measured expectations (re-tested by `reference`) ----------------------
EXPECTED = {
    "directoryRowsPerPage": 50,
    "leadersMatrixRows": 30,
    "sponsorRowsPage1": 43,
    "webDevelopersLastPage": 1933,
    "webDevelopersTotalClaim": 96607,
    "profileReviewsPerPage": 10,
    "note": (
        "Measured on clutch.co/web-developers, 2026-09-18. Row counts per page are "
        "stable but not contractual -- the reference mode reports what it finds today "
        "rather than asserting these numbers."
    ),
}
