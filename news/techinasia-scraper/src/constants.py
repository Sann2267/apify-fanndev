"""Endpoints, pagination ceilings and harvested credentials for techinasia.com.

WAF posture (verified 2026-09-21, Phase 1 recon)
------------------------------------------------
There is none. ``www.techinasia.com`` sits on plain nginx with no Cloudflare,
DataDome, PerimeterX, Akamai or AWS WAF in front of it. A bare ``requests`` call
with a stock User-Agent returns 200, and all five curl_cffi profiles on the
ladder (chrome124 / chrome131 / chrome136 / safari17_0 / edge101) returned
byte-identical 337,178-byte homepages. No cookie warm-up, no token, no signed
parameter, no TLS gate.

We still route through curl_cffi rather than ``requests`` because it costs
nothing and keeps the actor alive if Tech in Asia puts a CDN in front of the
origin later. ``chrome131`` is the default only because it is the portfolio
baseline -- no evidence here argues for any particular profile.

Three separate backends serve the site
--------------------------------------
1. ``/wp-json/techinasia/2.0/``  WordPress REST -- the editorial surface.
2. ``/api/2.0/``                Laravel -- the company database and job board.
3. Algolia                      the real search, plus company funding facets.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

BASE_URL = "https://www.techinasia.com"
WP_API = f"{BASE_URL}/wp-json/techinasia/2.0"
LARAVEL_API = f"{BASE_URL}/api/2.0"

# No WAF was found, so this is a longevity hedge rather than a bypass. The
# ladder is tried in order only if a request fails outright.
TLS_PROFILES = ("chrome131", "chrome124", "safari17_0", "edge101", "chrome136")

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE_URL}/",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
REQUEST_TIMEOUT = 45

# --------------------------------------------------------------------------
# WordPress REST ceilings -- both are hard 400s, not silent truncation
# --------------------------------------------------------------------------
#
# ``per_page`` above 30 and ``page`` above 30 both return
# ``{"code":"rest_invalid_param"}``. The ceiling on ``page`` is independent of
# ``per_page`` (page=31 fails even at per_page=1), so every WP list route tops
# out at 30 x 30 = 900 records no matter how it is sliced.
#
# This matters because the envelope LIES about it: ``/posts`` reports
# ``total: 79475, total_pages: 2650`` and then refuses page 31. Anything past
# the newest 900 posts of a route has to come from Algolia or from slicing
# across categories and tags.

WP_MAX_PER_PAGE = 30
WP_MAX_PAGE = 30
WP_MAX_RECORDS_PER_ROUTE = WP_MAX_PER_PAGE * WP_MAX_PAGE  # 900

# --------------------------------------------------------------------------
# Laravel ceilings -- far more generous
# --------------------------------------------------------------------------
#
# ``per_page=100`` is accepted and there is no page cap: /companies walks all
# 4,826 pages (120,649 companies) and page 4,827 returns an empty data array
# rather than an error. Standard Laravel paginator envelope, so ``last_page``
# and ``next_page_url`` are both trustworthy here (unlike the WP ``total_pages``).

LARAVEL_MAX_PER_PAGE = 100

# --------------------------------------------------------------------------
# Algolia
# --------------------------------------------------------------------------
#
# Credentials are harvested from the app bundle at runtime (see client.py).
# These are the values verified on 2026-09-21 and are used as a seed; a 403
# triggers a re-harvest, because the bundle filename carries a content hash
# that rotates on every front-end deploy.
#
# The key is Algolia's public *search-only* key, shipped to every browser that
# loads the site. It is not a credential we had to defeat anything to obtain.

ALGOLIA_APP_ID = "219WX3MPV4"
ALGOLIA_SEARCH_KEY = "b528008a75dc1c4402bfe0d8db8b3f8e"
ALGOLIA_TRENDING_KEY = "d7c7832cdeaee9b669eb4824da869c3a"

ALGOLIA_INDEX_POSTS = "posts"
ALGOLIA_INDEX_COMPANIES = "companies"
ALGOLIA_INDEX_JOBS = "job_postings"
ALGOLIA_INDEX_TRENDING = "asktia_top_pageviews"

# Algolia's own paginationLimitedTo, confirmed empirically: hitsPerPage=100
# serves pages 0-9 and page 10 comes back with zero hits and nbPages=0. The
# window is 1,000 records per *query*, so a broad sweep has to be split into
# narrower queries (per category, per country, per funding stage) to go deeper.
ALGOLIA_MAX_WINDOW = 1000
ALGOLIA_MAX_HITS_PER_PAGE = 1000

# Deliberately NOT exposed by this actor:
#   posts_conversions -- 174 records of Tech in Asia's own subscriber-conversion
#   and lifetime-value figures per article (total_conversions, total_ltv,
#   avg_ltv). The public search key over-permits and reaches it, but it is
#   internal revenue reporting, rendered nowhere on the site, and outside what
#   this actor is for.

# --------------------------------------------------------------------------
# Dataset envelope
# --------------------------------------------------------------------------

RECORD_POST = "POST"
RECORD_COMPANY = "COMPANY"
RECORD_JOB = "JOB"
RECORD_CATEGORY = "CATEGORY"
RECORD_TAG = "TAG"
RECORD_TOPIC = "TOPIC"
RECORD_TRENDING_QUESTION = "TRENDING_QUESTION"
RECORD_ERROR = "ERROR"

# The full article body. Tech in Asia is a subscription publication, so the
# actor emits metadata and the publisher's own excerpt by default and only
# includes this field when the buyer explicitly asks for it.
CONTENT_FIELDS = ("content",)
