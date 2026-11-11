"""mobile.de Scraper -- Apify Actor entrypoint."""

from __future__ import annotations

import logging
from typing import Any

from apify import Actor
from apify.log import ActorLogFormatter

from .client import MobileDeBlocked, MobileDeClient
from .constants import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_PAGE_SIZE,
    DEFAULT_REQUEST_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    SELLER_TYPES,
    SORT_BY,
)
from .modes import (
    MODE_REQUIRED_INPUT,
    MODES,
    Budget,
    guarded,
    run_dealer_contact,
    run_dealer_inventory,
    run_detail,
    run_market_count,
    run_reference_data,
    run_search,
    run_similar_ads,
)
from .parsers import (
    FilterError,
    build_ms,
    build_search_path,
    clamp_page_size,
    error_record,
    normalise_page_url,
    vehicle_category_or_raise,
)
from .input_errors import input_error

log = logging.getLogger("mobilede")

PUSH_BATCH = 100


def _configure_logging() -> None:
    """Route this actor's progress logs into the Apify run log.

    The SDK configures only the 'apify' logger, so without this the lines an
    operator needs -- which filters mobile.de silently dropped, when the
    ~2,000-row depth ceiling cut a query short -- never appear.
    """
    actor_log = logging.getLogger("mobilede")
    if actor_log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(ActorLogFormatter(include_logger_name=True))
    actor_log.addHandler(handler)
    actor_log.setLevel(logging.INFO)
    actor_log.propagate = False


async def _proxy_url(actor_input: dict[str, Any]) -> str | None:
    """Resolve the Apify proxy, if the run asked for one.

    mobile.de is gated on TLS fingerprint, not on IP: during recon every
    endpoint this actor uses answered 200 to an unproxied Indonesian address,
    while a plain `requests` call from that same address was refused. So a
    proxy is genuinely optional here.

    Where it does earn its keep: `www.mobile.de` is the only host that serves
    these endpoints internationally -- `m.mobile.de` and `suchen.mobile.de`
    answer 403 from outside Germany. A RESIDENTIAL German address
    (`countryCode: "DE"`) is the safe default for long runs and is what makes
    prices, delivery options and regional availability match what a German
    buyer sees.

    A proxy that cannot be set up never fails the run; it continues direct and
    says so, because direct genuinely works.
    """
    cfg = actor_input.get("proxyConfiguration")
    if not cfg or not cfg.get("useApifyProxy"):
        log.info("No Apify Proxy requested -- going direct (mobile.de allows it).")
        return None
    try:
        proxy_configuration = await Actor.create_proxy_configuration(
            actor_proxy_input=cfg
        )
    except Exception as exc:  # noqa: BLE001 - proxying is optional here
        log.warning(
            "Apify Proxy was requested but could not be set up (%s: %s). "
            "Continuing WITHOUT a proxy -- mobile.de's gate is the TLS "
            "fingerprint, not the IP, so the run should still work.",
            type(exc).__name__, exc,
        )
        return None
    if proxy_configuration is None:
        log.warning("Proxy requested but no configuration came back; going direct.")
        return None
    url = await proxy_configuration.new_url()
    log.info(
        "Using Apify Proxy (groups=%s, country=%s)",
        cfg.get("apifyProxyGroups") or "auto",
        cfg.get("apifyProxyCountry") or "auto",
    )
    return url


def _as_list(value: Any) -> list[str]:
    """Accept a list, a newline/comma-separated string, or Apify's URL objects."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.replace(",", "\n").split("\n")
        return [p.strip() for p in parts if p.strip()]
    out: list[str] = []
    for entry in value:
        if isinstance(entry, dict):
            entry = entry.get("url") or entry.get("value") or ""
        text = str(entry).strip()
        if text:
            out.append(text)
    return out


def _filters_from_input(actor_input: dict[str, Any]) -> dict[str, Any]:
    """Map the friendly input fields onto mobile.de's short filter codes.

    The short codes are the only ones the API honours -- the legacy
    `makeModelVariant1.makeId=` form that older mobile.de scrapers use is
    accepted and then ignored, returning every car on the site.
    """
    filters: dict[str, Any] = {}
    vc = vehicle_category_or_raise(actor_input.get("vehicleCategory"))
    filters["vc"] = vc

    make_id = actor_input.get("makeId")
    model_id = actor_input.get("modelId")
    model_group_id = actor_input.get("modelGroupId")
    if make_id:
        filters["ms"] = build_ms(make_id, model_id, model_group_id)
    elif model_id or model_group_id:
        raise FilterError(
            "A model was given without makeId. mobile.de's model ids are only "
            "unique within a make, so both are needed. Run mode "
            "'reference_data' to list them."
        )

    if actor_input.get("searchQuery"):
        filters["q"] = str(actor_input["searchQuery"]).strip()

    # Ranges use mobile.de's "min:max" syntax; either side may be left empty.
    def rng(lo_key: str, hi_key: str, code: str) -> None:
        lo = actor_input.get(lo_key)
        hi = actor_input.get(hi_key)
        if lo in (None, "") and hi in (None, ""):
            return
        filters[code] = f"{'' if lo in (None, '') else lo}:{'' if hi in (None, '') else hi}"

    rng("priceMin", "priceMax", "p")
    rng("mileageMin", "mileageMax", "ml")
    rng("firstRegistrationMin", "firstRegistrationMax", "fr")
    rng("powerMin", "powerMax", "pw")

    if actor_input.get("fuelType"):
        filters["ft"] = actor_input["fuelType"]
    if actor_input.get("transmission"):
        filters["tr"] = actor_input["transmission"]
    if actor_input.get("condition"):
        filters["con"] = actor_input["condition"]
    if actor_input.get("sellerType"):
        filters["st"] = SELLER_TYPES.get(
            actor_input["sellerType"], actor_input["sellerType"]
        )
    if actor_input.get("includeDamaged") is False:
        filters["dam"] = "false"
    if actor_input.get("country"):
        filters["cn"] = actor_input["country"]
    if actor_input.get("zipCode"):
        filters["z"] = str(actor_input["zipCode"]).strip()
        if actor_input.get("radiusKm"):
            filters["rd"] = actor_input["radiusKm"]
    if actor_input.get("maxDaysOnline"):
        filters["doc"] = actor_input["maxDaysOnline"]

    sort = actor_input.get("sortBy")
    if sort:
        filters["sb"] = SORT_BY.get(sort, sort)
        filters["od"] = "down" if actor_input.get("sortDescending") else "up"

    return filters


def _search_targets(actor_input: dict[str, Any]) -> list[tuple[str, str]]:
    """Resolve the run's search targets to (path, label) pairs."""
    urls = _as_list(actor_input.get("searchUrls"))
    if urls:
        return [(normalise_page_url(u), u) for u in urls]
    filters = _filters_from_input(actor_input)
    path = build_search_path(filters)
    return [(path, path)]


async def main() -> None:
    async with Actor:
        _configure_logging()
        actor_input = await Actor.get_input() or {}

        mode = (actor_input.get("mode") or "search").strip()
        if mode not in MODES:
            raise input_error(
                f"Unknown mode {mode!r}. Valid modes: {', '.join(MODES)}"
            )

        page_size = clamp_page_size(actor_input.get("pageSize") or DEFAULT_PAGE_SIZE)
        budget = Budget(actor_input.get("maxItems"))
        proxy_url = await _proxy_url(actor_input)

        client = MobileDeClient(
            proxy_url=proxy_url,
            timeout=int(actor_input.get("timeoutSecs") or DEFAULT_TIMEOUT_SECS),
            max_retries=int(actor_input.get("maxRetries") or DEFAULT_MAX_RETRIES),
            delay=float(
                actor_input.get("requestDelaySecs")
                if actor_input.get("requestDelaySecs") is not None
                else DEFAULT_REQUEST_DELAY_SECS
            ),
            language=actor_input.get("language") or "de",
        )

        buffer: list[dict[str, Any]] = []
        pushed = 0

        async def emit(row: dict[str, Any]) -> None:
            nonlocal pushed
            buffer.append(row)
            if len(buffer) >= PUSH_BATCH:
                await Actor.push_data(buffer)
                pushed += len(buffer)
                buffer.clear()

        async def flush() -> None:
            nonlocal pushed
            if buffer:
                await Actor.push_data(buffer)
                pushed += len(buffer)
                buffer.clear()

        log.info("Mode: %s | page size: %s | item cap: %s",
                 mode, page_size, budget.max_items or "none")

        try:
            if mode in ("search", "market_count"):
                targets = _search_targets(actor_input)
                if not targets:
                    raise ValueError(
                        f"Mode {mode!r} needs {MODE_REQUIRED_INPUT[mode]}."
                    )
                for path, label in targets:
                    if budget.exhausted:
                        break
                    if mode == "search":
                        await guarded(
                            lambda p=path, l=label: run_search(
                                client, emit, p,
                                budget=budget, page_size=page_size, label=l,
                            ),
                            emit, mode=mode, input_value=label,
                        )
                    else:
                        await guarded(
                            lambda p=path, l=label: run_market_count(
                                client, emit, p, label=l, budget=budget
                            ),
                            emit, mode=mode, input_value=label,
                        )

            elif mode in ("detail", "dealer_contact", "similar_ads"):
                refs = _as_list(actor_input.get("adIds")) + _as_list(
                    actor_input.get("adUrls")
                )
                if not refs:
                    raise ValueError(f"Mode {mode!r} needs {MODE_REQUIRED_INPUT[mode]}.")
                runner = {
                    "detail": run_detail,
                    "dealer_contact": run_dealer_contact,
                    "similar_ads": run_similar_ads,
                }[mode]
                log.info("%s targets to fetch", len(refs))
                for ref in refs:
                    if budget.exhausted:
                        log.info("Item budget reached")
                        break
                    await guarded(
                        lambda r=ref: runner(client, emit, r, budget=budget),
                        emit, mode=mode, input_value=ref,
                    )

            elif mode == "dealer_inventory":
                sellers = _as_list(actor_input.get("sellerIds"))
                if not sellers:
                    raise ValueError(f"Mode {mode!r} needs {MODE_REQUIRED_INPUT[mode]}.")
                vc = vehicle_category_or_raise(actor_input.get("vehicleCategory"))
                for sid in sellers:
                    if budget.exhausted:
                        break
                    await guarded(
                        lambda s=sid: run_dealer_inventory(
                            client, emit, s,
                            budget=budget, page_size=page_size, vehicle_category=vc,
                        ),
                        emit, mode=mode, input_value=sid,
                    )

            elif mode == "reference_data":
                vc = vehicle_category_or_raise(actor_input.get("vehicleCategory"))
                await guarded(
                    lambda: run_reference_data(client, emit, vc, budget=budget),
                    emit, mode=mode, input_value=vc,
                )

            await flush()

        except MobileDeBlocked as exc:
            await emit(
                error_record(
                    "blocked",
                    str(exc),
                    mode=mode,
                    input_value=actor_input.get("mode"),
                )
            )
            await flush()
            raise
        except Exception as exc:  # noqa: BLE001 - always leave a row behind
            await emit(
                error_record(
                    "run_failed",
                    f"{type(exc).__name__}: {exc}",
                    mode=mode,
                    input_value=str(actor_input)[:400],
                )
            )
            await flush()
            raise
        finally:
            await client.close()
            log.info(
                "Done. %s records pushed in %s HTTP requests.",
                pushed, client.requests_made,
            )
