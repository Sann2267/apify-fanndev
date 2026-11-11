"""Query construction and response shaping.

Two jobs live here, and the first one is the one that decides whether this
actor returns the right cars at all.

**Building the search URL.** mobile.de accepts several URL dialects and
silently ignores most of them. Probed on 2026-09-22, all returning HTTP 200:

    /fahrzeuge/search.html?vc=Car&ms=3500;20;;      ->     2,250 rows  (correct)
    /auto/bmw-3er-reihe.html                        ->    27,157 rows  (correct, fixed filter)
    /fahrzeuge/search.html?makeModelVariant1.makeId=3500
                                                    -> 1,574,052 rows  (FILTER DROPPED)
    /s/auto/bmw/                                    -> 1,574,052 rows  (FILTER DROPPED)

The last two are the whole car database wearing a BMW-shaped URL. Nothing in
the response says the filter was ignored -- but the API does echo back a
`sanitizedFilterParamsString` listing the filters it actually applied, and
that is the ground truth this module checks against.

**Flattening the item list.** `searchResults.items` is not a list of
listings. It mixes four `type` values, one of which nests another list:

    "ad"                organic listing
    "topAd"             paid placement, same shape
    "page1Ads"          CONTAINER -- its own .items holds more listings
    "inlineAdvertising" display slot, carries no vehicle at all

A naive ``[i["id"] for i in items]`` raises KeyError on the fourth and drops
every listing inside the third.
"""

from __future__ import annotations

import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Iterable

from .constants import (
    DECOY_PARAMS,
    FILTER_PARAMS,
    MAX_PAGE_SIZE,
    VEHICLE_CATEGORIES,
)

log = logging.getLogger("mobilede.parsers")

SEARCH_PATH = "/fahrzeuge/search.html"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- query building ---------------------------------------------------------


class FilterError(ValueError):
    """The requested filters cannot be expressed against this API."""


def build_search_path(filters: dict[str, Any]) -> str:
    """Turn a dict of mobile.de short filter codes into a root-relative path."""
    clean: dict[str, Any] = {}
    for key, value in filters.items():
        if value is None or value == "":
            continue
        if key not in FILTER_PARAMS:
            raise FilterError(
                f"{key!r} is not a mobile.de filter parameter. "
                f"Known codes: {', '.join(sorted(FILTER_PARAMS))}"
            )
        clean[key] = value
    query = urllib.parse.urlencode(clean, quote_via=urllib.parse.quote, safe=";:,")
    return f"{SEARCH_PATH}?{query}" if query else SEARCH_PATH


def normalise_page_url(raw: str) -> str:
    """Reduce any user-supplied mobile.de URL to the root-relative path the API wants.

    An absolute ``https://www.mobile.de/...`` URL is rejected by the API with
    400 "SVC API request failed" -- the service resolves the value against
    suchen.mobile.de, so it has to arrive as a path.
    """
    raw = (raw or "").strip()
    if not raw:
        raise FilterError("Empty URL.")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme and parsed.netloc:
        if "mobile.de" not in parsed.netloc:
            raise FilterError(f"Not a mobile.de URL: {raw}")
        path = parsed.path or "/"
        return f"{path}?{parsed.query}" if parsed.query else path
    return raw if raw.startswith("/") else f"/{raw}"


TELEMETRY_PARAMS = ("ref", "refId", "ps", "psz")


def is_canonical_search_path(page_path: str) -> bool:
    """Is this the one URL dialect that honours the paging parameters?"""
    return urllib.parse.urlsplit(page_path).path.rstrip("/") == SEARCH_PATH.rstrip("/")


def rebuild_canonical_path(sanitized: str | None) -> str | None:
    """Turn the API's echoed filter string back into a paginable search path.

    Needed because mobile.de's SEO landing pages (`/auto/bmw-3er-reihe.html`)
    ignore `psz` AND `ps` outright: they serve a fixed 24 rows, and `ps=200`
    comes back 20/24 duplicate. A pasted SEO URL is therefore un-walkable as
    given -- a pager would trickle ~4 new rows per request and never finish.

    The escape hatch is that the API tells us the filters it applied, in the
    canonical short-code form:

        /auto/bmw-3er-reihe.html
          -> dam=false&ms=3500;;21;&od=up&s=Car&sb=rel&vc=Car

    Replayed against `/fahrzeuge/search.html` that yields the identical
    27,160-row result set and pages properly at 204 rows per request.
    """
    if not sanitized:
        return None
    pairs = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(sanitized, keep_blank_values=True)
        if k not in TELEMETRY_PARAMS
    ]
    if not pairs:
        return None
    query = urllib.parse.urlencode(pairs, quote_via=urllib.parse.quote, safe=";:,")
    return f"{SEARCH_PATH}?{query}"


def describe_dropped_filters(page_path: str, sanitized: str | None) -> list[str]:
    """Name the filters mobile.de threw away, comparing what was sent to what it echoed.

    `sanitizedFilterParamsString` is the API's own statement of the filters it
    applied. Anything sent that is missing from it had no effect on the result
    set, which on this API is silent -- the run still returns 200 and a full
    page of cars, just the wrong ones.
    """
    sent = urllib.parse.parse_qs(urllib.parse.urlsplit(page_path).query)
    if not sent:
        return []
    applied = set(urllib.parse.parse_qs(sanitized or "").keys())
    dropped = []
    for key in sent:
        if key in {"ps", "psz", "ref", "refId"}:
            continue  # paging/telemetry, never echoed back
        if key in DECOY_PARAMS:
            dropped.append(f"{key} (legacy parameter, always ignored)")
        elif key not in applied:
            dropped.append(key)
    return dropped


def build_ms(make_id: Any, model_id: Any = None, model_group_id: Any = None) -> str:
    """Compose mobile.de's `ms` filter value: makeId;modelId;modelGroupId;variant.

    The two model slots are NOT interchangeable, and mixing them up is the
    single most dangerous mistake on this API because it fails silently with
    plausible-looking results.

    mobile.de's model reference list contains two kinds of entry. A series
    ("1 Series (All)", "3 Series (All)") is marked `isGroup: true` and belongs
    in the THIRD slot. An individual model ("116", "318") has no such flag and
    belongs in the SECOND slot. The ids share one number space, so a series id
    placed in the model slot still matches something:

        ms=3500;20;;   -> 2,250 cars, all BMW 525      (id 20 as a MODEL)
        ms=3500;;20;   -> 17,102 cars, BMW 1 Series    (id 20 as a GROUP)

    Both return HTTP 200 with a full page of BMWs. Nothing in the response
    says which reading was used.
    """
    make = str(make_id).strip()
    model = "" if model_id in (None, "") else str(model_id).strip()
    group = "" if model_group_id in (None, "") else str(model_group_id).strip()
    if model and group:
        raise FilterError(
            "Give either a model id or a model group (series) id, not both -- "
            "mobile.de's ms filter has a separate slot for each and combining "
            "them matches nothing."
        )
    return f"{make};{model};{group};"


def flatten_model_options(make_id: Any, model_data: Any) -> list[dict[str, Any]]:
    """Turn a make's model reference list into ready-to-use `ms` filter values.

    Emitting the finished `ms` string per entry is the point: it removes the
    chance of a caller putting a series id in the model slot (see `build_ms`).

    mobile.de returns this list in **two different shapes** depending on
    whether the make organises its models into series, and the flat one is the
    common case -- a walker written for the grouped shape alone silently
    returns nothing for most manufacturers:

        grouped (BMW, Mercedes)  [{optgroupLabel: "1er Reihe",
                                   items: [{value, label, isGroup?}, ...]}, ...]
        flat    (Audi, Abarth)   [{value, label}, ...]

    Makes in the flat shape have no series at all, so every value belongs in
    the model slot.
    """
    out: list[dict[str, Any]] = []

    def add(item: Any, series: str | None) -> None:
        if not isinstance(item, dict):
            return
        value = item.get("value")
        if value in (None, ""):
            return
        is_group = bool(item.get("isGroup"))
        out.append(
            {
                "label": item.get("label"),
                "series": series,
                "isGroup": is_group,
                "modelGroupId": value if is_group else None,
                "modelId": None if is_group else value,
                "ms": build_ms(
                    make_id,
                    None if is_group else value,
                    value if is_group else None,
                ),
            }
        )

    for entry in model_data or []:
        if not isinstance(entry, dict):
            continue
        if "items" in entry:  # grouped shape
            for item in entry.get("items") or []:
                add(item, entry.get("optgroupLabel"))
        else:  # flat shape -- the entry IS the model
            add(entry, None)
    return out


def vehicle_category_or_raise(value: str | None) -> str:
    """Validate `vc` locally, because the server will not.

    An unknown category is not rejected: mobile.de falls back to Car and
    returns the full 1.5M-row count, so "Van" looks like it worked.
    """
    if not value:
        return "Car"
    for known in VEHICLE_CATEGORIES:
        if known.lower() == value.strip().lower():
            return known
    raise FilterError(
        f"{value!r} is not a mobile.de vehicle category. mobile.de does not "
        f"reject unknown categories -- it silently searches Cars instead -- so "
        f"this is checked here. Valid: {', '.join(VEHICLE_CATEGORIES)}"
    )


def clamp_page_size(value: Any) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError):
        return MAX_PAGE_SIZE
    return max(1, min(size, MAX_PAGE_SIZE))


# --- response shaping -------------------------------------------------------


def flatten_items(items: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Pull every real listing out of a searchResults.items array.

    Handles the nested `page1Ads` container and skips `inlineAdvertising`
    slots, which carry a slotId and no vehicle.
    """
    out: list[dict[str, Any]] = []
    for entry in items or []:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("type")
        if kind == "page1Ads":
            out.extend(flatten_items(entry.get("items")))
        elif kind == "inlineAdvertising":
            continue
        elif "id" in entry:
            out.append(entry)
    return out


# Organic first: when the same vehicle appears twice in one page, this is the
# order we would rather keep it in.
_TYPE_PREFERENCE = {"ad": 0, "topAd": 1, "eyecatcherAd": 2, "page1Ad": 3}


def dedupe_listings(
    items: list[dict[str, Any]], already_seen: set[str]
) -> list[dict[str, Any]]:
    """Drop repeats, both against earlier pages and WITHIN this page.

    A single page routinely contains the same vehicle more than once, because
    mobile.de injects paid placements (`topAd`, `eyecatcherAd`, `page1Ad`)
    drawn from the same result set the organic rows come from. A dealer with
    37 vehicles returned 41 rows for that reason.

    Where a vehicle appears twice, the organic copy is kept: `type` is the
    only thing telling a consumer whether a row was paid placement, and a
    market average computed over rows where the paid copy won would be biased
    toward whatever dealers are promoting.
    """
    best: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in items:
        key = str(item.get("id"))
        if key in already_seen:
            continue
        rank = _TYPE_PREFERENCE.get(item.get("type"), 9)
        if key not in best:
            best[key] = item
            order.append(key)
        elif rank < _TYPE_PREFERENCE.get(best[key].get("type"), 9):
            best[key] = item
    return [best[k] for k in order]


def listing_url(item: dict[str, Any]) -> str | None:
    """Public detail URL for a listing row.

    `relativeUrl` carries the whole search context (refId, searchId, sort) as
    query parameters. Those are per-run session noise, so the stable
    `/fahrzeuge/details.html?id=` form is emitted instead.
    """
    ad_id = item.get("id")
    if ad_id is None:
        return None
    return f"https://suchen.mobile.de/fahrzeuge/details.html?id={ad_id}"


def record(
    item_type: str,
    record_id: Any,
    data: dict[str, Any],
    *,
    mode: str,
    source_url: str | None = None,
    query: str | None = None,
    rank: int | None = None,
    offset: int | None = None,
    parent_id: Any = None,
) -> dict[str, Any]:
    """Wrap a payload in the portfolio's dataset envelope."""
    metadata: dict[str, Any] = {"scrapedAt": utc_now_iso(), "mode": mode}
    if source_url is not None:
        metadata["sourceUrl"] = source_url
    if query is not None:
        metadata["query"] = query
    if rank is not None:
        metadata["rank"] = rank
    if offset is not None:
        metadata["offset"] = offset
    if parent_id is not None:
        metadata["parentId"] = parent_id
    return {
        "item_type": item_type,
        "id": None if record_id is None else str(record_id),
        "data": data,
        "metadata": metadata,
    }


def error_record(
    error: str,
    detail: str,
    *,
    mode: str,
    input_value: Any = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    """A diagnostic row.

    Every input produces a row even when it fails -- a downstream join that
    sees `_error: not_found` knows the input was processed, where a missing
    row looks like the actor crashed.
    """
    return record(
        "error",
        None,
        {"_error": error, "_errorDetail": detail, "_input": input_value},
        mode=mode,
        source_url=source_url,
    )
