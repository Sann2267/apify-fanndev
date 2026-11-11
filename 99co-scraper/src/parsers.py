"""Shaping 99.co pages into dataset records.

Three extraction layers, one per surface, chosen by stability:

  Indonesia   __NEXT_DATA__ -> props.pageProps.data. Already structured JSON,
              so listings pass through essentially verbatim.

  Singapore   schema.org JSON-LD for the spine (canonical URL, listing id and
              the true result total) merged with the RSC flight payload for
              the rich fields. The ItemList alone carries only url/name/type;
              the RSC alone has no stable anchor to the canonical URL. Joined
              on listing_id they give a complete record, and if the RSC shape
              ever moves the JSON-LD half still yields a usable row.

  API         plain JSON, passed through.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterator

log = logging.getLogger("ninetynine.parsers")

RE_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
RE_LD_JSON = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)
# RSC flight rows arrive as self.__next_f.push([1, "<json-string-escaped>"]).
RE_RSC_CHUNK = re.compile(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)')
# The listing id is the last dash-separated token of a Singapore listing URL.
RE_SG_LISTING_ID = re.compile(r"-([A-Za-z0-9]{20,})$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(
    input_value: str,
    source: str,
    record_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }
    if payload:
        rec.update(payload)
    return rec


def error_record(
    input_value: str, error: str, detail: str = "", source: str = "none"
) -> dict[str, Any]:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": "error",
        "_error": error,
        "_errorDetail": detail,
    }


class UnexpectedShape(Exception):
    """The page rendered but did not carry the payload it is supposed to."""


# -- Indonesia -------------------------------------------------------------


def next_data(html: str) -> dict[str, Any]:
    m = RE_NEXT_DATA.search(html)
    if not m:
        raise UnexpectedShape("no __NEXT_DATA__ script on the page")
    try:
        return json.loads(m.group(1))
    except ValueError as exc:
        raise UnexpectedShape(f"__NEXT_DATA__ is not valid JSON: {exc}") from exc


def id_page_data(html: str) -> dict[str, Any]:
    d = next_data(html)
    props = (d.get("props") or {}).get("pageProps") or {}
    data = props.get("data")
    if not isinstance(data, dict):
        raise UnexpectedShape("pageProps.data missing or not an object")
    return data


def id_is_404(html: str) -> bool:
    """The Indonesian app renders its 404 as a normal 200-shaped page."""
    try:
        d = next_data(html)
    except UnexpectedShape:
        return False
    return (d.get("page") or "") == "/404"


def parse_id_search(html: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Listings and pagination from an Indonesian search page.

    The listings array is a list of GROUPS, not listings: each group has a
    group_type_name of "primary" (developer and project placements) or
    "secondary" (ordinary listings), and they are interleaved. Both are
    emitted with groupType attached so a caller can drop placements, because
    silently keeping them would inflate a market count with paid inventory.
    """
    data = id_page_data(html)
    out: list[dict[str, Any]] = []
    for group in data.get("listings") or []:
        if not isinstance(group, dict):
            continue
        gtype = group.get("group_type_name")
        for item in group.get("data") or []:
            if isinstance(item, dict):
                out.append({"groupType": gtype, **item})

    pagination = data.get("pagination") or {}
    meta = {
        "page": pagination.get("page"),
        "pageSize": pagination.get("page_size"),
        "totalCount": pagination.get("count"),
        "totalPagesReported": pagination.get("total_page"),
        "locationInfo": data.get("location_info"),
        "appliedFilter": data.get("filter"),
    }
    return out, meta


def parse_id_detail(html: str) -> dict[str, Any]:
    """A single Indonesian listing, plus the extras only the detail page has."""
    d = next_data(html)
    props = (d.get("props") or {}).get("pageProps") or {}
    data = props.get("data")
    if not isinstance(data, dict) or not data.get("id"):
        raise UnexpectedShape("pageProps.data carries no listing id")

    record = dict(data)
    # Surfaces that exist only on the detail page. Kept under their own keys
    # rather than merged in, so the listing body stays byte-comparable with
    # the same listing as it appears in search results.
    for key, out_key in (
        ("poiData", "poiData"),
        ("qnas", "questionsAndAnswers"),
        ("priceInsightTrendMarket", "priceInsightTrendMarket"),
        ("venueData", "venueData"),
        ("internal_links", "internalLinks"),
    ):
        if props.get(key) is not None:
            record[out_key] = props[key]
    return record


def parse_id_locations(html: str) -> list[dict[str, Any]]:
    """Popular location facets, flattened parent-then-children.

    These are the seeds for working around the 9-page ceiling: each location
    is a narrower query whose own first 9 pages are reachable.
    """
    data = id_page_data(html)
    out: list[dict[str, Any]] = []
    for parent in data.get("popular_locations_filter") or []:
        if not isinstance(parent, dict):
            continue
        children = parent.get("children") or []
        out.append(
            {
                "locationId": parent.get("location_id"),
                "locationName": parent.get("location_name"),
                "locationTypeId": parent.get("location_type_id"),
                "urlSlug": parent.get("url_slug"),
                "parentSlug": None,
                "childCount": len(children),
            }
        )
        for child in children:
            if isinstance(child, dict):
                out.append(
                    {
                        "locationId": child.get("location_id"),
                        "locationName": child.get("location_name"),
                        "locationTypeId": child.get("location_type_id"),
                        "urlSlug": child.get("url_slug"),
                        "parentSlug": parent.get("url_slug"),
                        "childCount": 0,
                    }
                )
    return out


# -- Singapore -------------------------------------------------------------


def _ld_blocks(html: str) -> Iterator[Any]:
    for raw in RE_LD_JSON.findall(html):
        try:
            yield json.loads(raw)
        except ValueError:
            log.warning("Unparseable ld+json block (%d chars)", len(raw))


def _ld_nodes(html: str) -> Iterator[dict[str, Any]]:
    """Every schema.org node, flattening both @graph and top-level arrays."""
    for block in _ld_blocks(html):
        items = block if isinstance(block, list) else [block]
        for item in items:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                for node in graph:
                    if isinstance(node, dict):
                        yield node
            else:
                yield item


def decode_rsc(html: str) -> str:
    """Concatenate and unescape the RSC flight chunks.

    Each chunk is a JSON string literal, so it is decoded by wrapping it back
    in quotes and letting json handle the escapes. Chunks that fail to decode
    are skipped rather than aborting: the flight stream is split at arbitrary
    byte offsets and a trailing partial chunk is normal.
    """
    parts: list[str] = []
    for chunk in RE_RSC_CHUNK.findall(html):
        try:
            parts.append(json.loads('"' + chunk + '"'))
        except ValueError:
            continue
    return "".join(parts)


def _rsc_listing_objects(blob: str) -> dict[str, dict[str, Any]]:
    """Pull the listing objects out of the decoded flight stream.

    RSC encodes shared values as "$N" pointers into other rows, so a listing's
    price arrives as {"price": "$41"} with row 41 holding the real object.
    Rather than implement the whole reference machine, this walks the rows
    once, keeps every row that parses as an object, and then resolves the
    one-level "$N" pointers that listings actually use -- which covers price,
    psf, beds, bathrooms and floor area.
    """
    rows: dict[str, Any] = {}
    for m in re.finditer(r'(?m)^([0-9a-f]+):(\{.*|\[.*)$', blob):
        key, raw = m.group(1), m.group(2)
        try:
            rows[key] = json.loads(raw)
        except ValueError:
            continue

    def resolve(value: Any, depth: int = 0) -> Any:
        if depth > 3:
            return value
        if isinstance(value, str) and value.startswith("$") and value[1:] in rows:
            return resolve(rows[value[1:]], depth + 1)
        if isinstance(value, dict):
            return {k: resolve(v, depth + 1) for k, v in value.items()}
        if isinstance(value, list):
            return [resolve(v, depth + 1) for v in value]
        return value

    listings: dict[str, dict[str, Any]] = {}
    for row in rows.values():
        if isinstance(row, dict) and row.get("listing_id"):
            resolved = resolve(row)
            listings[str(resolved.get("listing_id"))] = resolved
    return listings


def parse_sg_search(html: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Listings and total from a Singapore search page.

    JSON-LD supplies the canonical URL and the honest result total; the RSC
    supplies price, beds, area, coordinates and agent. They are joined on the
    listing id, which appears in the URL as its final dash-separated token.
    """
    item_list: dict[str, Any] = {}
    for node in _ld_nodes(html):
        if node.get("@type") == "ItemList":
            item_list = node
            break

    rsc = _rsc_listing_objects(decode_rsc(html))

    out: list[dict[str, Any]] = []
    for element in item_list.get("itemListElement") or []:
        if not isinstance(element, dict):
            continue
        item = element.get("item") or {}
        url = element.get("url") or item.get("url")
        if not url:
            continue
        m = RE_SG_LISTING_ID.search(str(url))
        listing_id = m.group(1) if m else None
        extra = item.get("additionalProperty") or {}
        record: dict[str, Any] = {
            "listingId": listing_id,
            "listingUrl": url,
            "address": item.get("name"),
            "position": element.get("position"),
            "propertyTypeLabel": (
                extra.get("value") if isinstance(extra, dict) else None
            ),
        }
        if listing_id and listing_id in rsc:
            # Raw passthrough of the flight object alongside the JSON-LD spine.
            record["listing"] = rsc[listing_id]
        else:
            record["_warning"] = "rsc_listing_not_matched"
        out.append(record)

    # A page whose JSON-LD is missing still has flight data; emit those rather
    # than returning nothing, and say which half was used.
    if not out and rsc:
        for listing_id, obj in rsc.items():
            out.append(
                {
                    "listingId": listing_id,
                    "listingUrl": None,
                    "listing": obj,
                    "_warning": "jsonld_itemlist_missing",
                }
            )

    meta = {
        "totalCount": item_list.get("numberOfItems"),
        "listName": item_list.get("name"),
        "rscListingCount": len(rsc),
    }
    return out, meta


def _node_types(node: dict[str, Any]) -> list[str]:
    """schema.org @type, which may be a string or a list.

    99.co's listing pages use the list form (["Product", "Room"]), so keying
    a lookup on the string form alone silently drops the richest node on the
    page -- which is exactly what it did until this was fixed.
    """
    t = node.get("@type")
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return [x for x in t if isinstance(x, str)]
    return []


def parse_sg_detail(html: str, page_url: str) -> dict[str, Any]:
    """A single Singapore listing page.

    Built from schema.org rather than the flight stream: a detail page carries
    a fully populated Product/Room node -- sku, description, floorSize, geo,
    address, offers -- and, unlike the search page, no listing_id-bearing RSC
    object at all. The RSC is still decoded and attached when something is
    there, but it is enrichment, not the source of truth.
    """
    by_type: dict[str, dict[str, Any]] = {}
    for node in _ld_nodes(html):
        for t in _node_types(node):
            by_type.setdefault(t, node)

    product = by_type.get("Product") or {}
    real_estate = by_type.get("RealEstateListing") or {}
    web_page = by_type.get("WebPage") or {}

    # additionalProperty is a list of {name, value} pairs; flatten it while
    # keeping the original list, so a new property widens the record instead
    # of being lost.
    extra = product.get("additionalProperty")
    attributes: dict[str, Any] = {}
    if isinstance(extra, list):
        for item in extra:
            if isinstance(item, dict) and item.get("name") is not None:
                attributes[str(item["name"])] = item.get("value")
    elif isinstance(extra, dict) and extra.get("name") is not None:
        attributes[str(extra["name"])] = extra.get("value")

    m = RE_SG_LISTING_ID.search(page_url)
    listing_id = product.get("sku") or (m.group(1) if m else None)

    rsc = _rsc_listing_objects(decode_rsc(html))
    listing = rsc.get(str(listing_id)) if listing_id else None
    if listing is None and len(rsc) == 1:
        listing = next(iter(rsc.values()))

    geo = product.get("geo") or {}
    address = product.get("address") or {}

    record: dict[str, Any] = {
        "listingId": listing_id,
        "listingUrl": product.get("url") or page_url,
        "name": product.get("name") or real_estate.get("name"),
        "description": product.get("description"),
        "imageUrl": product.get("image"),
        "floorSize": product.get("floorSize"),
        "offers": product.get("offers"),
        "address": address,
        "addressLocality": address.get("addressLocality"),
        "addressRegion": address.get("addressRegion"),
        "latitude": geo.get("latitude"),
        "longitude": geo.get("longitude"),
        "attributes": attributes or None,
        "additionalProperty": extra,
        "datePublished": web_page.get("datePublished"),
        "dateModified": web_page.get("dateModified"),
        "breadcrumb": (by_type.get("BreadcrumbList") or {}).get("itemListElement"),
        "schemaTypes": sorted(by_type),
    }
    if listing is not None:
        record["listing"] = listing

    if not any((record["name"], record["description"], listing)):
        raise UnexpectedShape(
            "page carried neither a schema.org Product/RealEstateListing node "
            "nor an RSC listing object"
        )
    return record


def parse_hdb_median(payload: Any) -> list[dict[str, Any]]:
    """Flatten the HDB median resale table into one row per town.

    The API returns a headers array plus row arrays, so the column meaning
    lives in a separate structure from the values. Rows are zipped back onto
    their header titles here; the raw pair is kept too, because a new column
    should widen the record rather than silently shift every value left.
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise UnexpectedShape("HDB median payload has no data object")
    headers = [h.get("title") for h in (data.get("headers") or []) if isinstance(h, dict)]
    rows = data.get("rows") or data.get("data") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        values = row if isinstance(row, list) else row.get("values") if isinstance(row, dict) else None
        if not isinstance(values, list):
            continue
        cells = {}
        for idx, header in enumerate(headers):
            if header is not None and idx < len(values):
                cells[header] = values[idx]
        out.append({"columns": headers, "values": values, **cells})
    if not out:
        raise UnexpectedShape(
            f"HDB median payload had headers {headers!r} but no parseable rows"
        )
    return out
