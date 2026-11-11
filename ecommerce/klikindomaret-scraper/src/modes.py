"""Per-mode extraction logic. Each mode is an async generator yielding
dataset-ready records (envelope + raw passthrough)."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from src.client import KlikClient, UpstreamShapeError
from src.constants import (
    DEFAULT_DISTRICT_ID,
    DEFAULT_LAT,
    DEFAULT_LONG,
    DEFAULT_MODE,
    DEFAULT_STORE_CODE,
    EP_BANNERS,
    EP_CATEGORY_META,
    EP_SEARCH_RESULT,
    EP_STORES_SEARCH,
    EP_SUGGESTION,
)
from src.extractor import record

logger = logging.getLogger(__name__)

# search/result pages come in fixed sizes; 15 matches the site, but it accepts
# larger to cut request count. Keep it bounded so a page stays a sane payload.
SEARCH_PAGE_SIZE = 40


class StoreContext:
    """The store-scoped geo parameters every catalog call needs."""

    def __init__(self, store_code: str, latitude: str, longitude: str,
                 district_id: str, mode: str = DEFAULT_MODE) -> None:
        self.store_code = store_code
        self.latitude = latitude
        self.longitude = longitude
        self.district_id = district_id
        self.mode = mode

    def geo(self) -> dict:
        return {
            "storeCode": self.store_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "mode": self.mode,
            "districtId": self.district_id,
        }

    def __repr__(self) -> str:
        return f"StoreContext(store={self.store_code}, district={self.district_id})"


async def resolve_store(
    client: KlikClient,
    store_code: str | None,
    district_id: str | None,
    latitude: str | None,
    longitude: str | None,
) -> StoreContext:
    """Resolve a full store context. If a store_code + coords are supplied, use
    them; otherwise resolve from districtId (or the default district) via the
    stores/search endpoint."""
    if store_code and latitude and longitude:
        return StoreContext(store_code, latitude, longitude,
                            district_id or DEFAULT_DISTRICT_ID)

    did = district_id or DEFAULT_DISTRICT_ID
    try:
        env = await client.get_json(EP_STORES_SEARCH, params={"districtId": did}, page="unpage")
        data = env.get("data") or {}
        sc = data.get("storeCode") or store_code or DEFAULT_STORE_CODE
        lat = str(data.get("latitude") or latitude or DEFAULT_LAT)
        lon = str(data.get("longitude") or longitude or DEFAULT_LONG)
        logger.info("Resolved store %s for district %s.", sc, did)
        return StoreContext(sc, lat, lon, did)
    except UpstreamShapeError as exc:
        logger.warning("Store resolve failed (%s); falling back to defaults.", exc)
        return StoreContext(
            store_code or DEFAULT_STORE_CODE,
            latitude or DEFAULT_LAT,
            longitude or DEFAULT_LONG,
            did,
        )


async def run_stores(
    client: KlikClient, district_ids: list[str]
) -> AsyncIterator[dict]:
    """Emit the resolved store/area info for each requested district."""
    ids = district_ids or [DEFAULT_DISTRICT_ID]
    for did in ids:
        env = await client.get_json(EP_STORES_SEARCH, params={"districtId": did}, page="unpage")
        data = env.get("data")
        if isinstance(data, dict):
            yield record(data, "S1-api", "STORE", did)


def _flatten_categories(nodes: list, parent_path: str = "") -> list[dict]:
    """Depth-first flatten of the category/meta tree into one record per node,
    each keeping its raw fields plus a breadcrumb path."""
    out: list[dict] = []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        name = node.get("name", "")
        path = f"{parent_path} > {name}".strip(" >") if parent_path else name
        children = node.get("categories") or []
        flat = {k: v for k, v in node.items() if k != "categories"}
        flat["_categoryPath"] = path
        flat["_childCount"] = len(children)
        out.append(flat)
        out.extend(_flatten_categories(children, path))
    return out


async def run_category_tree(
    client: KlikClient, store: StoreContext
) -> AsyncIterator[dict]:
    """Emit one record per category node (all levels, flattened)."""
    env = await client.get_json(
        EP_CATEGORY_META,
        params=store.geo(),
        page="/xpress/category",
    )
    data = env.get("data") or []
    for node in _flatten_categories(data if isinstance(data, list) else []):
        yield record(node, "S1-api", "CATEGORY", store.store_code)


async def run_suggestions(
    client: KlikClient, store: StoreContext
) -> AsyncIterator[dict]:
    """Emit the search suggestion payload (popular keywords, recommendations)."""
    env = await client.get_json(
        EP_SUGGESTION,
        params=store.geo(),
        page="/xpress/category",
    )
    data = env.get("data")
    if isinstance(data, dict):
        yield record(data, "S1-api", "SUGGESTIONS", store.store_code)


async def run_promo_banners(
    client: KlikClient, store: StoreContext, max_items: int
) -> AsyncIterator[dict]:
    """Emit each promo banner plus a summary record of the promo-type filters."""
    emitted = 0
    page = 0
    size = 20
    while True:
        params = {
            **store.geo(),
            "page": page,
            "size": size,
            "metaCategoryId": "",
            "promoTypeIds": "",
            "promoTypeSubFilterIds": "",
            "sort": "",
        }
        env = await client.get_json(EP_BANNERS, params=params, page="/xpress/promo")
        data = env.get("data") or {}

        if page == 0:
            extra = data.get("additionalData")
            if isinstance(extra, dict) and extra:
                yield record(extra, "S1-api", "PROMO_FILTERS", store.store_code)

        content = data.get("content") or []
        for item in content:
            if isinstance(item, dict):
                yield record(item, "S1-api", "BANNER", store.store_code)
                emitted += 1
                if max_items and emitted >= max_items:
                    return

        if data.get("last", True) or not content:
            return
        page += 1


async def run_product_search(
    client: KlikClient,
    store: StoreContext,
    queries: list[dict],
    max_items: int,
) -> AsyncIterator[dict]:
    """Product listing by keyword or categoryId, paged. Needs cf_clearance."""
    for q in queries:
        label = q["label"]
        emitted = 0
        page = 0
        while True:
            params = {
                **store.geo(),
                "isUserFiltered": "false",
                "page": page,
                "size": SEARCH_PAGE_SIZE,
            }
            if q["type"] == "keyword":
                params["key"] = q["value"]
            else:  # category
                params["categoryId"] = q["value"]

            env = await client.get_json(
                EP_SEARCH_RESULT, params=params, page="/search", needs_clearance=True
            )
            data = env.get("data") or {}
            content = data.get("content") or []
            total_pages = data.get("totalPages", 0)

            for item in content:
                if isinstance(item, dict):
                    payload = dict(item)
                    payload["_query"] = label
                    payload["_queryType"] = q["type"]
                    yield record(payload, "S1-api", "PRODUCT", label)
                    emitted += 1
                    if max_items and emitted >= max_items:
                        break

            if max_items and emitted >= max_items:
                logger.info("Query %r hit maxItems=%d.", label, max_items)
                break
            if data.get("last", True) or not content or page + 1 >= total_pages:
                break
            page += 1

        logger.info("Query %r: %d product(s).", label, emitted)
