"""Endpoints, product keys and enums for Traveloka's UGC review service.

Reviews live on a single service (`ugcReview`) shared by every Traveloka
product, keyed by `productType` + `configId`. Hotels, Xperience activities, bus
operators, airport transfers and car rentals all read the same way.

Notably, Xperience *reviews* are open even though Xperience *search* is behind an
AWS WAF CAPTCHA -- so this actor can read activity reviews from an activity URL
even though it cannot list activities.
"""

from __future__ import annotations

GET_REVIEWS = ("/v2/ugc/review/consumption/v2/getReviews", "ugcReview")
GET_AGGREGATE = ("/v2/ugc/review/consumption/v2/getReviewAggregateSummary", "ugcReview")
GET_RATING_TAGS = ("/v2/ugc/review/consumption/v2/getReviewRatingTagAggregate", "ugcReview")
GET_FILTERS = ("/v2/ugc/review/consumption/v2/getReviewFilter", "ugcReview")
GET_COUNT = ("/v2/ugc/review/consumption/v2/getReviewCount", "ugcReview")
FEATURE_CONFIG = ("/v2/content/featurecontrol/getfeatureconfigweb", "content")

REFERER_HOTEL = "hotel/detail"
REFERER_ACTIVITY = "activities"

# Traveloka publishes the productType -> configId map in its own feature control
# payload, under this key. The actor reads it live so a Traveloka-side rename
# does not silently break every run; the table below is only a fallback.
FEATURE_KEY = "review-consumption-product-key-v2"

FALLBACK_CONFIG_IDS = {
    "HOTEL_GENERAL": "REV_CONSV2_HOTEL_GENERAL_V1",
    "EXPERIENCE_GENERAL": "REV_CONSV2_EXPERIENCE_GENERAL_V1",
    "EXPERIENCE_ATTRACTIONS": "REV_CONSV2_EXPERIENCE_ATTRACTIONS_V1",
    "EXPERIENCE_TOUR": "REV_CONSV2_EXPERIENCE_TOURS_V1",
    "EXPERIENCE_EVENT": "REV_CONSV2_EXPERIENCE_EVENTS_V1",
    "EXPERIENCE_BEAUTY_AND_SPA": "REV_CONSV2_EXPERIENCE_SPA_AND_RELAXATION_V1",
    "EXPERIENCE_FOOD_AND_DRINK": "REV_CONSV2_EXPERIENCE_CULINARY_V1",
    "EXPERIENCE_PLAYGROUNDS": "REV_CONSV2_EXPERIENCE_PLAYGROUND_V1",
    "EXPERIENCE_ENTERTAINMENT": "REV_CONSV2_EXPERIENCE_ENTERTAINMENT_V1",
    "EXPERIENCE_SPORTS": "REV_CONSV2_EXPERIENCE_SPORTS_V1",
    "EXPERIENCE_TRANSPORTS": "REV_CONSV2_EXPERIENCE_TRANSPORTATIONS_V1",
    "EXPERIENCE_TRAVEL_ESSENTIALS": "REV_CONSV2_EXPERIENCE_TRAVEL_ESSENTIALS_V1",
    "EXPERIENCE_CLASSES_AND_WORKSHOPS": "REV_CONSV2_EXPERIENCE_CLASSES_AND_CULTURE_V1",
    "BUS_GENERAL": "REV_CONSV2_BUS_GENERAL_V1",
    "AIRPORT_TRANSFER_GENERAL": "REV_CONSV2_AIRPORT_TRANSFER_GENERAL_V1",
    "VEHICLE_RENTAL_WITH_DRIVER": "REV_CONSV2_CAR_RENTAL_SUMMARY_WITH_DRIVER_V1",
    "VEHICLE_RENTAL_WITHOUT_DRIVER": "REV_CONSV2_CAR_RENTAL_SUMMARY_WITHOUT_DRIVER_V1",
}

# What the user picks -> the feature-map key and the productType sent upstream.
PRODUCT_PRESETS = {
    "hotel": ("HOTEL_GENERAL", "HOTEL", REFERER_HOTEL),
    "experience": ("EXPERIENCE_GENERAL", "EXPERIENCE", REFERER_ACTIVITY),
    "experience-attraction": ("EXPERIENCE_ATTRACTIONS", "EXPERIENCE", REFERER_ACTIVITY),
    "experience-tour": ("EXPERIENCE_TOUR", "EXPERIENCE", REFERER_ACTIVITY),
    "experience-spa": ("EXPERIENCE_BEAUTY_AND_SPA", "EXPERIENCE", REFERER_ACTIVITY),
    "experience-event": ("EXPERIENCE_EVENT", "EXPERIENCE", REFERER_ACTIVITY),
    "bus": ("BUS_GENERAL", "BUS", "bus-and-shuttle"),
    "airport-transfer": ("AIRPORT_TRANSFER_GENERAL", "AIRPORT_TRANSFER", "airport-transfer"),
    "car-rental": ("VEHICLE_RENTAL_WITH_DRIVER", "VEHICLE_RENTAL", "car-rental"),
}

# `sort` MUST be a bare string. Passing {"sortType": ...} or {"selectedValue":
# ...} is accepted with HTTP 200 and then silently ignored, so an actor that
# sends an object looks like it sorted when it did not.
SORT_VALUES = (
    "SORT_CREATED_DESCENDING",
    "SORT_HELPFUL_DESCENDING",
    "SORT_RATING_DESCENDING",
    "SORT_RATING_ASCENDING",
)

RATING_FILTERS = (
    "RATING_VALUE_ALL",
    "RATING_VALUE_EXCEPTIONAL",
    "RATING_VALUE_VERY_GOOD",
    "RATING_VALUE_PLEASANT",
)
FORMAT_FILTERS = (
    "FORMAT_VALUE_ALL",
    "FORMAT_VALUE_TEXT",
    "FORMAT_VALUE_MEDIA",
    "FORMAT_VALUE_TEXT_MEDIA",
)

PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
