"""Endpoints, headers and tuning constants for the Instagram profile scraper.

Scope note -- read this before extending the actor
--------------------------------------------------
This actor does **not** scrape an Instagram "Shop". Verified anonymously on
2026-09-01: Instagram Shop / product-catalog data is not present on any
public surface. `/<user>/shop/` and `/explore/shop/` redirect to
`/accounts/login/`, five major retail accounts carried zero
`shopping`/`catalog`/`merchant`/`storefront` fields, `product_type` on posts
is only ever `clips`/`igtv` (a media type, not a product), and there is no
`edge_media_to_tagged_product` -- only `edge_media_to_tagged_user`. Meta wound
Instagram Shopping down. See CRAWLING_METHOD.md for the full evidence.

What this actor does instead is extract the merchant's **public business
profile and bio links** -- and for a merchant the bio link *is* the shop
(Linktree, Shopee, Tokopedia, WhatsApp, own webstore).

Access profile
--------------
Instagram serves anonymous requests, but unevenly:

* The profile **HTML page** worked for every account tested (818-853 KB) and
  embeds the profile JSON in `<script type="application/json">` blocks.
* The `web_profile_info` **API** is richer -- it is the only source of the
  business address/contact fields and of recent posts -- but it returned an
  empty payload for some accounts in the same session where the page
  succeeded. It is therefore the preferred strategy, not the only one.

Hence a three-strategy ladder (S1 API -> S2 HTML -> S3 og-meta) rather than
trusting any single source. Anonymous access is also rate-limited, so
residential proxy rotation is strongly recommended for more than a handful
of profiles.
"""

ORIGIN = "https://www.instagram.com"

PROFILE_PAGE = f"{ORIGIN}/{{username}}/"
# Public web API used by instagram.com itself. Requires the web app id header.
PROFILE_API = f"{ORIGIN}/api/v1/users/web_profile_info/"

# Instagram's public web application ID. Not a secret and not account-bound;
# it is the same constant the logged-out web client sends.
IG_APP_ID = "936619743392459"

TLS_PROFILE_LADDER = ("chrome124", "safari17_0", "firefox133", "edge101", "chrome99_android")

PAGE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

API_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "X-IG-App-ID": IG_APP_ID,
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

MAX_RETRIES = 5
RETRY_DELAY_BASE = 2.0
REQUEST_TIMEOUT = 45

# Instagram throttles anonymous traffic hard; a pause between profiles keeps
# a run alive far longer than hammering it does.
DEFAULT_DELAY_SECONDS = 1.5

SOURCE_API = "S1-web-profile-info"
SOURCE_HTML = "S2-profile-html"
SOURCE_META = "S3-og-meta"
SOURCE_NONE = "none"

# Marketplaces and contact channels an Indonesian/SEA merchant actually
# links to. Used to classify each bio link so a consumer can jump straight
# to "where does this seller actually sell".
LINK_PLATFORMS = {
    "shopee": "SHOPEE",
    "tokopedia": "TOKOPEDIA",
    "blibli": "BLIBLI",
    "lazada": "LAZADA",
    "bukalapak": "BUKALAPAK",
    "tiktok": "TIKTOK",
    "wa.me": "WHATSAPP",
    "whatsapp": "WHATSAPP",
    "api.whatsapp": "WHATSAPP",
    "linktr.ee": "LINK_AGGREGATOR",
    "linktree": "LINK_AGGREGATOR",
    "lynk.id": "LINK_AGGREGATOR",
    "beacons.ai": "LINK_AGGREGATOR",
    "bio.link": "LINK_AGGREGATOR",
    "campsite.bio": "LINK_AGGREGATOR",
    "taplink": "LINK_AGGREGATOR",
    "shopify": "SHOPIFY",
    "facebook.com": "FACEBOOK",
    "youtube.com": "YOUTUBE",
    "t.me": "TELEGRAM",
}
