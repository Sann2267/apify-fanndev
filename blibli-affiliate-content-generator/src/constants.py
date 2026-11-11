"""Endpoints, TLS profiles and tuning constants.

WAF profile (recon 2026-09-01, see CRAWLING_METHOD.md)
-----------------------------------------------------
Cloudflare, with a mandatory `Referer` header, as on every Blibli surface.
The TLS ladder leads with `safari17_0` rather than a Chrome profile: it is
verified against all endpoints used here, and a sibling actor found that
Chrome fingerprints are specifically blocked on some `/backend/search/*`
paths. Sustained recon from one IP also drew intermittent 403s, so the
retry/backoff and profile rotation in `client.py` are load-bearing here,
not decorative -- and residential proxy is recommended for real runs.

What this actor can and cannot do about affiliate links
-------------------------------------------------------
Measured, not assumed:

* `POST /backend/affiliate/share-link` is **public** -- no cookie, no
  login. It mints Blibli's own AppsFlyer OneLink short link
  (`https://blibli.onelink.me/GNtk/...`) which redirects to the product
  page carrying `utm_campaign` / `utm_medium` / `utm_source` exactly as
  supplied. The site's own config calls this `appFlyersOneLink`.
* `POST /backend/affiliate/commission` returns **401 UNAUTHORIZED**, and
  `/member/p/affiliate` is a member-only route.

So Blibli's *commission attribution* sits behind a login and is out of
scope under this project's no-login constraint. This actor therefore
builds **tracking links, not commission links**: it mints the official
OneLink share URL and stamps whatever campaign/source/medium values the
user supplies -- which is where an affiliate or creator ID goes. That
distinction is stated plainly in the README and the output schema rather
than being papered over.
"""

ORIGIN = "https://www.blibli.com"

SEARCH_API = f"{ORIGIN}/backend/search/products"
# Public OneLink minter. Identical payloads return an identical link, so
# re-running an unchanged job does not create link sprawl.
SHARE_LINK_API = f"{ORIGIN}/backend/affiliate/share-link"

TLS_PROFILE_LADDER = ("safari17_0", "firefox133", "edge101", "chrome99_android", "safari18_0")

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

SEARCH_PAGE_SIZE = 40
SEARCH_MAX_PAGES = 20  # backend hard cap -> 800 products per query

# `PRODUCT_DETAIL` is the only pageType the share-link endpoint accepts;
# SEARCH / MERCHANT / HOMEPAGE / CATEGORY / PROMO / BRAND all return 400.
SHARE_PAGE_TYPE = "PRODUCT_DETAIL"
SHARE_PLATFORM = "WEB"

SORT_OPTIONS = {
    "bestSelling": "16",
    "relevance": "0",
    "cheapest": "3",
    "mostExpensive": "4",
    "newest": "5",
}

# Blibli's `warrantyType` facet values. "Garansi Resmi" is the official
# manufacturer warranty an affiliate marketer wants to advertise.
WARRANTY_OFFICIAL = "Garansi Resmi"

# The image path carries its own size segment. `medium` and `full` and
# `thumbnail` all resolve; `large` and `small` 404.
IMAGE_SIZES = ("medium", "full", "thumbnail")
