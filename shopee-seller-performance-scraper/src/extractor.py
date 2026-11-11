"""Flatten Shopee's 50-odd shop fields into the ones a buyer actually judges on.

The raw record is wide and inconsistent — some counts are absent rather than
zero, `response_time` is in seconds, `ctime` is a Unix timestamp, and the rating
breakdown is three separate counters. This turns it into a single comparable
row, and derives the three figures nobody wants to compute by hand: shop age,
response time in minutes, and the share of ratings that are positive.
"""

from datetime import datetime, timezone

FIELDS_PASSTHROUGH = (
    "shopid", "userid", "name", "country", "shop_location", "description",
    "is_official_shop", "is_preferred_plus_seller", "is_shopee_verified",
    "status", "place_id", "cover",
)


def _epoch(value) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return None


def _age_days(value) -> int | None:
    try:
        created = datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
    return (datetime.now(timezone.utc) - created).days


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_shop(payload: dict, domain: str) -> dict:
    data = (payload or {}).get("data") or {}

    good = _int(data.get("rating_good")) or 0
    normal = _int(data.get("rating_normal")) or 0
    bad = _int(data.get("rating_bad")) or 0
    total_ratings = good + normal + bad
    positive_share = round(good / total_ratings * 100, 2) if total_ratings else None

    response_time = _int(data.get("response_time"))
    ctime = data.get("ctime")

    username = data.get("account", {}).get("username") if isinstance(data.get("account"), dict) else None
    username = username or data.get("username")
    shop_id = _int(data.get("shopid"))

    record = {
        "shopId": shop_id,
        "username": username,
        "shopName": data.get("name"),
        "shopUrl": f"https://{domain}/shop/{shop_id}" if shop_id else None,
        "country": data.get("country"),
        "location": data.get("shop_location"),
        "description": data.get("description"),

        # Trust signals
        "isOfficialShop": bool(data.get("is_official_shop")),
        "isPreferredPlusSeller": bool(data.get("is_preferred_plus_seller")),
        "isShopeeVerified": bool(data.get("is_shopee_verified")),

        # Scale
        "followerCount": _int(data.get("follower_count")),
        "followingCount": _int(data.get("following_count")),
        "itemCount": _int(data.get("item_count")),

        # Quality
        "ratingStar": data.get("rating_star"),
        "ratingGood": good,
        "ratingNormal": normal,
        "ratingBad": bad,
        "ratingTotal": total_ratings,
        "positiveRatingPercent": positive_share,

        # Service — the metrics a supplier is actually qualified on
        "responseRate": _int(data.get("response_rate")),
        "responseTimeSeconds": response_time,
        "responseTimeMinutes": (round(response_time / 60, 1)
                                if isinstance(response_time, int) else None),

        # Age
        "createdAt": _epoch(ctime),
        "shopAgeDays": _age_days(ctime),
        "lastActiveAt": _epoch(data.get("last_active_time")),

        "_rawFieldCount": len(data),
    }

    for key in FIELDS_PASSTHROUGH:
        if key in data and key not in ("shopid", "name", "country", "shop_location",
                                       "description", "is_official_shop",
                                       "is_preferred_plus_seller", "is_shopee_verified"):
            record[key] = data[key]

    return record
