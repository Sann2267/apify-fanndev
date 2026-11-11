"""Endpoint map, enums and sitemap locations for the Traveloka hotel surface.

Every path/domain pair here was verified live. The `accomSearch` search list
(`/v2/hotel/searchList`) and the dynamic room-rate endpoints are deliberately
missing: they answer `x-amzn-waf-action: captcha`, which no headless client can
satisfy. The price calendar below carries the nightly rates instead, and it
covers a whole month per request rather than a single stay date.
"""

from __future__ import annotations

# -- endpoints ----------------------------------------------------------

AUTOCOMPLETE = ("/v1/hotel/autocomplete", "accomContent")
HOTEL_DETAIL = ("/v2/hotel/search/detail", "accomSearch")
ROOMS_STATIC = ("/v2/hotel/search/rooms/static", "accomRoom")
PRICE_CALENDAR = ("/v2/hotel/calendar/hotel", "accomSearch")
HOTEL_ASSETS = ("/v2/node/hotel/assets", "accomContent")
REVIEW_SUMMARY = ("/v2/ugc/review/consumption/v2/getReviewAggregateSummary", "ugcReview")

REFERER_SEARCH = "hotel/search"
REFERER_DETAIL = "hotel/detail"

# -- request enums ------------------------------------------------------

CC_GUARANTEE_OPTIONS = {
    "ccInfoPreferences": ["CC_TOKEN", "CC_FULL_INFO"],
    "ccGuaranteeRequirementOptions": ["CC_GUARANTEE"],
}
# Calendar uses the short form; sending the long one yields an empty month.
CC_GUARANTEE_OPTIONS_CALENDAR = {
    "ccInfoPreferences": ["CC_TOKEN"],
    "ccGuaranteeRequirementOptions": ["CC_GUARANTEE"],
}
RATE_TYPES = ["PAY_NOW", "PAY_AT_PROPERTY"]

# `configId` for the UGC review service, read from Traveloka's own feature
# control map (`review-consumption-product-key-v2` -> `HOTEL_GENERAL`).
REVIEW_CONFIG_ID = "REV_CONSV2_HOTEL_GENERAL_V1"
REVIEW_PRODUCT_TYPE = "HOTEL"

# -- sitemaps -----------------------------------------------------------

SITEMAP_INDEX = "https://www.traveloka.com/id-id/sitemap/index/hotel-detail.xml.gz"
# robots.txt allows /*/sitemap/** and the /id-id/ locale; it disallows /api/.
SITEMAP_TIMEOUT = 90

# Autocomplete row groups, in the order we prefer them when resolving a query.
AUTOCOMPLETE_GROUPS = (
    "hotelContent",
    "geoRegionContent",
    "geoCityContent",
    "geoAreaContent",
    "landmarkContent",
    "geoCountryContent",
    "autoCompleteContent",
)
HOTEL_ROW_TYPES = {"HOTEL", "ACCOMMODATION"}

MAX_CALENDAR_MONTHS = 12
DEFAULT_IMAGE_TYPE = "MEDIUM_THUMBNAIL_V3"
