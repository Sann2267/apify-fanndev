"""The five scraping modes, and the chaining that joins them.

Every mode is an async generator of dataset records so that `main` can stream
results and stop the moment the item budget is spent, rather than assembling a
list and discovering afterwards that it overshot.

The modes are deliberately built on four surfaces and no others, because those
are the four that Etsy's robots.txt allows *and* DataDome serves to an
HTTP-only client:

    /c/<category>?page=N                 64 product cards per page, to page 250
    /search/shops?q=<kw>&page=N          12 shop cards per page, keyword-filtered
    /<locale>/shop/<name>[?search_query=] the shop, its stats and its catalogue
    /<locale>/shop/<name>/reviews?page=N  14 reviews per page, with the item
    /listing/<id>/<exact-slug>           the full product record

Keyword product search therefore runs keyword -> shops -> each shop's own
catalogue search, which is the only route to keyword-matched products that
does not go through the disallowed `/search?q=`. It costs one request per shop
instead of one per result page, and it returns products that genuinely match:
on a verification run, 35 of 36 cards returned for `search_query=ring` had
"ring" in the title, against a visibly different unfiltered catalogue.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any, AsyncIterator, Callable

from .client import EtsyBlocked, EtsyChallengeWall, EtsyClient, EtsyNotFound
from .constants import (
    CATEGORY_MAX_PAGE,
    EMPTY_PAGE_TOLERANCE,
    SHOP_LOCALE_DEFAULT,
    SITE_ROOT,
)
from .parsers import (
    error_record,
    has_next_page,
    listing_id_from_url,
    parse_grid,
    parse_product_detail,
    parse_review_sentiment,
    parse_reviews,
    parse_shop_profile,
    parse_shop_search,
    record,
    shop_name_from_url,
    strip_tracking,
)

log = logging.getLogger("etsy.modes")

LOCALE_PATH_RE = re.compile(
    r"^https?://(?:www\.)?etsy\.com/(?:([a-z]{2}(?:-[a-z]{2})?)/)?(.*)$", re.I
)
KNOWN_LOCALES = {
    "uk", "au", "ca", "de", "de-en", "dk-en", "fi-en", "hk-en", "ie", "il-en",
    "in-en", "no-en", "nz", "se-en", "sg-en", "es", "mx", "us-es", "at", "ch",
    "fr", "ca-fr", "it", "nl", "be", "jp", "pl", "pt", "se",
}


class Budget:
    """A shared item ceiling.

    Held by the run rather than by each mode so that a chained crawl cannot
    spend the user's `maxItems` several times over -- the whole point of
    `deepCrawl` is that one number bounds the entire job.
    """

    def __init__(self, max_items: int) -> None:
        self.max_items = max_items if max_items and max_items > 0 else 0
        self.used = 0

    @property
    def exhausted(self) -> bool:
        return bool(self.max_items) and self.used >= self.max_items

    def take(self) -> bool:
        if self.exhausted:
            return False
        self.used += 1
        return True


# -- URL handling ----------------------------------------------------------


def split_locale(url: str) -> tuple[str, str]:
    """Return (locale, rest-of-path) for an Etsy URL, locale possibly ""."""
    m = LOCALE_PATH_RE.match(url.strip())
    if not m:
        return "", url
    candidate, rest = m.group(1) or "", m.group(2) or ""
    if candidate and candidate.lower() not in KNOWN_LOCALES:
        # Not a locale at all -- "/c/..." and "/shop/..." both start with a
        # two-letter-ish segment, so the whitelist is what keeps this from
        # eating the real first path segment.
        return "", f"{candidate}/{rest}" if rest else candidate
    return candidate.lower(), rest


def with_locale(url: str, locale: str) -> str:
    """Rewrite an Etsy URL to carry `locale` as its path prefix."""
    _, rest = split_locale(url)
    prefix = f"/{locale}" if locale else ""
    return f"{SITE_ROOT}{prefix}/{rest.lstrip('/')}"


def shop_url(shop_name: str, locale: str, *, suffix: str = "") -> str:
    """Build a shop URL that DataDome will actually serve.

    The locale prefix is not cosmetic here: the bare `/shop/<name>` path draws
    the interstitial from every IP and TLS profile tried, while the prefixed
    form is served. A caller that asked for the unprefixed site still gets a
    prefix on shop URLs, because the alternative is a guaranteed block.
    """
    prefix = locale or SHOP_LOCALE_DEFAULT
    return f"{SITE_ROOT}/{prefix}/shop/{shop_name}{suffix}"


def classify(url: str) -> str:
    _, rest = split_locale(url)
    path = "/" + rest.split("?", 1)[0].strip("/")
    if path.startswith("/listing/"):
        return "listing"
    if path.startswith("/shop/"):
        return "shopReviews" if path.rstrip("/").endswith("/reviews") else "shop"
    if path.startswith("/search/shops"):
        return "shopSearch"
    if path.startswith("/c"):
        return "category"
    if path.startswith("/market/"):
        return "market"
    return "unknown"


def keyword_to_shop_search(keyword: str, locale: str, page: int) -> str:
    prefix = f"/{locale}" if locale else ""
    q = urllib.parse.quote_plus(keyword)
    return f"{SITE_ROOT}{prefix}/search/shops?q={q}&page={page}"


# -- filtering -------------------------------------------------------------


def make_card_filter(options: dict[str, Any]) -> Callable[[dict[str, Any]], bool]:
    """Build the product-card predicate from the run's options.

    `bestsellerOnly` is intentionally strict. Etsy does not render the
    Bestseller or Star Seller badge into grid HTML at all right now -- the
    page's own listing-card config says `badges_disabled: true` and the
    `quality_signals.bestseller_logic_desktop` experiment is `off` -- so a
    filter that quietly substituted a popularity heuristic would return rows
    the user would reasonably read as badged when they are not. It filters on
    the badge, and `main` warns at startup that `minReviewCount` / `minRating`
    are the signals that actually work on this surface today.

    Those two read `shopReviewCount` and `shopRating`, because that is what a
    grid card carries: the stars on a card describe the seller, not the item
    (see `parse_listing_cards`). They are a seller-quality filter, which is
    the closest thing a grid offers to the badge this cannot reproduce.
    """
    bestseller_only = bool(options.get("bestsellerOnly"))
    include_ads = bool(options.get("includeAds"))
    min_reviews = options.get("minReviewCount") or 0
    min_rating = options.get("minRating") or 0

    def keep(card: dict[str, Any]) -> bool:
        if not include_ads and card.get("isAd"):
            return False
        if bestseller_only and not (card.get("isBestseller") or card.get("isStarSeller")):
            return False
        if min_reviews and (card.get("shopReviewCount") or 0) < min_reviews:
            return False
        if min_rating and (card.get("shopRating") or 0) < min_rating:
            return False
        return True

    return keep


# -- paging ----------------------------------------------------------------


async def _paginate_cards(
    client: EtsyClient,
    base_url: str,
    *,
    max_pages: int,
    mode: str,
    keyword: str | None,
    budget: Budget,
    keep: Callable[[dict[str, Any]], bool],
    locale: str,
    parent_id: str | None = None,
    hard_page_cap: int = CATEGORY_MAX_PAGE,
) -> AsyncIterator[dict[str, Any]]:
    """Walk a grid page by page, emitting search_result records."""
    seen: set[str] = set()
    empty_streak = 0
    rank = 0

    for page in range(1, min(max_pages, hard_page_cap) + 1):
        if budget.exhausted:
            return
        url = base_url if page == 1 else _with_page(base_url, page)
        try:
            final_url, html = await client.get_page(url)
        except EtsyChallengeWall as exc:
            yield error_record(url, "challenge_wall", str(exc), mode=mode)
            return
        except EtsyNotFound as exc:
            yield error_record(url, "not_found", str(exc), mode=mode)
            return
        except (EtsyBlocked, Exception) as exc:  # noqa: BLE001
            yield error_record(url, "fetch_failed", f"{type(exc).__name__}: {exc}", mode=mode)
            return

        cards = parse_grid(html)
        if not cards:
            empty_streak += 1
            # An empty grid is not proof of exhaustion on Etsy: during recon
            # page 25 of a category came back empty while pages 50, 100 and
            # 250 were full. Only a run of empties ends the walk.
            if empty_streak > EMPTY_PAGE_TOLERANCE:
                log.info("Stopping %s after %d empty pages", base_url, empty_streak)
                return
            continue
        empty_streak = 0

        emitted_this_page = 0
        for card in cards:
            lid = card.get("listingId")
            if not lid or lid in seen:
                continue
            seen.add(lid)
            rank += 1
            if not keep(card):
                continue
            if not budget.take():
                return
            emitted_this_page += 1
            yield record(
                "search_result",
                lid,
                card,
                source_url=final_url,
                mode=mode,
                keyword=keyword,
                rank=rank,
                page=page,
                parent_id=parent_id,
                locale=locale,
            )
        log.info(
            "%s page %d: %d cards, %d kept (%d/%s items used)",
            base_url, page, len(cards), emitted_this_page,
            budget.used, budget.max_items or "unlimited",
        )

        if not has_next_page(html, page):
            return


def _with_page(url: str, page: int) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}page={page}"


# -- mode: search ----------------------------------------------------------


async def mode_search(
    client: EtsyClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    locale = options["locale"]
    keep = make_card_filter(options)
    max_pages = int(options.get("maxPagesPerTarget") or 5)
    shops_per_keyword = int(options.get("shopsPerKeyword") or 12)

    for url in options.get("startUrls") or []:
        kind = classify(url)
        if kind == "category":
            async for rec in _paginate_cards(
                client, with_locale(url, locale), max_pages=max_pages, mode="search",
                keyword=None, budget=budget, keep=keep, locale=locale,
            ):
                yield rec
        elif kind == "shopSearch":
            async for rec in _shop_search_pages(
                client, url, keyword=None, options=options, budget=budget, locale=locale
            ):
                yield rec
        elif kind in ("shop", "listing"):
            # A shop or product URL in search mode is still a sensible thing
            # for a user to paste, so route it rather than reject it.
            async for rec in (
                mode_shop(client, {**options, "startUrls": [url]}, budget)
                if kind == "shop"
                else mode_product(client, {**options, "startUrls": [url]}, budget)
            ):
                yield rec
        else:
            yield error_record(
                url,
                "unsupported_url",
                f"{url!r} is not a surface this actor can read. Search mode takes "
                f"category URLs (https://www.etsy.com/c/...) and shop-search URLs "
                f"(https://www.etsy.com/search/shops?q=...). Etsy's robots.txt "
                f"disallows /search?q= product search for every crawler.",
                mode="search",
            )
        if budget.exhausted:
            return

    for keyword in options.get("searchKeywords") or []:
        # Shop and products are interleaved on purpose. Emitting every matched
        # shop first would let a full page of 12 shop rows swallow a small
        # maxItems before a single product was reached -- and products are
        # what a keyword search is for.
        searched = 0
        async for rec in _shop_search_pages(
            client, None, keyword=keyword, options=options, budget=budget, locale=locale
        ):
            yield rec
            if budget.exhausted:
                return
            if rec.get("item_type") != "shop_result" or searched >= shops_per_keyword:
                continue
            name = (rec.get("data") or {}).get("shopName")
            if not name:
                continue
            searched += 1
            # Keyword -> products, through this shop's own catalogue search:
            # the only route to keyword-matched listings that does not go
            # through the disallowed /search?q=.
            target = shop_url(name, locale) + "?search_query=" + urllib.parse.quote_plus(keyword)
            async for prod in _paginate_cards(
                client, target, max_pages=max_pages, mode="search", keyword=keyword,
                budget=budget, keep=keep, locale=locale, parent_id=name,
            ):
                yield prod
            if budget.exhausted:
                return


async def _shop_search_pages(
    client: EtsyClient,
    url: str | None,
    *,
    keyword: str | None,
    options: dict[str, Any],
    budget: Budget,
    locale: str,
) -> AsyncIterator[dict[str, Any]]:
    """Walk /search/shops, emitting shop_result records."""
    max_pages = int(options.get("maxPagesPerTarget") or 5)
    if keyword is None and url:
        parsed = urllib.parse.urlparse(url)
        keyword = urllib.parse.parse_qs(parsed.query).get("q", [None])[0]

    rank = 0
    for page in range(1, max_pages + 1):
        if budget.exhausted:
            return
        target = (
            keyword_to_shop_search(keyword, locale, page)
            if keyword
            else _with_page(with_locale(url or "", locale), page)
        )
        try:
            final_url, html = await client.get_page(target)
        except EtsyChallengeWall as exc:
            yield error_record(target, "challenge_wall", str(exc), mode="search")
            return
        except Exception as exc:  # noqa: BLE001
            yield error_record(target, "fetch_failed", f"{type(exc).__name__}: {exc}", mode="search")
            return

        shops = parse_shop_search(html)
        if not shops:
            # Unlike the product grid, an empty shop search IS conclusive: a
            # nonsense keyword returns zero cards on page 1 and Etsy does not
            # shard this surface.
            log.info("Shop search %r exhausted at page %d", keyword, page)
            return

        for shop in shops:
            rank += 1
            if not budget.take():
                return
            yield record(
                "shop_result",
                shop.get("shopName"),
                shop,
                source_url=final_url,
                mode="search",
                keyword=keyword,
                rank=rank,
                page=page,
                locale=locale,
            )


# -- mode: shop ------------------------------------------------------------


async def mode_shop(
    client: EtsyClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    locale = options["locale"]
    keep = make_card_filter(options)
    max_pages = int(options.get("maxPagesPerTarget") or 5)

    for raw in _shop_targets(options):
        if budget.exhausted:
            return
        name = shop_name_from_url(raw) or raw.strip().strip("/")
        target = shop_url(name, locale)
        try:
            final_url, html = await client.get_page(target)
        except EtsyChallengeWall as exc:
            yield error_record(target, "challenge_wall", str(exc), mode="shop")
            continue
        except EtsyNotFound as exc:
            yield error_record(target, "not_found", str(exc), mode="shop")
            continue
        except Exception as exc:  # noqa: BLE001
            yield error_record(target, "fetch_failed", f"{type(exc).__name__}: {exc}", mode="shop")
            continue

        profile = parse_shop_profile(html, final_url)
        if budget.take():
            yield record(
                "shop_profile", name, profile, source_url=final_url,
                mode="shop", locale=locale,
            )

        # Page 1's catalogue comes from the JSON-LD ItemList merged with the
        # card markup, so it carries both the ISO currency code and the ad
        # flag. Some shop layouts mix recommendation carousels into the same
        # grid, so anything belonging to a different shop is dropped -- a
        # foreign listing silently attributed to this seller would be worse
        # than a missing one.
        shop_id = profile.get("shopId")
        first_page = _own_listings(parse_grid(html), shop_id, name)
        seen: set[str] = set()
        rank = 0
        for item in first_page:
            lid = item.get("listingId")
            if not lid or lid in seen:
                continue
            seen.add(lid)
            rank += 1
            if not keep(item):
                continue
            if not budget.take():
                return
            # Etsy renders its own "Featured items" strip without a seller
            # name, because on a shop page it is redundant. Downstream it is
            # not, so the shop is filled in -- both the name and the link.
            if not item.get("shopName"):
                item["shopName"] = name
                item["shopUrl"] = item.get("shopUrl") or shop_url(name, locale)
            yield record(
                "search_result", lid, item, source_url=final_url, mode="shop",
                rank=rank, page=1, parent_id=name, locale=locale,
            )

        if max_pages > 1 and not budget.exhausted:
            async for rec in _paginate_shop_rest(
                client, target, seen=seen, start_rank=rank, max_pages=max_pages,
                budget=budget, keep=keep, locale=locale, shop_name=name,
                shop_id=shop_id,
            ):
                yield rec

        if options.get("extractReviews") and not budget.exhausted:
            async for rec in _shop_reviews(
                client, name, options=options, budget=budget, locale=locale
            ):
                yield rec


async def _paginate_shop_rest(
    client: EtsyClient,
    base_url: str,
    *,
    seen: set[str],
    start_rank: int,
    max_pages: int,
    budget: Budget,
    keep: Callable[[dict[str, Any]], bool],
    locale: str,
    shop_name: str,
    shop_id: str | None,
) -> AsyncIterator[dict[str, Any]]:
    rank = start_rank
    empty_streak = 0
    for page in range(2, max_pages + 1):
        if budget.exhausted:
            return
        url = _with_page(base_url, page)
        try:
            final_url, html = await client.get_page(url)
        except EtsyChallengeWall as exc:
            yield error_record(url, "challenge_wall", str(exc), mode="shop")
            return
        except Exception as exc:  # noqa: BLE001
            yield error_record(url, "fetch_failed", f"{type(exc).__name__}: {exc}", mode="shop")
            return

        cards = _own_listings(parse_grid(html), shop_id, shop_name)
        fresh = [c for c in cards if c.get("listingId") and c["listingId"] not in seen]
        if not fresh:
            empty_streak += 1
            if empty_streak > EMPTY_PAGE_TOLERANCE:
                return
            continue
        empty_streak = 0
        for item in fresh:
            seen.add(item["listingId"])
            rank += 1
            if not keep(item):
                continue
            if not budget.take():
                return
            if not item.get("shopName"):
                item["shopName"] = shop_name
                item["shopUrl"] = item.get("shopUrl") or shop_url(shop_name, locale)
            yield record(
                "search_result", item["listingId"], item, source_url=final_url,
                mode="shop", rank=rank, page=page, parent_id=shop_name, locale=locale,
            )


def _own_listings(
    items: list[dict[str, Any]], shop_id: str | None, shop_name: str
) -> list[dict[str, Any]]:
    """Keep only the listings that belong to the shop being scraped.

    A shop page's grid can include recommendation cards from other sellers.
    The numeric shop id on each card is the reliable discriminator; when a
    card carries neither an id nor a seller name -- which is how Etsy renders
    a shop's own "Featured items" strip -- it is kept, because on a shop page
    the unattributed card is that shop's.
    """
    if not shop_id:
        return items
    kept = []
    for item in items:
        card_shop = item.get("shopId")
        card_name = item.get("shopName")
        if card_shop and str(card_shop) != str(shop_id):
            continue
        if card_name and card_name != shop_name:
            continue
        kept.append(item)
    return kept


def _shop_targets(options: dict[str, Any]) -> list[str]:
    out = [u for u in (options.get("startUrls") or []) if classify(u) in ("shop", "shopReviews")]
    out += [s for s in (options.get("shopNames") or []) if s]
    return out


# -- mode: product ---------------------------------------------------------


async def mode_product(
    client: EtsyClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    locale = options["locale"]
    for url in _listing_targets(options):
        if budget.exhausted:
            return
        async for rec in _one_product(client, url, options, budget, locale):
            yield rec


async def _one_product(
    client: EtsyClient,
    url: str,
    options: dict[str, Any],
    budget: Budget,
    locale: str,
    *,
    parent_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    if not re.search(r"/listing/\d+/[a-z0-9\-]+", url, re.I):
        yield error_record(
            url,
            "unresolvable_listing",
            "A product URL must carry the exact slug, e.g. "
            "https://www.etsy.com/listing/4306368113/birth-flower-ring-925-sterling-silver. "
            "A bare listing ID cannot be used: Etsy answers /listing/<id> and any "
            "wrong slug with a 301, and DataDome blocks the redirect, so the "
            "canonical URL cannot be discovered from the ID alone. Take the url "
            "field of any search_result or shop catalogue record instead.",
            mode="product",
        )
        return

    target = with_locale(url, locale) if locale else strip_tracking(url) or url
    try:
        final_url, html = await client.get_page(target)
    except EtsyChallengeWall as exc:
        yield error_record(target, "challenge_wall", str(exc), mode="product")
        return
    except EtsyNotFound as exc:
        yield error_record(target, "not_found", str(exc), mode="product")
        return
    except Exception as exc:  # noqa: BLE001
        yield error_record(target, "fetch_failed", f"{type(exc).__name__}: {exc}", mode="product")
        return

    detail = parse_product_detail(html, final_url)
    sentiment = parse_review_sentiment(html)
    if sentiment:
        detail["reviewSentiment"] = sentiment
    listing_id = detail.get("listingId") or listing_id_from_url(final_url)

    if budget.take():
        yield record(
            "product_detail", listing_id, detail, source_url=final_url,
            mode="product", parent_id=parent_id, locale=locale,
        )

    if options.get("extractReviews"):
        inline = parse_reviews(html, source_url=final_url)
        for rev in inline:
            if budget.exhausted:
                return
            rev["purchasedListingId"] = rev.get("purchasedListingId") or listing_id
            rev["purchasedListingUrl"] = rev.get("purchasedListingUrl") or strip_tracking(final_url)
            if not budget.take():
                return
            yield record(
                "review", rev.get("reviewId"), rev, source_url=final_url,
                mode="product", parent_id=listing_id, locale=locale,
            )

        # A listing page is not guaranteed to render its reviews: some
        # variants ship an empty reviews component and fetch the contents from
        # /api/, which robots.txt disallows. A product can honestly report
        # hundreds of reviews and show none. The shop's own reviews pages name
        # the item each review was left for, so they are the way to reach them
        # -- at one request per 14 reviews, which is why it is opt-in.
        if not inline and detail.get("reviewCount"):
            shop = detail.get("shopName")
            if options.get("deepReviews") and shop and listing_id:
                log.info(
                    "Listing %s reports %s reviews but renders none; reading "
                    "them from shop %s instead.",
                    listing_id, detail.get("reviewCount"), shop,
                )
                async for rev_rec in _shop_reviews(
                    client, shop, options=options, budget=budget, locale=locale,
                    only_listing_id=listing_id,
                ):
                    yield rev_rec
            else:
                log.info(
                    "Listing %s reports %s reviews but renders none inline. "
                    "Turn on deepReviews to read them from the shop's reviews "
                    "pages instead.",
                    listing_id, detail.get("reviewCount"),
                )


def _listing_targets(options: dict[str, Any]) -> list[str]:
    out = [u for u in (options.get("startUrls") or []) if classify(u) == "listing"]
    out += [u for u in (options.get("productUrls") or []) if u]
    return out


# -- mode: reviews ---------------------------------------------------------


async def mode_reviews(
    client: EtsyClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """Reviews for products and for whole shops.

    Etsy renders only the first handful of a listing's reviews into the page;
    the rest arrive from `/api/`, which robots.txt disallows. The deep surface
    is the shop's own reviews pages, 14 per page, and every review there names
    the item it was left for -- so reviews for one product are collected by
    walking its shop and keeping the matching `purchasedListingId`.
    """
    locale = options["locale"]
    listing_targets = _listing_targets(options)
    shop_targets = _shop_targets(options)

    for url in listing_targets:
        if budget.exhausted:
            return
        listing_id = listing_id_from_url(url)
        shop_of_listing: str | None = None
        # deepReviews is handled below for this mode, so it is switched off for
        # the inner call -- otherwise a listing that renders no reviews would
        # walk its shop twice.
        async for rec in _one_product(
            client, url, {**options, "extractReviews": True, "deepReviews": False},
            budget, locale,
        ):
            kind = rec.get("item_type")
            data = rec.get("data") or {}
            if kind == "product_detail":
                # The product record is the only place the shop name appears,
                # and deep review collection needs it to know which shop to
                # walk, so it is captured here rather than re-fetched.
                shop_of_listing = data.get("shopName")
                listing_id = data.get("listingId") or listing_id
                sentiment = data.get("reviewSentiment")
                if sentiment and budget.take():
                    yield record(
                        "review_sentiment", listing_id, sentiment,
                        source_url=rec["metadata"]["sourceUrl"], mode="reviews",
                        parent_id=listing_id, locale=locale,
                    )
            else:
                # Reviews and diagnostics pass straight through; the product
                # record itself is not what this mode is asked for.
                yield rec

        if options.get("deepReviews") and listing_id and shop_of_listing and not budget.exhausted:
            async for r in _shop_reviews(
                client, shop_of_listing, options=options, budget=budget, locale=locale,
                only_listing_id=listing_id,
            ):
                yield r

    for raw in shop_targets:
        if budget.exhausted:
            return
        name = shop_name_from_url(raw) or raw.strip().strip("/")
        async for rec in _shop_reviews(
            client, name, options=options, budget=budget, locale=locale
        ):
            yield rec


async def _shop_reviews(
    client: EtsyClient,
    shop_name: str,
    *,
    options: dict[str, Any],
    budget: Budget,
    locale: str,
    only_listing_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    max_pages = int(options.get("maxReviewPages") or options.get("maxPagesPerTarget") or 5)
    base = shop_url(shop_name, locale, suffix="/reviews")
    empty_streak = 0

    for page in range(1, max_pages + 1):
        if budget.exhausted:
            return
        url = base if page == 1 else _with_page(base, page)
        try:
            final_url, html = await client.get_page(url)
        except EtsyChallengeWall as exc:
            yield error_record(url, "challenge_wall", str(exc), mode="reviews")
            return
        except EtsyNotFound as exc:
            yield error_record(url, "not_found", str(exc), mode="reviews")
            return
        except Exception as exc:  # noqa: BLE001
            yield error_record(url, "fetch_failed", f"{type(exc).__name__}: {exc}", mode="reviews")
            return

        reviews = parse_reviews(html, source_url=final_url)
        if not reviews:
            empty_streak += 1
            if empty_streak > EMPTY_PAGE_TOLERANCE:
                return
            continue
        empty_streak = 0

        for rev in reviews:
            if only_listing_id and rev.get("purchasedListingId") != only_listing_id:
                continue
            if not budget.take():
                return
            yield record(
                "review", rev.get("reviewId"), rev, source_url=final_url,
                mode="reviews", page=page,
                parent_id=rev.get("purchasedListingId") or shop_name, locale=locale,
            )


# -- mode: deepCrawl -------------------------------------------------------


async def mode_deep_crawl(
    client: EtsyClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """Search, then follow every product found into its full record.

    The chain is the reason this actor exists as one thing rather than four:
    the URLs it follows carry the exact slug that a product page needs, which
    a user starting from a listing ID alone cannot reconstruct.
    """
    locale = options["locale"]
    deep_limit = int(options.get("deepCrawlProducts") or 10)
    # The discovery pass must not eat the whole budget, or there would be
    # nothing left to spend on the detail pages it exists to feed.
    discovery_budget = Budget(
        max(1, int(budget.max_items * 0.5)) if budget.max_items else 0
    )

    found: list[tuple[str, str | None]] = []
    async for rec in mode_search(client, options, discovery_budget):
        budget.used += 1
        yield rec
        if rec.get("item_type") == "search_result":
            url = (rec.get("data") or {}).get("url")
            if url:
                found.append((url, (rec.get("data") or {}).get("shopName")))
        if budget.exhausted:
            return

    log.info(
        "Deep crawl: %d products discovered, following the first %d",
        len(found), min(deep_limit, len(found)),
    )

    seen: set[str] = set()
    followed = 0
    for url, shop in found:
        if budget.exhausted or followed >= deep_limit:
            break
        lid = listing_id_from_url(url)
        if lid and lid in seen:
            continue
        if lid:
            seen.add(lid)
        followed += 1
        async for rec in _one_product(
            client, url, {**options, "extractReviews": True}, budget, locale,
            parent_id=shop,
        ):
            yield rec


# -- registry --------------------------------------------------------------

MODES: dict[str, Callable[..., AsyncIterator[dict[str, Any]]]] = {
    "search": mode_search,
    "shop": mode_shop,
    "product": mode_product,
    "reviews": mode_reviews,
    "deepCrawl": mode_deep_crawl,
}

# What each mode needs at least one of, checked before any request is made so
# a misconfigured run fails loudly instead of finishing green and empty.
MODE_REQUIRED_INPUT: dict[str, tuple[str, ...]] = {
    "search": ("startUrls", "searchKeywords"),
    "shop": ("startUrls", "shopNames"),
    "product": ("startUrls", "productUrls"),
    "reviews": ("startUrls", "productUrls", "shopNames"),
    "deepCrawl": ("startUrls", "searchKeywords"),
}


def normalise_locale(raw: str | None) -> str:
    value = (raw or "").strip().strip("/").lower()
    if value in ("", "us", "en-us", "default"):
        return ""
    return value if value in KNOWN_LOCALES else ""
