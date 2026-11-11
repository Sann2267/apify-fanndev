"""One async generator per scrape mode.

Every mode yields dataset records and never raises for a per-target failure:
a target that cannot be fetched becomes a diagnostic error row so downstream
joins always see a row for every input.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, AsyncIterator, Callable

from .client import IndotradingClient, IndotradingNotFound
from .constants import (
    CATALOG_PATH,
    DEFAULT_CONCURRENCY,
    DEFAULT_MAX_PAGES,
    LAST_LOGIN_FAILED,
    LAST_LOGIN_PATH,
    MAX_PAGE_HARD_CAP,
    PAGE_PARAM,
    SEARCH_COMPANY_PATH,
    SEARCH_PRODUCTS_PATH,
    SITE_ROOT,
    WA_LEADS_PATH,
)
from .parsers import (
    company_directory_ids,
    envelope,
    error_record,
    listing_meta,
    parse_category_tree,
    parse_company_cards,
    parse_product_cards,
    parse_product_detail,
    parse_supplier_product_cards,
    parse_supplier_profile,
)

log = logging.getLogger("indotrading.modes")

RE_COMPANY_DIR_HREF = re.compile(r'href="(/company_[a-z0-9\-]+_\d+/?)"', re.I)


# -- input normalisation ---------------------------------------------------


def _as_list(value: Any) -> list[str]:
    """Accept both ["a", "b"] and [{"url": "a"}] -- Apify's request-list editor
    emits the latter, a plain string array the former."""
    if not value:
        return []
    if isinstance(value, str):
        value = [value]
    out: list[str] = []
    for item in value:
        if isinstance(item, dict):
            item = item.get("url") or item.get("value") or item.get("slug")
        if item:
            out.append(str(item).strip())
    return out


def category_path(target: str) -> str:
    """Normalise a category input to a site path.

    Accepts a full URL, a "/jual-x" path, a bare "jual-x" slug, or a plain
    "x" name, because users paste all four.
    """
    target = target.strip()
    if target.startswith("http"):
        target = "/" + target.split("indotrading.com/", 1)[-1].lstrip("/")
    if not target.startswith("/"):
        target = "/" + target
    target = target.rstrip("/")
    if not target.startswith("/jual-"):
        target = "/jual-" + target.lstrip("/")
    return target


def supplier_path(target: str) -> str:
    target = target.strip()
    if target.startswith("http"):
        target = "/" + target.split("indotrading.com/", 1)[-1].lstrip("/")
    if not target.startswith("/"):
        target = "/" + target
    # A supplier profile lives at the site root; strip any ?page= the user
    # copied out of the address bar so paging starts where they expect.
    return target.split("?", 1)[0].rstrip("/")


def _dedupe_key(record: dict[str, Any]) -> str | None:
    """Identity of a listing row, for suppressing repeated pages.

    Returns None when the row carries no usable identity, in which case it is
    emitted rather than dropped -- losing a row is worse than repeating one.
    """
    for field in ("productId", "companySlug", "categorySlug"):
        value = record.get(field)
        if value:
            return f"{field}:{value}"
    url = record.get("productUrl") or record.get("companyUrl")
    return f"url:{url}" if url else None


def _page_params(page: int) -> dict[str, Any] | None:
    # Page 1 is the bare path. `?page=1` also works, but the bare path is what
    # a browser requests and keeps the referer chain natural.
    return None if page <= 1 else {PAGE_PARAM: page}


def _resolved_max_pages(actor_input: dict[str, Any]) -> int:
    requested = int(actor_input.get("maxPages") or DEFAULT_MAX_PAGES)
    return max(1, min(requested, MAX_PAGE_HARD_CAP))


# -- contact enrichment ----------------------------------------------------


async def _whatsapp_for(
    client: IndotradingClient, secure_product_id: str, referer: str
) -> dict[str, Any] | None:
    """One call to the open contact endpoint on webapi.indotrading.com.

    Needs the encrypted id from data-enc-pid; the plain P-number is rejected.
    Returns None rather than raising, because a missing phone number should
    degrade the record, not fail the page it came from.
    """
    try:
        data = await client.get_json(
            WA_LEADS_PATH, params={"secureProductId": secure_product_id}, referer=referer
        )
    except Exception as exc:  # noqa: BLE001 - enrichment is best-effort
        log.warning("Contact lookup failed for %s: %s", secure_product_id[:16], exc)
        return None
    if not isinstance(data, dict):
        return None
    return {
        "whatsappNumber": data.get("waNumber"),
        "contactCompanyName": data.get("companyName"),
        "contactProductName": data.get("productName"),
    }


async def _enrich_contacts(
    client: IndotradingClient,
    records: list[dict[str, Any]],
    referer: str,
    concurrency: int,
) -> None:
    """Fill whatsappNumber in place, bounded by a semaphore.

    One extra request per product, so this roughly doubles the cost of a
    listing page -- it is opt-in for that reason.
    """
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(record: dict[str, Any]) -> None:
        secure_id = record.get("secureProductId")
        if not secure_id:
            # The card carried no encrypted id at all, so there is nothing to
            # look up. Say so rather than leaving the field indistinguishable
            # from a lookup that ran and came back empty.
            record["whatsappNumber"] = None
            record["_warning"] = "no_secure_product_id_on_card"
            return
        async with semaphore:
            extra = await _whatsapp_for(client, secure_id, referer)
        if extra is None:
            record["whatsappNumber"] = None
            record["_warning"] = "contact_lookup_failed"
            return
        record.update(extra)
        if not extra.get("whatsappNumber"):
            # The endpoint answered 200 with a complete record and simply no
            # waNumber field: this seller has no WhatsApp on file. Distinct
            # from a failed lookup, and the two must not look alike.
            record["_warning"] = "no_whatsapp_number_on_file"

    await asyncio.gather(*(one(r) for r in records))


async def _enrich_last_login(
    client: IndotradingClient, records: list[dict[str, Any]], referer: str
) -> None:
    """Batch the activity lookup for every distinct company on a page.

    The endpoint takes a list and answers positionally with minutes since last
    login, or the string "failed" for an id it cannot resolve.
    """
    ids: list[str] = []
    for record in records:
        company_id = record.get("companyId")
        if company_id and company_id not in ids:
            ids.append(company_id)
    if not ids:
        return
    try:
        answer = await client.post_json(
            LAST_LOGIN_PATH, {"lCompanyId": ids}, referer=referer
        )
    except Exception as exc:  # noqa: BLE001 - enrichment is best-effort
        log.warning("Last-login lookup failed for %d companies: %s", len(ids), exc)
        return
    if not isinstance(answer, list):
        return

    by_id: dict[str, int | None] = {}
    for company_id, value in zip(ids, answer):
        if value == LAST_LOGIN_FAILED:
            by_id[company_id] = None
            continue
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            minutes = None
        by_id[company_id] = minutes if (minutes or 0) > 0 else None

    for record in records:
        company_id = record.get("companyId")
        if company_id in by_id:
            record["lastLoginMinutesAgo"] = by_id[company_id]


# -- shared listing walker -------------------------------------------------


async def _walk_listing(
    client: IndotradingClient,
    path: str,
    input_label: str,
    source: str,
    record_type: str,
    parse: Callable[[str], list[dict[str, Any]]],
    actor_input: dict[str, Any],
    base_params: dict[str, Any] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Page through a listing until it runs dry.

    The stop condition is an empty page, never the advertised page count:
    indotrading prints "(Halaman 1 dari 16)" on a category that is empty from
    page 13 onward, so trusting the counter would emit four pages of nothing
    and report success.
    """
    max_pages = _resolved_max_pages(actor_input)
    max_items = int(actor_input.get("maxItemsPerTarget") or 0)
    include_contact = bool(actor_input.get("includeContact"))
    include_last_login = bool(actor_input.get("includeLastLogin"))
    concurrency = int(actor_input.get("concurrency") or DEFAULT_CONCURRENCY)

    emitted = 0
    duplicates = 0
    seen_keys: set[str] = set()
    referer = SITE_ROOT + path
    meta: dict[str, Any] = {}

    effective_path = path
    effective_params = dict(base_params or {})

    for page in range(1, max_pages + 1):
        params = dict(effective_params)
        page_params = _page_params(page)
        if page_params:
            params.update(page_params)

        try:
            final_url, body = await client.get_page(
                effective_path, params=params or None, referer=referer
            )
        except IndotradingNotFound as exc:
            if page == 1:
                yield error_record(input_label, "not_found", str(exc), source)
            return
        except Exception as exc:  # noqa: BLE001 - one target must not kill the run
            yield error_record(
                input_label, "fetch_failed", f"{type(exc).__name__}: {exc}", source
            )
            return

        if page == 1:
            # A search keyword that matches a category name is 302'd to
            # /jual-<slug> -- and the redirect DROPS the query string, so
            # re-requesting /searchkeyword.aspx?keyword=...&page=2 lands back
            # on page 1 of the category, forever. Follow the redirect once and
            # page the destination directly.
            landed = "/" + final_url.split("indotrading.com/", 1)[-1].lstrip("/")
            landed_path = landed.split("?", 1)[0].rstrip("/")
            if landed_path and landed_path != effective_path.rstrip("/"):
                log.info(
                    "%s: redirected to %s -- paging that path directly, since the "
                    "redirect discards the page parameter",
                    input_label, landed_path,
                )
                effective_path = landed_path
                effective_params = {}

            meta = listing_meta(body)
            if meta.get("advertisedPages"):
                log.info(
                    "%s: site advertises %s pages / %s products (treated as a hint, "
                    "not a stop condition)",
                    input_label,
                    meta.get("advertisedPages"),
                    meta.get("advertisedTotalProducts"),
                )

        records = parse(body)
        if not records:
            if page == 1:
                # The page exists and rendered, but matched nothing. That is a
                # fact about the query, not a failure -- and it still has to
                # leave a row, or a downstream join sees the same silence it
                # would see from a crash.
                yield error_record(
                    input_label,
                    "no_results",
                    f"{final_url} rendered with no results",
                    source,
                )
                return
            log.info(
                "%s: page %d is empty -- stopping after %d records "
                "(%d repeats dropped; site advertised %s pages / %s items)",
                input_label, page, emitted, duplicates,
                meta.get("advertisedPages"), meta.get("advertisedTotalProducts"),
            )
            return

        # Indotrading's paging is not strictly stable: a page request
        # occasionally serves a neighbouring page's content instead, so the
        # same item arrives twice. Measured over /jual-pressure-washer, page 3
        # came back as a repeat of page 2 while pages 5-11 were all fresh.
        # Deduplicate before enrichment, so a repeat does not also pay for a
        # second contact lookup -- but never stop on it, because a page that
        # yields nothing new is followed by pages that do.
        fresh: list[dict[str, Any]] = []
        for record in records:
            key = _dedupe_key(record)
            if key is not None:
                if key in seen_keys:
                    duplicates += 1
                    continue
                seen_keys.add(key)
            fresh.append(record)
        records = fresh
        if not records:
            log.info(
                "%s: page %d was entirely repeats -- continuing, indotrading "
                "serves a stale page now and then",
                input_label, page,
            )
            referer = final_url
            continue

        if include_contact and record_type == "product":
            await _enrich_contacts(client, records, final_url, concurrency)
        if include_last_login:
            await _enrich_last_login(client, records, final_url)

        for record in records:
            if max_items and emitted >= max_items:
                log.info("%s: reached maxItemsPerTarget=%d", input_label, max_items)
                return
            yield envelope(
                input_label,
                source,
                record_type,
                {
                    **record,
                    "pageNumber": page,
                    "pageUrl": final_url,
                    "advertisedPages": meta.get("advertisedPages"),
                    "advertisedTotalProducts": meta.get("advertisedTotalProducts"),
                },
            )
            emitted += 1

        referer = final_url


# -- modes -----------------------------------------------------------------


async def mode_category_products(
    client: IndotradingClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    for target in _as_list(actor_input.get("categories")):
        path = category_path(target)
        log.info("Category %s", path)
        async for record in _walk_listing(
            client, path, target, "S1-category-html", "product",
            parse_product_cards, actor_input,
        ):
            yield record


async def mode_search_products(
    client: IndotradingClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Keyword product search.

    A term that matches a category name is 302'd to /jual-<slug> and answers
    with the whole category; a term that does not stays on the search path
    with a narrower result set. Both render the same card, so the walker does
    not need to care which happened -- but pageUrl records which it was.
    """
    for term in _as_list(actor_input.get("searchTerms")):
        log.info("Product search %r", term)
        async for record in _walk_listing(
            client,
            SEARCH_PRODUCTS_PATH,
            term,
            "S1-search-html",
            "product",
            parse_product_cards,
            actor_input,
            base_params={"keyword": term.lower(), "showcase": "false"},
        ):
            yield record


async def mode_product_detail(
    client: IndotradingClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    include_contact = bool(actor_input.get("includeContact"))
    concurrency = int(actor_input.get("concurrency") or DEFAULT_CONCURRENCY)
    semaphore = asyncio.Semaphore(max(1, concurrency))
    targets = _as_list(actor_input.get("productUrls"))

    async def one(target: str) -> dict[str, Any]:
        url = target if target.startswith("http") else SITE_ROOT + "/" + target.lstrip("/")
        async with semaphore:
            try:
                final_url, body = await client.get_page(url, referer=SITE_ROOT + "/")
            except IndotradingNotFound as exc:
                return error_record(target, "not_found", str(exc), "S1-product-jsonld")
            except Exception as exc:  # noqa: BLE001
                return error_record(
                    target, "fetch_failed", f"{type(exc).__name__}: {exc}",
                    "S1-product-jsonld",
                )
            record = parse_product_detail(body, final_url)
            if not record.get("productName"):
                return error_record(
                    target, "unexpected_shape",
                    "No Product JSON-LD and no #productTitle on the page",
                    "S1-product-jsonld",
                )
            if include_contact and record.get("secureProductId"):
                extra = await _whatsapp_for(client, record["secureProductId"], final_url)
                if extra:
                    record.update(extra)
                else:
                    record["whatsappNumber"] = None
                    record["_warning"] = "contact_lookup_failed"
            return envelope(target, "S1-product-jsonld", "product", record)

    for coro in asyncio.as_completed([one(t) for t in targets]):
        yield await coro


async def mode_supplier_profile(
    client: IndotradingClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Full company profile, optionally followed by its product catalogue."""
    include_products = bool(actor_input.get("includeSupplierProducts"))
    include_last_login = bool(actor_input.get("includeLastLogin"))
    max_pages = _resolved_max_pages(actor_input)

    for target in _as_list(actor_input.get("suppliers")):
        path = supplier_path(target)
        log.info("Supplier %s", path)
        try:
            final_url, body = await client.get_page(path, referer=SITE_ROOT + "/")
        except IndotradingNotFound as exc:
            yield error_record(target, "not_found", str(exc), "S1-supplier-html")
            continue
        except Exception as exc:  # noqa: BLE001
            yield error_record(
                target, "fetch_failed", f"{type(exc).__name__}: {exc}",
                "S1-supplier-html",
            )
            continue

        profile = parse_supplier_profile(body, final_url)
        if not profile.get("companyName"):
            yield error_record(
                target, "unexpected_shape",
                "No <h1> company name on the supplier page", "S1-supplier-html",
            )
            continue

        first_page = parse_supplier_product_cards(body)
        # The profile page never prints the company id, but every product card
        # on it carries data-rfq-cid, which is the same value.
        company_id = next(
            (c.get("companyId") for c in first_page if c.get("companyId")), None
        )
        profile["companyId"] = company_id

        if include_last_login and company_id:
            holder = [{"companyId": company_id}]
            await _enrich_last_login(client, holder, final_url)
            profile["lastLoginMinutesAgo"] = holder[0].get("lastLoginMinutesAgo")

        profile["productCountOnFirstPage"] = len(first_page)
        yield envelope(target, "S1-supplier-html", "supplier", profile)

        if not include_products:
            continue

        for page in range(1, max_pages + 1):
            if page == 1:
                cards, page_url = first_page, final_url
            else:
                try:
                    page_url, page_body = await client.get_page(
                        path, params={PAGE_PARAM: page}, referer=final_url
                    )
                except Exception as exc:  # noqa: BLE001
                    yield error_record(
                        target, "fetch_failed",
                        f"page {page}: {type(exc).__name__}: {exc}",
                        "S1-supplier-html",
                    )
                    break
                cards = parse_supplier_product_cards(page_body)
            if not cards:
                break
            for card in cards:
                yield envelope(
                    target, "S1-supplier-html", "product",
                    {
                        **card,
                        "companySlug": profile.get("companySlug"),
                        "pageNumber": page,
                        "pageUrl": page_url,
                    },
                )


async def _directory_path(client: IndotradingClient, target: str) -> str:
    """Resolve a user target to a /company_<slug>_<id>/ path.

    A category page links to its own supplier directory, which is the only
    place the numeric category id appears -- it is not derivable from the slug.
    """
    cleaned = target.strip()
    if "company_" in cleaned:
        if cleaned.startswith("http"):
            return "/" + cleaned.split("indotrading.com/", 1)[-1].lstrip("/")
        return "/" + cleaned.lstrip("/")

    path = category_path(cleaned)
    _, body = await client.get_page(path, referer=SITE_ROOT + "/")
    match = RE_COMPANY_DIR_HREF.search(body)
    if not match:
        raise IndotradingNotFound(
            f"{path} exists but links to no supplier directory"
        )
    return match.group(1)


async def mode_supplier_directory(
    client: IndotradingClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Suppliers listed under a category."""
    for target in _as_list(actor_input.get("categories")):
        try:
            path = await _directory_path(client, target)
        except IndotradingNotFound as exc:
            yield error_record(target, "not_found", str(exc), "S1-directory-html")
            continue
        except Exception as exc:  # noqa: BLE001
            yield error_record(
                target, "fetch_failed", f"{type(exc).__name__}: {exc}",
                "S1-directory-html",
            )
            continue

        log.info("Supplier directory %s (from %r)", path, target)
        async for record in _walk_listing(
            client, path, target, "S1-directory-html", "supplier",
            parse_company_cards, actor_input,
        ):
            record.update(company_directory_ids(record.get("pageUrl") or path))
            yield record


async def mode_search_suppliers(
    client: IndotradingClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Keyword company search.

    /searchcompany.aspx is a resolver, not a result page: it 302s to the
    directory of whichever category best matches the keyword. So the first
    request is spent finding the path, and the walker pages that.
    """
    for term in _as_list(actor_input.get("searchTerms")):
        try:
            final_url, _ = await client.get_page(
                SEARCH_COMPANY_PATH,
                params={"keyword": term.lower()},
                referer=SITE_ROOT + "/",
            )
        except IndotradingNotFound as exc:
            yield error_record(
                term, "not_found",
                f"No supplier category matched {term!r}: {exc}",
                "S1-directory-html",
            )
            continue
        except Exception as exc:  # noqa: BLE001
            yield error_record(
                term, "fetch_failed", f"{type(exc).__name__}: {exc}",
                "S1-directory-html",
            )
            continue

        if "company_" not in final_url:
            yield error_record(
                term, "not_found",
                f"Company search for {term!r} did not resolve to a directory "
                f"(landed on {final_url})",
                "S1-directory-html",
            )
            continue

        path = "/" + final_url.split("indotrading.com/", 1)[-1].lstrip("/")
        log.info("Supplier search %r -> %s", term, path)
        async for record in _walk_listing(
            client, path, term, "S1-directory-html", "supplier",
            parse_company_cards, actor_input,
        ):
            record.update(company_directory_ids(record.get("pageUrl") or path))
            yield record


async def mode_category_tree(
    client: IndotradingClient, actor_input: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Every category slug on the site, from one request to /productcatalog."""
    try:
        final_url, body = await client.get_page(
            CATALOG_PATH, referer=SITE_ROOT + "/", allow_home_fallback=True
        )
    except Exception as exc:  # noqa: BLE001
        yield error_record(
            CATALOG_PATH, "fetch_failed", f"{type(exc).__name__}: {exc}",
            "S1-catalog-html",
        )
        return

    categories = parse_category_tree(body)
    if not categories:
        yield error_record(
            CATALOG_PATH, "unexpected_shape",
            "No /jual- links on the catalogue page", "S1-catalog-html",
        )
        return

    log.info("Category tree: %d categories", len(categories))
    for category in categories:
        yield envelope(
            CATALOG_PATH, "S1-catalog-html", "category",
            {**category, "pageUrl": final_url},
        )


MODES: dict[str, Callable[..., AsyncIterator[dict[str, Any]]]] = {
    "categoryProducts": mode_category_products,
    "searchProducts": mode_search_products,
    "productDetail": mode_product_detail,
    "supplierProfile": mode_supplier_profile,
    "supplierDirectory": mode_supplier_directory,
    "searchSuppliers": mode_search_suppliers,
    "categoryTree": mode_category_tree,
}

MODE_REQUIRED_INPUT: dict[str, str] = {
    "categoryProducts": "categories",
    "searchProducts": "searchTerms",
    "productDetail": "productUrls",
    "supplierProfile": "suppliers",
    "supplierDirectory": "categories",
    "searchSuppliers": "searchTerms",
}
