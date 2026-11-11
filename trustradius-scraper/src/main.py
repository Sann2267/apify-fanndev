"""Mode dispatch for the TrustRadius Actor.

Six modes, one host, one transport:

* ``categoryProducts`` -- the ranked product list of a category, 25 per page via
                          ``?f=<offset>``, optional filters, and a fan-out that
                          reaches past the 1000-offset ceiling.
* ``products``         -- one product in full: rating + feature ratings, pricing
                          editions, awards, pros/cons, competitors, install base
                          by industry (HG Insights); optionally the pricing page
                          (reviewer price quotes, support, deployment).
* ``reviews``          -- every review of a product, 10 per page via ``?page=N``,
                          optionally stopping at a date and optionally enriched
                          with the full questionnaire of each review.
* ``alternatives``     -- the curated competitor list plus TrustRadius's
                          alternatives by company-size segment.
* ``compare``          -- a head-to-head comparison page: per-feature scores with
                          winners, pricing editions, buy-again insights.
* ``categories``       -- the whole category tree, so users can find valid slugs.
"""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse as up

from apify import Actor

from src.client import Blocked, NotFound, TrustRadiusClient
from src.constants import (
    BASE,
    CATEGORY_OFFSET_CEILING,
    CATEGORY_PAGE_SIZE,
    DEEP_FANOUT,
    MODES,
    REVIEWS_PAGE_SIZE,
    ROBOTS_DISALLOWED_PREFIXES,
)
from src.extractor import (
    UnexpectedShape,
    category_product_record,
    now_iso,
    parse_categories,
    parse_category_page,
    parse_compare,
    parse_competitors,
    parse_pricing_page,
    parse_product_page,
    parse_review_detail,
    parse_reviews_page,
    slim_product,
)
from src.flight import FlightError
from src.input_errors import input_error

log = logging.getLogger(__name__)

DEFAULT_PRODUCTS = ["hubspot-crm"]
DEFAULT_CATEGORIES = ["crm"]
DEFAULT_COMPARISONS = ["hubspot-crm-vs-pipedrive"]


# -- input normalisation ---------------------------------------------------------


def _path_of(value: str) -> str:
    value = (value or "").strip()
    if value.startswith("http"):
        parsed = up.urlparse(value)
        if "trustradius.com" not in parsed.netloc:
            raise ValueError(f"{value!r} is not a trustradius.com URL")
        return parsed.path
    return value


def _check_robots(path: str) -> None:
    for prefix in ROBOTS_DISALLOWED_PREFIXES:
        if path.startswith(prefix):
            raise ValueError(f"{path} is disallowed by trustradius.com/robots.txt")


def product_slug(raw: str) -> str:
    """'hubspot-crm', '/products/hubspot-crm/reviews', or a full URL -> slug."""
    path = _path_of(raw)
    if not path:
        raise ValueError("empty product")
    _check_robots(path)
    path = path if path.startswith("/") else "/" + path
    m = re.match(r"^/products/([^/?#]+)", path)
    if m:
        return m.group(1)
    if "/" in path.strip("/"):
        raise ValueError(f"{raw!r} is not a product -- expected a slug or /products/<slug>")
    return path.strip("/")


def category_slug(raw: str) -> str:
    """'crm', '/crm', '/categories/crm' or a full URL -> slug. The site serves
    each category at both /<slug> and /categories/<slug> (canonical)."""
    path = _path_of(raw)
    if not path:
        raise ValueError("empty category")
    _check_robots(path)
    parts = [p for p in path.split("/") if p]
    if parts and parts[0] == "categories":
        parts = parts[1:]
    if len(parts) != 1:
        raise ValueError(f"{raw!r} is not a category -- expected a slug such as 'crm'")
    return parts[0]


def comparison_slug(raw: str) -> str:
    """'a-vs-b', 'a vs b', 'a,b', '/compare-products/a-vs-b' or a URL -> 'a-vs-b'."""
    path = _path_of(raw)
    if path.startswith("/compare-products/"):
        return path.split("/compare-products/", 1)[1].strip("/")
    for sep in (",", " vs ", " VS ", " Vs "):
        if sep in path:
            parts = [product_slug(p) for p in path.split(sep) if p.strip()]
            if len(parts) < 2:
                break
            return "-vs-".join(parts)
    if "-vs-" in path:
        return path.strip("/")
    raise ValueError(f"{raw!r} is not a comparison -- use 'product-a-vs-product-b' or 'product-a, product-b'")


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = re.split(r"[\n]", value)
    else:
        items = []
        for entry in value:
            items.append(str(entry.get("url") or entry.get("value") or "") if isinstance(entry, dict) else str(entry))
    return [i.strip() for i in items if i and i.strip()]


NOT_FOUND_MARKER = 'E{"digest":"NEXT_NOT_FOUND"}'


def parse_or_404(parser, stream: str, what: str):
    """With ``RSC: 1`` a missing page answers **200**, not 404, carrying an
    ``E{"digest":"NEXT_NOT_FOUND"}`` row. That row also appears on valid pages
    (an empty parallel-route slot on /crm), so it only means "not found" when
    the data this parser needs is absent as well."""
    try:
        return parser(stream)
    except (UnexpectedShape, FlightError) as exc:
        if NOT_FOUND_MARKER in stream:
            raise NotFound(f"no such {what} on trustradius.com") from exc
        raise


def envelope(input_value: str, source: str, record_type: str, payload: dict) -> dict:
    return {"_input": input_value, "_source": source, "_scrapedAt": now_iso(), "recordType": record_type, **payload}


def error_record(input_value: str, kind: str, detail: str) -> dict:
    return {"_input": input_value, "_source": "none", "_scrapedAt": now_iso(), "recordType": "ERROR",
            "_error": kind, "_errorDetail": detail[:500]}


# -- runner ------------------------------------------------------------------


class Runner:
    def __init__(self, client: TrustRadiusClient, cfg: dict):
        self.client = client
        self.cfg = cfg
        self.pushed = 0
        self.errors = 0
        self._stop = False

    async def push(self, records: list[dict]) -> None:
        if not records:
            return
        await Actor.push_data(records)
        self.pushed += sum(1 for r in records if r.get("recordType") != "ERROR")

    async def fail(self, input_value: str, exc: Exception) -> None:
        kind = {
            NotFound: "not_found",
            Blocked: "blocked",
            UnexpectedShape: "unexpected_shape",
            FlightError: "unexpected_shape",
            ValueError: "invalid_input",
        }.get(type(exc), "exception")
        self.errors += 1
        Actor.log.warning(f"{input_value}: {kind} -- {exc}")
        await Actor.push_data(error_record(input_value, kind, f"{type(exc).__name__}: {exc}"))

    # -- categories --------------------------------------------------------

    async def categories(self) -> None:
        stream = await self.client.get_flight(f"{BASE}/categories")
        recs = parse_categories(stream)
        wanted = [s.lower() for s in as_list(self.cfg.get("categories"))]
        if wanted and self.cfg.get("filterCategoryTree"):
            recs = [r for r in recs if r["slug"] in wanted or any(w in (r["name"] or "").lower() for w in wanted)]
        await self.push([envelope("categories", "tr-rsc-categories", "CATEGORY", r) for r in recs])
        Actor.log.info(f"categories: {len(recs)} categories")

    # -- category listing ----------------------------------------------------

    def _category_url(self, slug: str, filters: dict, offset: int) -> str:
        params = dict(filters)
        if offset:
            params["f"] = str(offset)
        query = up.urlencode(params)
        return f"{BASE}/categories/{slug}" + (f"?{query}" if query else "")

    async def _walk_category(self, raw: str, slug: str, filters: dict, limit: int, seen: set, emitted: list) -> dict:
        """Page one ordering/slice of a category until ``limit``, the end, or
        the offset ceiling. Returns the first page's meta."""
        offset, first_meta = 0, None
        while offset < CATEGORY_OFFSET_CEILING and len(emitted) < limit:
            stream = await self.client.get_flight(self._category_url(slug, filters, offset))
            meta, products, category = parse_category_page(stream)
            if first_meta is None:
                first_meta = meta
                if meta.get("missing"):
                    if NOT_FOUND_MARKER in stream and category is None:
                        raise NotFound(f"no such category {slug!r} on trustradius.com")
                    raise UnexpectedShape(f"category page for {slug!r} has no product list")
            if not products:
                break
            batch = []
            for i, product in enumerate(products):
                key = product.get("_id") or product.get("slug")
                if key in seen:
                    continue
                seen.add(key)
                rank = offset + i + 1 if not filters else None
                rec = category_product_record(product, category, rank, filters)
                if filters:
                    rec["filterRank"] = offset + i + 1
                batch.append(envelope(raw, "tr-rsc-category", "PRODUCT", rec))
                if len(emitted) + len(batch) >= limit:
                    break
            emitted.extend(batch)
            await self.push(batch)
            total = meta.get("total") or 0
            offset += CATEGORY_PAGE_SIZE
            if total and offset >= total:
                break
        return first_meta or {}

    async def category_products(self, raw: str) -> None:
        slug = category_slug(raw)
        limit = int(self.cfg.get("maxItems") or 100)
        filters = {}
        if self.cfg.get("companySize") and self.cfg["companySize"] != "any":
            filters["company-size"] = self.cfg["companySize"]
        if self.cfg.get("topRatedOnly"):
            filters["top"] = "true"
        if self.cfg.get("hasPricingOnly"):
            filters["hp"] = "true"
        if self.cfg.get("freeOptionOnly"):
            filters["free-pricing"] = "true"
        if self.cfg.get("operatingSystem") and self.cfg["operatingSystem"] != "any":
            filters["os"] = self.cfg["operatingSystem"]

        seen: set = set()
        emitted: list = []
        meta = await self._walk_category(raw, slug, filters, limit, seen, emitted)
        total = meta.get("total") or 0
        # Past the ceiling: every other ordering/slice sees a different first
        # 1000, so walking them and deduping by product id reaches further.
        if (
            self.cfg.get("deepPagination")
            and not filters
            and len(emitted) < limit
            and total > CATEGORY_OFFSET_CEILING
        ):
            Actor.log.info(f"{slug}: {total} listed but offsets stop at {CATEGORY_OFFSET_CEILING}; fanning out")
            for extra in DEEP_FANOUT:
                if len(emitted) >= limit:
                    break
                before = len(emitted)
                await self._walk_category(raw, slug, extra, limit, seen, emitted)
                Actor.log.info(f"{slug}: fan-out {extra} added {len(emitted) - before} new products")
        Actor.log.info(f"{slug}: {len(emitted)} products (category lists {total})")

    # -- product -----------------------------------------------------------------

    async def product(self, raw: str) -> None:
        slug = product_slug(raw)
        product = parse_or_404(parse_product_page, await self.client.get_flight(f"{BASE}/products/{slug}"), f"product {slug!r}")
        rec = {"slug": product.get("slug") or slug, "url": f"{BASE}/products/{slug}", **product}
        if self.cfg.get("includePricing", True):
            try:
                rec["pricingPage"] = parse_or_404(parse_pricing_page, await self.client.get_flight(f"{BASE}/products/{slug}/pricing"), "pricing page")
            except (NotFound, UnexpectedShape) as exc:
                rec["pricingPage"] = None
                rec["_warning"] = f"pricing page: {exc}"
        await self.push([envelope(raw, "tr-rsc-product", "PRODUCT_DETAILS", rec)])

    # -- reviews -----------------------------------------------------------------

    async def reviews(self, raw: str) -> None:
        slug = product_slug(raw)
        limit = int(self.cfg.get("maxItems") or 100)
        since = (self.cfg.get("reviewsNewerThan") or "").strip() or None
        details = bool(self.cfg.get("includeReviewDetails"))
        sem = asyncio.Semaphore(int(self.cfg.get("maxConcurrency") or 3))
        count, page, total, fetched = 0, 1, None, 0

        async def enrich(rec: dict) -> dict:
            if not details or not rec.get("slug"):
                return rec
            async with sem:
                try:
                    rec["details"] = parse_review_detail(await self.client.get_html(f"{BASE}/reviews/{rec['slug']}"))
                except (NotFound, Blocked, UnexpectedShape, ValueError) as exc:
                    rec["details"] = None
                    rec["_warning"] = f"review details: {type(exc).__name__}: {exc}"[:300]
            return rec

        while count < limit:
            stream = await self.client.get_flight(f"{BASE}/products/{slug}/reviews" + (f"?page={page}" if page > 1 else ""))
            fetched += 1
            header, reviews = parse_reviews_page(stream)
            if page == 1:
                total = header.get("totalReviews")
                if header.get("product") is None and not reviews:
                    if NOT_FOUND_MARKER in stream:
                        raise NotFound(f"no such product {slug!r} on trustradius.com")
                    raise UnexpectedShape(f"reviews page for {slug!r} carries neither a product nor reviews")
                Actor.log.info(f"{slug}: {total} reviews listed")
            if not reviews:
                break
            product = header.get("product") or {"slug": slug}
            keep, stop = [], False
            for r in reviews:
                if since and r.get("datePublished") and r["datePublished"][:10] < since:
                    # Newest first, but one page can be locally out of order
                    # (publish date != submit date), so finish the page.
                    stop = True
                    continue
                keep.append(r)
            keep = keep[: limit - count]
            enriched = await asyncio.gather(*(enrich(r) for r in keep))
            await self.push([
                envelope(raw, "tr-rsc-reviews" + ("+legacy-detail" if details else ""), "REVIEW",
                         {"productSlug": product.get("slug"), "productName": product.get("name"),
                          "reviewPage": page, **r})
                for r in enriched
            ])
            count += len(keep)
            if stop or count >= limit or len(reviews) < REVIEWS_PAGE_SIZE:
                break
            if total and page * REVIEWS_PAGE_SIZE >= total:
                break
            page += 1
        Actor.log.info(f"{slug}: {count} reviews emitted from {fetched} page(s)")

    # -- alternatives --------------------------------------------------------------

    async def alternatives(self, raw: str) -> None:
        slug = product_slug(raw)
        curated, segments = parse_competitors(await self.client.get_html(f"{BASE}/products/{slug}/competitors"))
        merged: dict[str, dict] = {}
        order: list[str] = []

        def add(p: dict, list_name: str, pos: int):
            key = p.get("slug") or p.get("_id")
            if not key or key == slug:
                return
            if key not in merged:
                merged[key] = {"forProduct": slug, **slim_product(p), "lists": {}}
                order.append(key)
            merged[key]["lists"][list_name] = pos

        for i, p in enumerate(curated, 1):
            add(p, "competitors", i)
        for seg_name, items in (segments or {}).items():
            for i, p in enumerate(items or [], 1):
                if isinstance(p, dict):
                    add(p, f"alternatives_{seg_name}", i)
        await self.push([envelope(raw, "tr-legacy-competitors", "ALTERNATIVE", merged[k]) for k in order])
        Actor.log.info(f"{slug}: {len(order)} alternatives")

    # -- compare ---------------------------------------------------------------------

    async def compare(self, raw: str) -> None:
        cslug = comparison_slug(raw)
        data = parse_or_404(parse_compare, await self.client.get_flight(f"{BASE}/compare-products/{cslug}"), f"comparison {cslug!r}")
        await self.push([envelope(raw, "tr-rsc-compare", "COMPARISON",
                                  {"comparison": cslug, "url": f"{BASE}/compare-products/{cslug}", **data})])


# -- entry point -------------------------------------------------------------------


async def main() -> None:
    async with Actor:
        cfg = await Actor.get_input() or {}
        mode = cfg.get("mode") or "products"
        if mode not in MODES:
            raise input_error(f"unknown mode {mode!r}; expected one of {MODES}")

        proxy_cfg = None
        proxy_input = cfg.get("proxyConfiguration")
        if proxy_input and (proxy_input.get("useApifyProxy") or proxy_input.get("proxyUrls")):
            try:
                proxy_cfg = await Actor.create_proxy_configuration(actor_proxy_input=proxy_input)
            except Exception as exc:  # noqa: BLE001 -- measured: raises ValueError (exit 91, 0 records) when no proxy password is available
                Actor.log.warning(f"proxy unavailable ({exc!s:.120}); continuing without a proxy")
                proxy_cfg = None
            if proxy_cfg is None:
                Actor.log.warning("proxy configuration could not be created; continuing without a proxy")

        counter = {"n": 0}

        async def new_proxy() -> str | None:
            if proxy_cfg is None:
                return None
            counter["n"] += 1
            # A new session id = a new exit IP; the client asks for one on
            # every Cloudflare challenge.
            return await proxy_cfg.new_url(session_id=f"tr{counter['n']}")

        client = TrustRadiusClient(proxy_factory=new_proxy)
        runner = Runner(client, cfg)
        try:
            if mode == "categories":
                try:
                    await runner.categories()
                except Exception as exc:  # noqa: BLE001 -- surfaced as an ERROR record
                    await runner.fail("categories", exc)
            else:
                key, default, handler = {
                    "categoryProducts": ("categories", DEFAULT_CATEGORIES, runner.category_products),
                    "products": ("products", DEFAULT_PRODUCTS, runner.product),
                    "reviews": ("products", DEFAULT_PRODUCTS, runner.reviews),
                    "alternatives": ("products", DEFAULT_PRODUCTS, runner.alternatives),
                    "compare": ("comparisons", DEFAULT_COMPARISONS, runner.compare),
                }[mode]
                inputs = as_list(cfg.get(key)) or default
                # Reviews paginate sequentially per product and fan out their
                # detail fetches, so inputs themselves run with lower concurrency.
                width = 1 if mode == "reviews" else int(cfg.get("maxConcurrency") or 3)
                sem = asyncio.Semaphore(max(1, width))

                async def one(item: str):
                    async with sem:
                        try:
                            await handler(item)
                        except Exception as exc:  # noqa: BLE001 -- surfaced as an ERROR record
                            await runner.fail(item, exc)

                await asyncio.gather(*(one(i) for i in inputs))
        finally:
            await client.close()
        Actor.log.info(
            f"done: mode={mode} records={runner.pushed} errors={runner.errors} "
            f"requests={client.requests} challenges={client.challenges} "
            f"MB={client.bytes / 1e6:.1f} tls={client.winning_profile}"
        )
        if runner.pushed == 0 and runner.errors:
            await Actor.fail(status_message=f"no records; {runner.errors} input(s) failed -- see ERROR records")
