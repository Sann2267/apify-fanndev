"""The twelve extraction modes and the paging they share.

One actor rather than twelve
----------------------------
Every surface here sits behind one gate, on one host, under one header set, and
returns the same product object. Splitting them would mean twelve copies of the
AES gate -- and twelve things to fix on the day Alfagift rotates the
passphrase. They also chain constantly: a category yields ids the category mode
reads, a banner yields the promotion id the promo mode reads, a search result
yields the productIds the detail mode reads. So this follows the portfolio's
single-actor-many-modes pattern, with `item_type` on every row as the
discriminator.

Paging
------
`start` is a 0-BASED PAGE INDEX, not an item offset. `start=1&limit=50` is rows
50-99. Reading it as an offset silently re-fetches page 0 on every iteration,
which is the single easiest way to get a plausible-looking but wrong dataset
out of this API.

There is no page-size cap -- limit=5000 returned all 2072 rows of the largest
category in one response -- so `_paged` asks for one big page first and only
loops when the server says there is more. Most runs make exactly one request
per target.

Walking past the end returns HTTP 200 with an empty `products` array and
`currentPage` reset to 0. That silent-empty is the stop condition; there is no
404 and no `hasMore` flag to read.

Poisoned pages
--------------
One thing makes the big-page default fragile, and it is worth stating plainly
because it silently loses a tenth of the catalogue otherwise. Some category
listings contain a record the gateway cannot serialise, and asking for a page
that spans it returns HTTP 500 -- deterministically, on every attempt, from
every address and page size, while a neighbouring category answers the very
same request fine. At recon time the whole "Lifestyle" top-level category
(1008 products) answered 500 at every page size, yet paging it at limit=100
returned 866 of those rows: only page 0 was poisoned.

So a 500 on a listing page is not treated as a dead target. `_rescue_page`
re-fetches that page's item range in smaller slices -- 1000 splits into ten
100s, and a failing 100 splits into ten 10s -- and keeps whatever survives,
reporting the rows it could not reach instead of pretending the category is
empty. That recovers around 86% of a poisoned category rather than 0%.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Callable

from .client import (
    AlfagiftBadInput,
    AlfagiftBlocked,
    AlfagiftClient,
    AlfagiftError,
    AlfagiftNotFound,
    AlfagiftUpstreamBroken,
)
from .constants import (
    BRAND_ALPHABET,
    BRAND_LETTERS_UPSTREAM_BROKEN,
    BRANDS_PER_LETTER_CEILING,
    DEFAULT_BANNER_LOCATION,
    DEFAULT_PAGE_SIZE,
    EP_BANNERS,
    EP_BRAND_PRODUCTS,
    EP_BRANDS,
    EP_CATEGORIES,
    EP_CATEGORY_PRODUCTS,
    EP_NEW_PRODUCTS,
    EP_PRODUCT_DETAIL,
    EP_PROMO_DETAIL,
    EP_PROMO_PRODUCTS,
    EP_RECOMMENDATIONS,
    EP_SEARCH,
    EP_SUGGESTIONS,
    MAX_PAGE_SIZE,
    NEW_PRODUCTS_CEILING,
    RECOMMENDATIONS_CEILING,
    SITE_ROOT,
)
from .parsers import (
    as_strings,
    brand_url,
    enrich_product,
    error_record,
    flatten_categories,
    promotion_id_from_banner,
    record,
    resolve_brand_id,
    resolve_category_id,
    resolve_keyword,
    resolve_product_id,
    resolve_promotion_id,
)

log = logging.getLogger("alfagift.modes")


class Budget:
    """A shared ceiling on dataset rows for the whole run."""

    def __init__(self, limit: int) -> None:
        self.limit = max(0, int(limit or 0))
        self.used = 0

    @property
    def exhausted(self) -> bool:
        return self.limit > 0 and self.used >= self.limit

    def take(self, n: int = 1) -> bool:
        if self.exhausted:
            return False
        self.used += n
        return True

    @property
    def remaining(self) -> int | None:
        return None if self.limit == 0 else max(0, self.limit - self.used)


def _page_size(options: dict[str, Any]) -> int:
    raw = int(options.get("pageSize") or DEFAULT_PAGE_SIZE)
    return max(1, min(raw, MAX_PAGE_SIZE))


def _max_pages(options: dict[str, Any]) -> int:
    return max(1, int(options.get("maxPagesPerTarget") or 50))


# A poisoned page is split into ten smaller ones, twice: 1000 -> 100 -> 10.
# Below ten there is nothing left to save -- the loss is already smaller than
# one screen of results -- and the request count stops being worth it.
RESCUE_SPLIT = 10
RESCUE_MIN_PAGE_SIZE = 10


class PageLoss:
    """How many rows a target lost to poisoned pages, for the summary row."""

    def __init__(self) -> None:
        self.lost_rows = 0
        self.failed_pages = 0

    def note(self, rows: int) -> None:
        self.lost_rows += rows
        self.failed_pages += 1

    @property
    def any(self) -> bool:
        return self.failed_pages > 0


async def _rescue_page(
    client: AlfagiftClient,
    path: str,
    params: dict[str, Any],
    *,
    page: int,
    page_size: int,
    loss: PageLoss,
) -> list[dict[str, Any]]:
    """Re-fetch one failed page's item range in smaller slices.

    Page `page` at size `page_size` covers items [page*page_size, +page_size),
    so at size page_size/10 that is sub-pages page*10 .. page*10+9. The
    arithmetic is exact but Alfagift's own paging is not: a page asked for at
    limit=100 routinely comes back with 95 rows, so the ranges covered at two
    different page sizes overlap slightly. Callers therefore run the result
    through `_fresh` -- this function does not promise distinct rows.
    """
    if page_size <= RESCUE_MIN_PAGE_SIZE:
        loss.note(page_size)
        log.warning(
            "Page %d of %s is unreadable even at %d rows -- Alfagift returns "
            "HTTP 500 for it however it is sliced. Skipping those rows.",
            page, path, page_size,
        )
        return []

    smaller = max(RESCUE_MIN_PAGE_SIZE, page_size // RESCUE_SPLIT)
    factor = page_size // smaller
    log.info(
        "Page %d of %s returned HTTP 500; re-reading it as %d pages of %d.",
        page, path, factor, smaller,
    )

    recovered: list[dict[str, Any]] = []
    for step in range(factor):
        sub_page = page * factor + step
        try:
            payload = await client.get_json(
                path, params={**params, "start": sub_page, "limit": smaller}
            )
        except AlfagiftBlocked:
            recovered.extend(
                await _rescue_page(
                    client, path, params,
                    page=sub_page, page_size=smaller, loss=loss,
                )
            )
            continue
        if isinstance(payload, dict):
            recovered.extend(payload.get("products") or [])
    return recovered


async def _paged(
    client: AlfagiftClient,
    path: str,
    *,
    params: dict[str, Any],
    page_size: int,
    max_pages: int,
    budget: Budget,
    loss: PageLoss | None = None,
    from_page: int = 0,
    start_rank: int = 0,
    seen: set[str] | None = None,
) -> AsyncIterator[tuple[dict[str, Any], int, int]]:
    """Walk a product listing endpoint, yielding (product, page, rank).

    `rank` continues across pages so a caller can order the whole target from
    the dataset without knowing where the page boundaries fell.

    `seen` de-duplicates within one target, and is not optional paranoia.
    Alfagift's paging has genuine slack: a page asked for at limit=100 can come
    back with 95 rows, so the item ranges covered at one page size do not line
    up exactly with the ranges covered at another. The rescue path mixes two
    page sizes over the same target by design, which is precisely when that
    slack turns into a repeated row.
    """
    loss = loss if loss is not None else PageLoss()
    seen = seen if seen is not None else set()
    rank = start_rank
    total: int | None = None

    for page in range(from_page, max_pages):
        if budget.exhausted:
            return
        try:
            payload = await client.get_json(
                path, params={**params, "start": page, "limit": page_size}
            )
        except AlfagiftBlocked:
            # Not a dead target -- a page the gateway cannot serialise. Save
            # what is savable and carry on rather than abandoning the rest.
            products = await _rescue_page(
                client, path, params, page=page, page_size=page_size, loss=loss,
            )
            for product in _fresh(products, seen):
                yield product, page, rank
                rank += 1
            continue

        if not isinstance(payload, dict):
            return
        if total is None and isinstance(payload.get("totalData"), int):
            total = payload["totalData"]
        products = payload.get("products") or []
        if not products:
            # Silent empty: the documented end of the listing.
            return
        for product in _fresh(products, seen):
            yield product, page, rank
            rank += 1
        if total is not None and rank >= total:
            return
        if len(products) < page_size:
            return


def _fresh(
    products: list[dict[str, Any]], seen: set[str]
) -> list[dict[str, Any]]:
    """Drop rows already emitted for this target, remembering the rest."""
    out: list[dict[str, Any]] = []
    for product in products:
        key = str(product.get("productId") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(product)
    return out


async def _first_page(
    client: AlfagiftClient,
    path: str,
    params: dict[str, Any],
    *,
    page_size: int,
    loss: PageLoss,
    seen: set[str],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Read page 0, rescuing it if the gateway cannot serialise it.

    Returns the payload -- which carries the listing's totals and the echo
    fields that name the category or brand -- plus the products.

    When page 0 is poisoned there is no payload, and a summary row built from
    nothing would claim the category is named null and holds zero products.
    That is worse than no summary at all, so the echo fields are recovered with
    a one-row probe: a page of size 1 spans too little of the listing to hit
    the record that breaks the big pages, and answered fine on the category
    that poisoned every other page size during recon. If even that fails the
    fields stay null, which at least reads as unknown rather than as zero.
    """
    try:
        payload = await client.get_json(
            path, params={**params, "start": 0, "limit": page_size}
        )
    except AlfagiftBlocked:
        products = await _rescue_page(
            client, path, params, page=0, page_size=page_size, loss=loss,
        )
        probe: dict[str, Any] | None = None
        try:
            candidate = await client.get_json(
                path, params={**params, "start": 0, "limit": 1}
            )
            if isinstance(candidate, dict):
                # Keep the metadata, drop its single product -- that row comes
                # back through the rescue and must not be counted twice.
                probe = {k: v for k, v in candidate.items() if k != "products"}
        except AlfagiftError:
            log.info("Metadata probe for %s also failed; summary stays sparse", path)
        return probe, _fresh(products, seen)
    if not isinstance(payload, dict):
        return None, []
    return payload, _fresh(list(payload.get("products") or []), seen)


def _loss_note(loss: PageLoss) -> dict[str, Any]:
    """The warning fields a summary row carries when pages were unreadable."""
    if not loss.any:
        return {}
    return {
        "_warning": "poisoned_pages_skipped",
        "unreadablePages": loss.failed_pages,
        "approxRowsLost": loss.lost_rows,
    }


def _listing_is_hollow(payload: Any, id_field: str) -> bool:
    """Detect the hollow HTTP 200 an unknown category or brand id returns.

    Alfagift answers a nonexistent categoryId with a perfectly well-formed
    200 -- totalData 0, and every echo field (`currentCategoryId`,
    `currentCategoryName`) blank. A real but empty listing echoes the id back.
    Without this check a typo'd id looks exactly like a category that happens
    to have no products, and the run finishes green having scraped nothing.
    """
    if not isinstance(payload, dict):
        return True
    return not payload.get(id_field)


# -- product-listing modes --------------------------------------------------

async def mode_search(
    client: AlfagiftClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """Keyword search. Also emits the SEO block and Alfagift's own spelling
    suggestions, which are what tell you a keyword matched nothing useful.
    """
    page_size = _page_size(options)
    max_pages = _max_pages(options)

    for raw in options.get("searchKeywords") or []:
        if budget.exhausted:
            return
        keyword = resolve_keyword(raw)
        if not keyword:
            yield error_record(raw, "unsupported_input", "empty keyword", mode="search")
            continue
        source = f"{SITE_ROOT}/find/{keyword.replace(' ', '-')}"
        loss = PageLoss()
        seen: set[str] = set()
        base_params = {"keyword": keyword}
        try:
            first, products = await _first_page(
                client, EP_SEARCH, base_params, page_size=page_size, loss=loss, seen=seen,
            )
        except AlfagiftError as exc:
            yield error_record(raw, _kind(exc), str(exc), mode="search")
            continue

        if first is None and not products:
            yield error_record(
                raw, "parse_failed", "search returned no object", mode="search",
            )
            continue

        first = first or {}
        total = first.get("totalData") or 0
        log.info("Search %r: %s product(s) across %s page(s)",
                 keyword, total, first.get("totalPage"))

        meta_fields = {
            k: first.get(k)
            for k in ("metaTitle", "metaDescription", "seoText",
                      "automationLinkTitle", "suggestions", "keyword")
        }
        if budget.take():
            yield record(
                "search_summary", keyword,
                {
                    "totalData": total,
                    "totalPage": first.get("totalPage"),
                    **meta_fields,
                    **_loss_note(loss),
                },
                mode="search", source_url=source, query=keyword,
            )

        rank = 0
        for product in products:
            if not budget.take():
                break
            yield record(
                "product", product.get("productId"), enrich_product(product),
                mode="search", source_url=source, query=keyword, rank=rank, page=0,
            )
            rank += 1

        # Only walk on when one page genuinely did not hold everything.
        if rank and rank < total and not budget.exhausted:
            async for product, page, offset_rank in _paged(
                client, EP_SEARCH, params=base_params,
                page_size=page_size, max_pages=max_pages, budget=budget,
                loss=loss, from_page=1, start_rank=rank, seen=seen,
            ):
                if not budget.take():
                    break
                yield record(
                    "product", product.get("productId"), enrich_product(product),
                    mode="search", source_url=source, query=keyword,
                    rank=offset_rank, page=page,
                )


async def mode_search_suggestions(
    client: AlfagiftClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """Autocomplete. One request per seed, five suggestions back.

    Alfagift publishes no search volume anywhere, so these are ranked
    suggestions and nothing more -- the rank is the only popularity signal
    available, and it is relative, not absolute.
    """
    for raw in options.get("searchKeywords") or []:
        if budget.exhausted:
            return
        keyword = resolve_keyword(raw)
        if not keyword:
            yield error_record(raw, "unsupported_input", "empty keyword",
                               mode="searchSuggestions")
            continue
        try:
            payload = await client.get_json(EP_SUGGESTIONS, params={"keyword": keyword})
        except AlfagiftError as exc:
            yield error_record(raw, _kind(exc), str(exc), mode="searchSuggestions")
            continue
        suggestions = (payload or {}).get("suggestions") or []
        if not budget.take():
            return
        yield record(
            "search_suggestions", keyword,
            {"keyword": keyword, "suggestions": suggestions,
             "suggestionCount": len(suggestions)},
            mode="searchSuggestions", query=keyword,
        )


async def mode_category_tree(
    client: AlfagiftClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """The whole navigable category tree, one row per node."""
    payload = await client.get_json(EP_CATEGORIES)
    nodes = (payload or {}).get("categories") or []
    rows = flatten_categories(nodes)
    log.info("Category tree: %d node(s)", len(rows))
    for row in rows:
        if not budget.take():
            return
        yield record(
            "category", row.get("categoryId"), row,
            mode="categoryTree", source_url=SITE_ROOT,
            parent_id=row.get("parentId") or None,
        )


async def _category_targets(
    client: AlfagiftClient, options: dict[str, Any], level: int | None
) -> list[dict[str, Any]]:
    """Resolve the categories a run should walk.

    With no explicit ids, this fetches the tree and takes every node at the
    requested level. Level 0 (ten parents) is what `fullCatalog` uses, because
    a parent's listing already contains its children's products -- the ten
    level-0 calls cover the whole catalogue in ten requests, where the 51
    level-1 calls would cover the same ground more slowly.
    """
    payload = await client.get_json(EP_CATEGORIES)
    nodes = (payload or {}).get("categories") or []
    rows = flatten_categories(nodes)
    if level is None:
        return rows
    return [r for r in rows if r.get("categoryLevel") == level]


async def mode_category_products(
    client: AlfagiftClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """Products in one or more categories, given ids or /c/ URLs."""
    async for rec in _walk_categories(
        client, options, budget, mode="categoryProducts",
        targets=options.get("categoryIds") or [],
    ):
        yield rec


async def mode_full_catalog(
    client: AlfagiftClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """Every product Alfagift sells, by walking the ten level-0 categories.

    A parent's listing already contains its children's products, so ten
    requests cover the whole catalogue where the 51 level-1 calls would cover
    the same ground more slowly. A full run on 2026-09-21 produced 10,071
    products from 49 requests, all with distinct productIds -- each product
    resolves to exactly one top-level category, so the ten walks do not
    overlap. De-duplication is per target, not across them, in case that ever
    changes.
    """
    targets = await _category_targets(client, options, level=0)
    log.info(
        "Full catalogue: walking %d top-level categories (about 10,000 "
        "products).", len(targets),
    )
    async for rec in _walk_categories(
        client, options, budget, mode="fullCatalog",
        targets=[t["categoryId"] for t in targets],
        known=({t["categoryId"]: t for t in targets}),
    ):
        yield rec


async def _walk_categories(
    client: AlfagiftClient,
    options: dict[str, Any],
    budget: Budget,
    *,
    mode: str,
    targets: list[str],
    known: dict[str, dict[str, Any]] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    page_size = _page_size(options)
    max_pages = _max_pages(options)
    known = known or {}

    for raw in targets:
        if budget.exhausted:
            return
        category_id = resolve_category_id(str(raw))
        if not category_id:
            yield error_record(
                str(raw), "unsupported_input",
                "Expected a 24-character category id or an alfagift.id /c/ URL",
                mode=mode,
            )
            continue

        path = EP_CATEGORY_PRODUCTS.format(category_id=category_id)
        source = known.get(category_id, {}).get("categoryUrl") or f"{SITE_ROOT}/c/{category_id}"
        loss = PageLoss()
        seen: set[str] = set()
        # sortDirection is a proven decoy (see constants.py) but the web app
        # always sends it, so it is sent here too for contract parity.
        base_params = {"sortDirection": ""}
        try:
            first, products = await _first_page(
                client, path, base_params, page_size=page_size, loss=loss, seen=seen,
            )
        except AlfagiftError as exc:
            yield error_record(str(raw), _kind(exc), str(exc), mode=mode)
            continue

        if first is None and not products:
            yield error_record(
                str(raw), "fetch_failed",
                "Alfagift returned HTTP 500 for every slice of this category's "
                "first page, so none of it could be read",
                mode=mode,
            )
            continue

        if first is not None and _listing_is_hollow(first, "currentCategoryId"):
            yield error_record(
                str(raw), "not_found",
                "Alfagift returned a hollow HTTP 200 with a blank "
                "currentCategoryId, which is how it reports an unknown "
                "category id rather than a 404",
                mode=mode,
            )
            continue

        first = first or {}
        known_row = known.get(category_id, {})
        total = first.get("totalData") or known_row.get("totalData") or 0
        name = first.get("currentCategoryName") or known_row.get("categoryName")
        log.info("Category %s (%s): %s product(s)", name, category_id, total)

        if budget.take():
            yield record(
                "category_summary", category_id,
                {
                    "categoryId": category_id,
                    "categoryName": name,
                    "parentId": first.get("currentCategoryParentId"),
                    "totalData": total,
                    "categoryUrl": source,
                    **_loss_note(loss),
                },
                mode=mode, source_url=source,
                parent_id=first.get("currentCategoryParentId") or None,
            )

        rank = 0
        for product in products:
            if not budget.take():
                break
            yield record(
                "product", product.get("productId"), enrich_product(product),
                mode=mode, source_url=source, rank=rank, page=0,
                parent_id=category_id,
            )
            rank += 1

        if rank and rank < total and not budget.exhausted:
            async for product, page, offset_rank in _paged(
                client, path, params=base_params,
                page_size=page_size, max_pages=max_pages, budget=budget,
                loss=loss, from_page=1, start_rank=rank, seen=seen,
            ):
                if not budget.take():
                    break
                yield record(
                    "product", product.get("productId"), enrich_product(product),
                    mode=mode, source_url=source, rank=offset_rank, page=page,
                    parent_id=category_id,
                )

        if loss.any:
            log.warning(
                "Category %s lost about %d row(s) across %d unreadable page(s) "
                "-- Alfagift answers HTTP 500 for those slices however they "
                "are requested.",
                name or category_id, loss.lost_rows, loss.failed_pages,
            )


async def mode_product_detail(
    client: AlfagiftClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """The full product page payload: barcode, brand, gallery, long copy.

    Worth a separate request per product because listings do not carry any of
    it -- barcode, brandId/brandName, the four image sets, the HTML
    description, `discountEndDate` and the benefit list exist only here.
    """
    for raw in options.get("productIds") or []:
        if budget.exhausted:
            return
        product_id = resolve_product_id(str(raw))
        if not product_id:
            yield error_record(
                str(raw), "unsupported_input",
                "Expected a numeric productId or an alfagift.id /p/ URL. A SKU "
                "(for example A13170001210) is not accepted here -- Alfagift "
                "answers one with HTTP 500, and only the numeric productId "
                "from a listing row or a /p/ URL works.",
                mode="productDetail",
            )
            continue
        try:
            payload = await client.get_json(
                EP_PRODUCT_DETAIL.format(product_id=product_id)
            )
        except AlfagiftNotFound:
            yield error_record(
                str(raw), "not_found",
                f"Alfagift has no product with id {product_id}",
                mode="productDetail",
            )
            continue
        except AlfagiftError as exc:
            yield error_record(str(raw), _kind(exc), str(exc), mode="productDetail")
            continue

        detail = (payload or {}).get("productDetail")
        if not isinstance(detail, dict):
            yield error_record(
                str(raw), "parse_failed",
                "Response carried no productDetail object",
                mode="productDetail",
            )
            continue
        if not budget.take():
            return
        yield record(
            "product_detail", detail.get("productId") or product_id,
            enrich_product(detail),
            mode="productDetail",
            source_url=f"{SITE_ROOT}/p/{product_id}",
        )


# -- brand modes ------------------------------------------------------------

async def mode_brand_directory(
    client: AlfagiftClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """Every brand Alfagift indexes, swept A-Z.

    Five letters are permanently broken upstream (C, F, G, V, W): they answer
    HTTP 500 "solr.brands.error" on every attempt, from every address, with
    backoff. That is Alfagift's index, not this actor -- so those letters get a
    diagnostic row naming the fault rather than silently missing brands.
    """
    letters = [
        letter.upper()
        for letter in (as_strings(options.get("brandLetters")) or list(BRAND_ALPHABET))
        if letter.strip()
    ]
    broken_hit = []
    for letter in letters:
        if budget.exhausted:
            break
        try:
            payload = await client.get_json(EP_BRANDS, params={"alphabet": letter})
        except AlfagiftUpstreamBroken as exc:
            broken_hit.append(letter)
            yield error_record(
                letter, "upstream_index_broken", str(exc), mode="brandDirectory",
            )
            continue
        except AlfagiftError as exc:
            yield error_record(letter, _kind(exc), str(exc), mode="brandDirectory")
            continue

        brands = (payload or {}).get("brands") or []
        if len(brands) >= BRANDS_PER_LETTER_CEILING:
            log.warning(
                "Letter %s returned %d brands, which is the server's per-letter "
                "ceiling -- the list is probably truncated.",
                letter, len(brands),
            )
        log.info("Brand letter %s: %d brand(s)", letter, len(brands))
        for rank, brand in enumerate(brands):
            if not budget.take():
                return
            row = dict(brand)
            row["brandUrl"] = brand_url(brand)
            row["alphabet"] = letter
            yield record(
                "brand", brand.get("id"), row,
                mode="brandDirectory", source_url=f"{SITE_ROOT}/brands",
                query=letter, rank=rank,
            )
    if broken_hit:
        log.warning(
            "Letters %s are broken in Alfagift's own brand index and returned "
            "no data. Known-bad set: %s.",
            ", ".join(broken_hit), ", ".join(sorted(BRAND_LETTERS_UPSTREAM_BROKEN)),
        )


async def mode_brand_products(
    client: AlfagiftClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """Products carried under one or more brands.

    Many rows in the brand directory are junk entries with zero products (the
    brand literally named "A" is one), so an empty result here is usually the
    brand and not the request.
    """
    page_size = _page_size(options)
    max_pages = _max_pages(options)

    for raw in options.get("brandIds") or []:
        if budget.exhausted:
            return
        brand_id = resolve_brand_id(str(raw))
        if not brand_id:
            yield error_record(
                str(raw), "unsupported_input",
                "Expected a numeric brandId or an alfagift.id /b/ URL",
                mode="brandProducts",
            )
            continue

        path = EP_BRAND_PRODUCTS.format(brand_id=brand_id)
        loss = PageLoss()
        seen: set[str] = set()
        # storeId is in the app's own template and is accepted empty;
        # anonymous callers have no store, and sending it empty returns the
        # national listing.
        base_params = {"storeId": ""}
        try:
            first, products = await _first_page(
                client, path, base_params, page_size=page_size, loss=loss, seen=seen,
            )
        except AlfagiftError as exc:
            yield error_record(str(raw), _kind(exc), str(exc), mode="brandProducts")
            continue

        if first is None and not products:
            yield error_record(
                str(raw), "fetch_failed",
                "Alfagift returned HTTP 500 for every slice of this brand's "
                "first page",
                mode="brandProducts",
            )
            continue

        if first is not None and _listing_is_hollow(first, "currentBrandId"):
            yield error_record(
                str(raw), "not_found",
                "Alfagift returned a hollow HTTP 200 with a blank "
                "currentBrandId, which is how it reports an unknown brand id",
                mode="brandProducts",
            )
            continue

        first = first or {}
        total = first.get("totalData") or 0
        name = first.get("currentBrandName")
        source = f"{SITE_ROOT}/b/{brand_id}"
        log.info("Brand %s (%s): %s product(s)", name, brand_id, total)

        if budget.take():
            yield record(
                "brand_summary", brand_id,
                {
                    "brandId": brand_id,
                    "brandName": name,
                    "totalData": total,
                    "brandMetaTitle": first.get("brandMetaTitle"),
                    "brandMetaDescription": first.get("brandMetaDescription"),
                    "brandMetaKeyword": first.get("brandMetaKeyword"),
                    "brandUrl": source,
                    **_loss_note(loss),
                },
                mode="brandProducts", source_url=source,
            )

        rank = 0
        for product in products:
            if not budget.take():
                break
            yield record(
                "product", product.get("productId"), enrich_product(product),
                mode="brandProducts", source_url=source, rank=rank, page=0,
                parent_id=brand_id,
            )
            rank += 1

        if rank and rank < total and not budget.exhausted:
            async for product, page, offset_rank in _paged(
                client, path, params=base_params,
                page_size=page_size, max_pages=max_pages, budget=budget,
                loss=loss, from_page=1, start_rank=rank, seen=seen,
            ):
                if not budget.take():
                    break
                yield record(
                    "product", product.get("productId"), enrich_product(product),
                    mode="brandProducts", source_url=source,
                    rank=offset_rank, page=page, parent_id=brand_id,
                )


# -- feed modes -------------------------------------------------------------

async def mode_new_arrivals(
    client: AlfagiftClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """Alfagift's newest-products feed. Server-capped at 198 rows.

    The cap is real and not a paging bug: limit=200 returns 198 and limit=1000
    also returns 198, with totalData echoing whatever came back rather than a
    catalogue-wide count.
    """
    async for rec in _flat_feed(
        client, budget, EP_NEW_PRODUCTS, NEW_PRODUCTS_CEILING, mode="newArrivals",
    ):
        yield rec


async def mode_recommendations(
    client: AlfagiftClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """The homepage recommendation rail. Server-capped at 48 rows.

    These are Alfagift's merchandising picks for an anonymous visitor, not
    personalised output -- there is no member session here for them to be
    personalised against.
    """
    async for rec in _flat_feed(
        client, budget, EP_RECOMMENDATIONS, RECOMMENDATIONS_CEILING,
        mode="recommendations",
    ):
        yield rec


async def _flat_feed(
    client: AlfagiftClient,
    budget: Budget,
    path: str,
    ceiling: int,
    *,
    mode: str,
) -> AsyncIterator[dict[str, Any]]:
    """One request for the whole feed.

    `pageSize` deliberately does not apply here. These two endpoints stop at a
    fixed number of rows however large a limit they are given, so asking for
    the ceiling gets everything there is in a single call and asking for less
    would only truncate it.
    """
    payload = await client.get_json(path, params={"start": 0, "limit": ceiling})
    products = (payload or {}).get("products") or []
    if len(products) >= ceiling:
        log.info(
            "%s returned %d products, the server's ceiling for this feed. "
            "Alfagift does not page past it.", mode, len(products),
        )
    log.info("%s: %d product(s)", mode, len(products))
    for rank, product in enumerate(products):
        if not budget.take():
            return
        yield record(
            "product", product.get("productId"), enrich_product(product),
            mode=mode, source_url=SITE_ROOT, rank=rank, page=0,
        )


# -- promotion modes --------------------------------------------------------

async def _fetch_banners(
    client: AlfagiftClient, options: dict[str, Any]
) -> list[dict[str, Any]]:
    location = options.get("bannerLocation") or DEFAULT_BANNER_LOCATION
    limit = int(options.get("bannerLimit") or 150)
    payload = await client.get_json(
        EP_BANNERS.format(location=location), params={"start": 0, "limit": limit}
    )
    return (payload or {}).get("banners") or []


async def mode_promo_banners(
    client: AlfagiftClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """Live promotional campaigns with their run dates and artwork.

    Each banner carries a start and end date, so a scheduled run of this mode
    is a campaign calendar: what Alfamart is promoting, for how long, and with
    which creative.

    The id trap: a banner's own `id` is NOT the id the promotion-products
    endpoint wants. That one is buried in `bannerDeepLinkTap`. Both are emitted
    -- `id` on the envelope, `promotionId` in the data -- so downstream never
    has to guess which is which.
    """
    banners = await _fetch_banners(client, options)
    log.info("Banner location %s: %d banner(s)",
             options.get("bannerLocation") or DEFAULT_BANNER_LOCATION, len(banners))

    for rank, banner in enumerate(banners):
        if not budget.take():
            return
        promotion_id = promotion_id_from_banner(banner)
        row = dict(banner)
        row["promotionId"] = promotion_id
        row["bannerId"] = banner.get("id")

        if promotion_id and options.get("includePromoDetail"):
            try:
                detail = await client.get_json(
                    EP_PROMO_DETAIL.format(promotion_id=banner.get("id"))
                )
                if isinstance(detail, dict):
                    row["promoDetail"] = detail
            except AlfagiftError as exc:
                row["promoDetail"] = {"_error": _kind(exc), "_errorDetail": str(exc)}

        yield record(
            "promo_banner", banner.get("id"), row,
            mode="promoBanners", source_url=banner.get("bannerDeepLinkTap"),
            rank=rank,
        )


async def mode_promo_products(
    client: AlfagiftClient, options: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """The products inside each live promotional campaign.

    With no explicit promotionIds this discovers them from the banner rail, so
    the default run answers "what is on promotion at Alfamart right now, and at
    what price" in two hops.
    """
    explicit = options.get("promotionIds") or []
    targets: list[tuple[str, dict[str, Any] | None]] = []

    if explicit:
        for raw in explicit:
            promotion_id = resolve_promotion_id(str(raw))
            if not promotion_id:
                yield error_record(
                    str(raw), "unsupported_input",
                    "Expected a 24-character promotion id or a "
                    "/promotion-products?id=... URL",
                    mode="promoProducts",
                )
                continue
            targets.append((promotion_id, None))
    else:
        banners = await _fetch_banners(client, options)
        for banner in banners:
            promotion_id = promotion_id_from_banner(banner)
            if promotion_id:
                targets.append((promotion_id, banner))
        log.info(
            "Discovered %d promotion(s) from %d banner(s)",
            len(targets), len(banners),
        )

    seen: set[str] = set()
    for promotion_id, banner in targets:
        if budget.exhausted:
            return
        if promotion_id in seen:
            continue
        seen.add(promotion_id)
        source = f"{SITE_ROOT}/promotion-products?id={promotion_id}"
        try:
            payload = await client.get_json(
                EP_PROMO_PRODUCTS.format(promotion_id=promotion_id)
            )
        except AlfagiftError as exc:
            yield error_record(promotion_id, _kind(exc), str(exc), mode="promoProducts")
            continue

        if payload is None:
            # Zero-length HTTP 200: this id is not a promotion. Almost always
            # a banner id used in place of the deep-link id.
            yield error_record(
                promotion_id, "not_a_promotion",
                "Alfagift answered with an empty body, which is how it reports "
                "an id that is not a promotion -- a banner's own id does not "
                "work here, only the id inside its bannerDeepLinkTap",
                mode="promoProducts",
            )
            continue

        products = payload.get("products") or []
        campaign_name = (banner or {}).get("bannerName")
        log.info("Promotion %s (%s): %d product(s)",
                 campaign_name or "?", promotion_id, len(products))

        if budget.take():
            yield record(
                "promo_campaign", promotion_id,
                {
                    "promotionId": promotion_id,
                    "campaignName": campaign_name,
                    "startDate": (banner or {}).get("startDate"),
                    "endDate": (banner or {}).get("endDate"),
                    "bannerId": (banner or {}).get("id"),
                    "bannerImageFileName": (banner or {}).get("bannerImageFileName"),
                    "totalData": payload.get("totalData"),
                    "productCount": len(products),
                },
                mode="promoProducts", source_url=source,
            )

        for rank, product in enumerate(products):
            if not budget.take():
                return
            yield record(
                "product", product.get("productId"), enrich_product(product),
                mode="promoProducts", source_url=source, rank=rank,
                parent_id=promotion_id,
                extra_meta={"campaignName": campaign_name},
            )


def _kind(exc: Exception) -> str:
    """Map an exception onto the `_error` vocabulary the output schema lists."""
    return {
        AlfagiftNotFound: "not_found",
        AlfagiftBadInput: "unsupported_input",
        AlfagiftUpstreamBroken: "upstream_index_broken",
        AlfagiftBlocked: "fetch_failed",
    }.get(type(exc), "fetch_failed")


ModeFn = Callable[
    [AlfagiftClient, dict[str, Any], Budget], AsyncIterator[dict[str, Any]]
]

MODES: dict[str, ModeFn] = {
    "search": mode_search,
    "searchSuggestions": mode_search_suggestions,
    "categoryTree": mode_category_tree,
    "categoryProducts": mode_category_products,
    "fullCatalog": mode_full_catalog,
    "productDetail": mode_product_detail,
    "brandDirectory": mode_brand_directory,
    "brandProducts": mode_brand_products,
    "newArrivals": mode_new_arrivals,
    "recommendations": mode_recommendations,
    "promoBanners": mode_promo_banners,
    "promoProducts": mode_promo_products,
}

# Modes that cannot do anything without an input list. The rest discover their
# own targets (the category tree, the banner rail, the A-Z sweep).
MODE_REQUIRED_INPUT: dict[str, tuple[str, ...]] = {
    "search": ("searchKeywords",),
    "searchSuggestions": ("searchKeywords",),
    "categoryProducts": ("categoryIds",),
    "productDetail": ("productIds",),
    "brandProducts": ("brandIds",),
}
