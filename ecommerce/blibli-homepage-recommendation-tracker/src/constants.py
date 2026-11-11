"""Endpoints, TLS profiles and tuning constants for the Blibli homepage
recommendation tracker.

WAF profile (recon 2026-09-01)
-------------------------------
Same Cloudflare setup re-verified against these endpoints specifically,
identical to every other actor in this portfolio targeting `www.blibli.com`
(see `blibli-promo-extractor` / `blibli-store-review-analyzer`):

1. **TLS/JA3.** Plain `httpx` and un-impersonated `curl_cffi` both 403 with
   a large HTML shell. Any `curl_cffi` impersonation profile returns 200.
2. **`Referer` is mandatory.** A good JA3 without it still 403s.

No cookie, token or login is required on any endpoint below -- the feed
returned is Blibli's *anonymous/default* ranking (no session, no cookies
sent), which is also the reproducible, cacheable variant worth scraping.
"""

ORIGIN = "https://www.blibli.com"

# Lists the homepage's content tabs: "Untukmu" (For You, MANUAL/personalized),
# "Zona affiliate" (MANUAL), plus several auto-generated category tabs
# (source: AUTOMATIC), e.g. "Handuk", "Hobi & Koleksi". Each tab carries both
# a long opaque `id` (a UUID-like string) and a short `name` (`TAB_1`,
# `TAB_5-4`, ...) -- see the endpoint note below for why `name` is the one
# that matters.
TABS_API = f"{ORIGIN}/backend/content-api/homepage-infinite-recommendations/tabs"

# The feed itself. **Must be built with the tab's `name` field (`TAB_1`),
# not its `id`.** The `id` looks like the obvious key (it is a stable-looking
# UUID-shaped string) and is a trap: every path shape tried with `id` in it
# returns 404/500 (`HOMEPAGE_INFINITE_RECOMMENDATION_TAB_NOT_FOUND` once the
# path shape is otherwise correct), while the short `name` from the tabs
# listing works immediately. Costs real debugging time if not documented.
FEED_API_TEMPLATE = ORIGIN + "/backend/content-api/homepage-infinite-recommendations/{tab_name}/products"

TLS_PROFILE_LADDER = ("chrome124", "safari17_0", "firefox133", "chrome131", "chrome99_android")

BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.5
REQUEST_TIMEOUT = 45

# This is an *infinite/personalized recommendation* feed (its own field says
# so: `extendedData.personalizationLogic` is literally `DEFAULT_RERANK`), not
# a fixed enumerable catalogue. The endpoint's own `paging.total_page` value
# is noisy garbage here -- observed oscillating 2, 2, 2, 1, 2, 2, 1 across
# consecutive pages of the SAME tab in one sweep, and some tabs omit the
# `paging` key entirely. Do not use it as a stop condition. A hard page cap
# plus "this page added zero new ids" are the only trustworthy stop signals.
DEFAULT_MAX_PAGES_PER_TAB = 15

# Same 20-item default the endpoint itself reports via `item_per_page` when
# it bothers to report paging at all; used only as a display/estimate hint.
FEED_ITEM_PER_PAGE_HINT = 20
