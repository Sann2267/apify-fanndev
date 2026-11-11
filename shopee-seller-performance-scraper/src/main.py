"""Mode dispatch for the Shopee seller-performance Actor.

* ``shop``      -- one record per shop, looked up by username or by numeric
  shop ID. Both work; IDs are the reliable route because a brand's username
  frequently is not its brand name.
* ``reference`` -- probe the endpoint and report what it yielded.

The failure mode this Actor exists to get right: ``get_shop_detail`` answers
**HTTP 200 with an error body** when a username does not exist
(``error 2003013 invalid_username``). Treating that as success records an empty
shop; this Actor emits ``NOT_FOUND`` and says which lookup failed.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

from apify import Actor

from src.client import Blocked, Gated, NotFound, ShopeeClient
from src.constants import (
    DOMAINS,
    INVALID_USERNAME_ERROR,
    MODES,
    URL_SHOP_BY_ID,
    URL_SHOP_BY_USERNAME,
)
from src.extractor import parse_shop
from src.input_errors import input_error

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _envelope(payload: dict, *, source: str, query: str, record_type: str,
              country: str | None = None, attempts: int | None = None) -> dict:
    return {
        "_input": query,
        "_query": query,
        "_source": source,
        "_country": country,
        "_scrapedAt": _now(),
        "_attempts": attempts,
        "recordType": record_type,
        **payload,
    }


def _parse_target(raw: str) -> tuple[str, str]:
    """Return ``(kind, value)`` — 'shopid' or 'username'.

    Accepts a bare username, a numeric ID, a ``/shop/<id>`` URL, a
    ``/<username>`` URL, or a product URL of the form
    ``…-i.<shopid>.<itemid>`` — the last one matters because the flash-sale
    Actor in this portfolio emits exactly those, so the two chain together.
    """
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        return "username", ""

    if raw.isdigit():
        return "shopid", raw

    found = re.search(r"-i\.(\d+)\.\d+", raw)
    if found:
        return "shopid", found.group(1)

    found = re.search(r"/shop/(\d+)", raw)
    if found:
        return "shopid", found.group(1)

    if raw.startswith("http"):
        path = re.sub(r"^https?://[^/]+/", "", raw)
        path = path.split("?")[0].split("/")[0]
        return "username", path

    return "username", raw.lstrip("@")


async def _one_shop(client: ShopeeClient, raw: str, country: str) -> dict:
    domain = DOMAINS[country]
    kind, value = _parse_target(raw)
    if not value:
        return _envelope({"error": "unparseable-input"},
                         source="none", query=raw, record_type="ERROR", country=country)

    url = (URL_SHOP_BY_ID.format(domain=domain, shopid=value) if kind == "shopid"
           else URL_SHOP_BY_USERNAME.format(domain=domain, username=value))

    try:
        payload, profile, attempts = await client.get_json(url, domain, country)
    except Gated as exc:
        return _envelope(
            {"error": "gated", "message": str(exc),
             "hint": "Shopee refused this endpoint at its load balancer. "
                     "Retry through a residential proxy."},
            source="shop-detail", query=raw, record_type="GATED", country=country)
    except NotFound:
        return _envelope({"error": "not-found", "lookupKind": kind, "lookupValue": value},
                         source="shop-detail", query=raw, record_type="NOT_FOUND",
                         country=country)
    except Blocked as exc:
        return _envelope({"error": "blocked", "message": str(exc)},
                         source="shop-detail", query=raw, record_type="ERROR",
                         country=country)

    # HTTP 200 carrying an error body. The whole reason this branch exists.
    if payload.get("error") == INVALID_USERNAME_ERROR:
        return _envelope(
            {"error": "invalid-username", "lookupKind": kind, "lookupValue": value,
             "hint": "Shopee answered 200 but reported invalid_username. A brand's "
                     "store username often differs from its brand name - look the "
                     "shop up by numeric shopId instead."},
            source="shop-detail", query=raw, record_type="NOT_FOUND",
            country=country, attempts=attempts)
    if payload.get("error"):
        return _envelope(
            {"error": "api-error", "apiError": payload.get("error"),
             "message": payload.get("error_msg"), "lookupKind": kind,
             "lookupValue": value},
            source="shop-detail", query=raw, record_type="ERROR",
            country=country, attempts=attempts)

    shop = parse_shop(payload, domain)
    shop["_tlsProfile"] = profile
    shop["_lookupKind"] = kind
    if kind == "username" and not shop.get("username"):
        shop["username"] = value
    return _envelope(shop, source="shop-detail", query=raw, record_type="SHOP",
                     country=country, attempts=attempts)


async def _run_shops(client, targets, country, concurrency) -> int:
    semaphore = asyncio.Semaphore(concurrency)

    async def worker(raw: str) -> dict:
        async with semaphore:
            return await _one_shop(client, raw, country)

    pushed = 0
    for coro in asyncio.as_completed([worker(t) for t in targets]):
        await Actor.push_data(await coro)
        pushed += 1
    return pushed


async def _run_reference(client, country) -> int:
    domain = DOMAINS[country]
    probes = []
    for target in ("shopee_id", "samsung.official", "definitely_not_a_real_shop_xyz"):
        try:
            payload, profile, attempts = await client.get_json(
                URL_SHOP_BY_USERNAME.format(domain=domain, username=target),
                domain, country)
            if payload.get("error") == INVALID_USERNAME_ERROR:
                probes.append({"username": target, "ok": False,
                               "note": "HTTP 200 with invalid_username error body",
                               "attempts": attempts})
                continue
            shop = parse_shop(payload, domain)
            probes.append({
                "username": target, "ok": True, "attempts": attempts,
                "tlsProfile": profile, "rawFieldCount": shop["_rawFieldCount"],
                "followerCount": shop["followerCount"],
                "ratingStar": shop["ratingStar"],
                "responseRate": shop["responseRate"],
                "shopAgeDays": shop["shopAgeDays"],
            })
        except Exception as exc:
            probes.append({"username": target, "ok": False,
                           "error": f"{type(exc).__name__}: {exc}"})

    await Actor.push_data(_envelope(
        {
            "surface": "shopee /api/v4/shop/get_shop_detail",
            "probes": probes,
            "known": {
                "openEndpoint": "shop/get_shop_detail (by username AND by shopid)",
                "gatedEndpoints": ["shop/get_shop_seo", "search/search_items",
                                   "item/get_ratings"],
                "erroringEndpoint": "shop/get_shop_base returns service_err",
                "silentFailure": "A missing username returns HTTP 200 with "
                                 "error 2003013 - status code alone is not enough.",
                "responseTimeUnit": "seconds",
            },
        },
        source="reference", query="reference", record_type="SURFACE", country=country))
    return 1


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        mode = (actor_input.get("mode") or "shop").strip()
        if mode not in MODES:
            raise input_error(f"mode must be one of {MODES}, got {mode!r}")

        country = (actor_input.get("country") or "ID").strip().upper()
        if country not in DOMAINS:
            raise input_error(f"unknown country {country!r}; supported: {sorted(DOMAINS)}")

        concurrency = max(1, min(int(actor_input.get("concurrency") or 4), 10))

        proxy_url = None
        proxy_config = actor_input.get("proxyConfiguration")
        if proxy_config:
            configuration = await Actor.create_proxy_configuration(actor_proxy_input=proxy_config)
            if configuration:
                proxy_url = await configuration.new_url()

        client = ShopeeClient(proxy_url=proxy_url, profile=actor_input.get("tlsProfile"))

        if mode == "reference":
            pushed = await _run_reference(client, country)
        else:
            targets = actor_input.get("shops") or []
            if not targets:
                raise input_error("shop mode needs at least one entry in `shops`.")
            pushed = await _run_shops(client, targets, country, concurrency)

        log.info("pushed %d record(s) in mode=%s", pushed, mode)
