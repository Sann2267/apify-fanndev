"""Review extraction: target resolution, coverage sweeps, record shaping.

The review endpoint exposes only a ~600-review window per distinct query
(30 per page x 20 pages, and past the end it *repeats* earlier reviews
rather than returning an empty list). Slicing the same target by rating and
by topic opens additional windows, which is how a store with tens of
thousands of reviews still yields a useful, and for negative reviews often
near-complete, sample. See `sweep_plan`.
"""

import logging
import re
from datetime import datetime, timezone

from src.constants import (
    RATINGS,
    REVIEW_MAX_PAGES,
    REVIEW_PAGE_SIZE,
    REVIEWS_API,
    SEARCH_API,
    SEARCH_MAX_PAGES,
    SEARCH_PAGE_SIZE,
    TOPIC_LABELS,
    TOPICS,
    TYPE_BRAND,
    TYPE_MERCHANT,
    TYPE_PRODUCT,
)

logger = logging.getLogger(__name__)

# /merchant/<slug>/<CODE> and /p/<slug>/ps--<SKU> are the two public URL
# shapes users will paste. Codes may also be given bare.
_MERCHANT_URL = re.compile(r"/merchant/[^/]+/([A-Za-z0-9\-]+)")
_PRODUCT_URL = re.compile(r"/p/[^/]+/(?:ps|is)--([A-Za-z0-9\-]+)")
_MERCHANT_CODE = re.compile(r"^[A-Z]{2,4}-\d{4,6}$")
_PRODUCT_SKU = re.compile(r"^[A-Z]{2,4}-\d{4,6}-\d{3,6}(?:-\d+)?$")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch_ms_to_iso(value) -> str | None:
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class InvalidTarget(ValueError):
    """The input string is not a recognisable Blibli store/product/brand."""


def resolve_target(raw: str) -> dict:
    """Turn a user-supplied string into `{type, value, label}`.

    Accepts a merchant URL, a product URL, a bare merchant code
    (`COP-60023`), a bare product SKU (`COP-60023-00933`), or an explicit
    `brand:<name>` prefix. Product SKUs are checked before merchant codes
    because a SKU starts with its merchant's code.
    """
    value = str(raw or "").strip()
    if not value:
        raise InvalidTarget("empty target")

    if value.lower().startswith("brand:"):
        brand = value.split(":", 1)[1].strip()
        if not brand:
            raise InvalidTarget(f"{raw!r} has no brand name after 'brand:'")
        return {"type": TYPE_BRAND, "value": brand, "label": f"brand:{brand}"}

    if "/" in value:
        product = _PRODUCT_URL.search(value)
        if product:
            return {"type": TYPE_PRODUCT, "value": product.group(1), "label": product.group(1)}
        merchant = _MERCHANT_URL.search(value)
        if merchant:
            return {"type": TYPE_MERCHANT, "value": merchant.group(1), "label": merchant.group(1)}
        raise InvalidTarget(
            f"{raw!r} is not a Blibli store or product URL. Expected "
            "/merchant/<name>/<CODE> or /p/<name>/ps--<SKU>."
        )

    upper = value.upper()
    if _PRODUCT_SKU.match(upper):
        return {"type": TYPE_PRODUCT, "value": upper, "label": upper}
    if _MERCHANT_CODE.match(upper):
        return {"type": TYPE_MERCHANT, "value": upper, "label": upper}
    raise InvalidTarget(
        f"{raw!r} is not a recognisable Blibli identifier. Use a store URL, a product URL, "
        "a store code like COP-60023, a product SKU like COP-60023-00933, or 'brand:<name>'."
    )


def sweep_plan(coverage: str) -> list[dict]:
    """The list of query slices to walk for one target.

    Each slice is an independent ~600-review window, so more slices means
    more unique reviews. Slices deliberately overlap; the caller dedupes by
    review id.

    - `standard`  one unfiltered sweep. Fastest, up to ~600 reviews.
    - `deep`      one sweep per star rating, then the unfiltered sweep.
                  Because 1- and 2-star reviews are usually far fewer than
                  600, this captures nearly all negative feedback even on a
                  store with tens of thousands of reviews -- the point of
                  the actor.
    - `maximum`   adds a sweep per review topic (quality, price, shipping,
                  packaging, service, authenticity, other).

    The rating slices deliberately come *before* the unfiltered sweep. The
    union is identical when the run is uncapped, but under
    `maxReviewsPerTarget` it is the difference between a rating-stratified
    sample and 100+ consecutive 5-star reviews: these stores run ~98%
    positive, so an unfiltered-first plan spends a small budget almost
    entirely on praise (measured: 5 negatives in a 120-record run, versus
    the near-complete 1-2 star capture this ordering gives).
    """
    if coverage == "standard":
        return [{}]
    plan = [{"rating": r} for r in RATINGS]
    if coverage == "maximum":
        plan += [{"topics": t} for t in TOPICS]
    return plan + [{}]


async def fetch_summary(client, target: dict) -> dict:
    """Aggregate stats for a target: rating histogram and topic counts.

    This is the cheapest and most analytically dense call in the actor --
    the topic counts are Blibli's own classification of what reviewers talk
    about, i.e. the "what do people complain about" signal, over the store's
    entire review base rather than just the sampled window.
    """
    payload = await client.get_json(
        REVIEWS_API,
        params={target["type"]: target["value"], "page": "1", "itemPerPage": "1"},
        referer="/",
    )
    return payload.get("summary") or {}


def summary_record(target: dict, summary: dict, merchant_name: str | None) -> dict:
    rating = summary.get("rating") or {}
    counts = rating.get("counts") or {}
    topics = (summary.get("filters") or {}).get("topics") or []
    total = summary.get("count")

    def _int(value):
        return value if isinstance(value, (int, float)) else 0

    negative = _int(counts.get("1")) + _int(counts.get("2"))
    positive = _int(counts.get("4")) + _int(counts.get("5"))
    known = negative + positive + _int(counts.get("3"))

    return {
        "_input": target["label"],
        "_source": "S2-review-summary",
        "_scrapedAt": _now(),
        "recordType": "STORE_SUMMARY",
        "targetType": target["type"],
        "targetValue": target["value"],
        "merchantName": merchant_name,
        "totalReviews": total,
        "averageRating": rating.get("average"),
        "maxRating": summary.get("maxRating"),
        "ratingCounts": counts,
        # Share of rated reviews that are 1-2 star. The single most useful
        # number for "is this store's sentiment getting worse", and cheap to
        # compute here rather than in every downstream consumer.
        "negativeSharePercent": round(negative / known * 100, 2) if known else None,
        "positiveSharePercent": round(positive / known * 100, 2) if known else None,
        "commentCount": summary.get("commentCount"),
        # Blibli's own topic classification over the whole review base.
        "topicCounts": {t.get("name"): t.get("count") for t in topics if t.get("name")},
        "topicLabels": {
            t.get("name"): TOPIC_LABELS.get(t.get("name"), t.get("name"))
            for t in topics
            if t.get("name")
        },
    }


def _polarity(rating) -> str | None:
    """Rating-derived polarity label. Deliberately NOT sentiment analysis --
    it is a direct mapping of the star rating, so a consumer can filter to
    negative reviews before spending tokens on an actual LLM pass."""
    if not isinstance(rating, (int, float)):
        return None
    if rating <= 2:
        return "negative"
    return "neutral" if rating == 3 else "positive"


def review_record(review: dict, target: dict, slice_: dict, merchant_name: str | None) -> dict:
    product = review.get("product") or {}
    images = review.get("images") or []
    videos = review.get("videos") or []
    content = review.get("content")
    return {
        "_input": target["label"],
        "_source": "S1-public-reviews",
        "_scrapedAt": _now(),
        "recordType": "REVIEW",
        **review,
        "targetType": target["type"],
        "targetValue": target["value"],
        "merchantName": merchant_name,
        "productSku": product.get("sku"),
        # Flattened, ready for an LLM/embedding pipeline without digging.
        "reviewText": content,
        "reviewLength": len(content) if isinstance(content, str) else 0,
        "hasText": bool(content and content.strip()),
        "ratingPolarity": _polarity(review.get("rating")),
        "imageCount": len(images),
        "videoCount": len(videos),
        "hasMedia": bool(images or videos),
        "createdAtIso": _epoch_ms_to_iso(review.get("createdDate")),
        "updatedAtIso": _epoch_ms_to_iso(review.get("updatedDate")),
        # Which slice surfaced this review. When it came from a topic sweep,
        # that topic is Blibli's own classification of the review.
        "matchedTopic": slice_.get("topics"),
        "matchedRatingFilter": slice_.get("rating"),
    }


async def fetch_merchant_name(client, merchant_code: str) -> str | None:
    """Resolve a store's display name.

    There is no public merchant-metadata endpoint (every candidate path
    returns the HTML app shell), so the name is read off the store's own
    catalogue listing instead. Best-effort: a store with no listable
    products simply has no name.
    """
    try:
        payload = await client.get_json(
            SEARCH_API,
            params={
                "merchant": merchant_code, "page": "1", "start": "0", "itemPerPage": "1",
                "channelId": "web", "showFacet": "false", "sort": "0",
            },
            referer="/",
        )
    except Exception as exc:  # noqa: BLE001 - name is cosmetic, never fatal
        logger.warning("Could not resolve merchant name for %s: %s", merchant_code, exc)
        return None
    products = (payload.get("data") or {}).get("products") or []
    return products[0].get("merchantName") if products else None


async def run_target(
    client, target, coverage, sort_by, max_reviews, min_rating, with_media_only,
    merchant_name=None, only_with_text=True,
):
    """Yield deduped review records for one target across every sweep slice.

    `merchant_name` is resolved once by the caller and threaded through, so
    a store expanded into many per-product sub-targets does not re-resolve
    the same name for every SKU.
    """
    seen: set[str] = set()
    emitted = 0

    for slice_ in sweep_plan(coverage):
        if max_reviews and emitted >= max_reviews:
            return
        page = 1
        while page <= REVIEW_MAX_PAGES:
            if max_reviews and emitted >= max_reviews:
                return
            params = {
                target["type"]: target["value"],
                "page": str(page),
                "itemPerPage": str(REVIEW_PAGE_SIZE),
                "sortBy": sort_by,
                **slice_,
            }
            if with_media_only:
                params["hasMedia"] = "true"
            if only_with_text:
                # Real server-side filter (verified: with sortBy=LATEST it
                # takes text density from 4/30 to 30/30 and returns a
                # different result set). Roughly half of Blibli's reviews are
                # star-only with no words, so without this the ~600-review
                # window is mostly empty rows -- useless for sentiment work.
                # Note `withComment`/`hasContent`/`hasText`/`commentOnly` are
                # silently ignored by the API; only `hasComment` bites.
                params["hasComment"] = "true"

            payload = await client.get_json(REVIEWS_API, params=params, referer="/")
            items = payload.get("data") or []
            reviews = [r for r in items if isinstance(r, dict) and r.get("id")]
            if not reviews:
                break

            # Past the end the endpoint repeats earlier reviews instead of
            # returning an empty page, so "no new IDs" is the only reliable
            # stop condition -- an empty-page check alone never fires.
            new_reviews = [r for r in reviews if r["id"] not in seen]
            if not new_reviews:
                break

            for review in new_reviews:
                seen.add(review["id"])
                if min_rating and not (
                    isinstance(review.get("rating"), (int, float))
                    and review["rating"] >= min_rating
                ):
                    continue
                yield review_record(review, target, slice_, merchant_name)
                emitted += 1
                if max_reviews and emitted >= max_reviews:
                    return

            logger.info(
                "%s=%s slice=%s page=%d -> %d new (%d emitted, %d seen)",
                target["type"], target["value"], slice_ or "none",
                page, len(new_reviews), emitted, len(seen),
            )
            page += 1


async def fetch_store_products(client, merchant_code: str, max_products: int):
    """A store's catalogue, used by `productBreakdown`."""
    collected = []
    for page in range(1, SEARCH_MAX_PAGES + 1):
        if max_products and len(collected) >= max_products:
            break
        payload = await client.get_json(
            SEARCH_API,
            params={
                "merchant": merchant_code, "page": str(page),
                "start": str((page - 1) * SEARCH_PAGE_SIZE),
                "itemPerPage": str(SEARCH_PAGE_SIZE),
                "channelId": "web", "showFacet": "false", "sort": "0",
            },
            referer="/",
        )
        data = payload.get("data") or {}
        products = data.get("products") or []
        if not products:
            break
        for product in products:
            if isinstance(product, dict) and product.get("sku"):
                collected.append(product)
                if max_products and len(collected) >= max_products:
                    break
        paging = data.get("paging") or {}
        if paging.get("total_page") and page >= paging["total_page"]:
            break
    return collected
