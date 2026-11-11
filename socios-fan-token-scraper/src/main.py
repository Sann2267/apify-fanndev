"""Socios.com / Chiliz scraper -- Apify actor entry point.

One actor, six modes, because all six read the same gateway with the same
anonymous role and the same pagination contract, and because the reference
tables are what make the poll data legible: a poll identifies its club by UUID
and nothing else, so ``partners`` is not a separate product, it is the key.
"""

from __future__ import annotations

import asyncio

from apify import Actor

from src.client import ChilizClient, ChilizError, Forbidden, UnexpectedShape
from src.constants import (
    COUNTRIES_URL,
    CURRENCIES_URL,
    LEAGUES_URL,
    MAX_PAGE_SIZE,
    MODES,
    PARTNERS_URL,
    POLL_ORDER_BY,
    POLL_STATUSES,
    POLL_TYPES,
    SPORTS_URL,
    SURVEYS_URL,
    VOTE_TOKENS_URL,
)
from src.records import envelope, error_record, poll_extras, token_extras
from src.resolve import resolve_partners
from src.runtime import clamp, dedupe, proxy_url_from, string_list
from src.input_errors import input_error


async def fetch_partners(client: ChilizClient, log) -> list[dict]:
    """The 231-row partner directory. Four of the six modes want it."""
    return await client.collect(PARTNERS_URL, max_items=None, log=log)


def _partner_indexes(partners: list[dict]) -> tuple[dict, dict]:
    by_id = {p["id"]: p for p in partners if p.get("id")}
    by_currency = {p["currencyId"]: p for p in partners if p.get("currencyId")}
    return by_id, by_currency


async def run_polls(client: ChilizClient, actor_input: dict, log) -> tuple[list[dict], list[dict]]:
    """Fan votes with their results, filtered server-side where the API allows."""
    errors: list[dict] = []
    params: list[tuple[str, object]] = []

    # Sent lower-case with hyphens: the upper-case names the API prints in its
    # own 400 are enum constants, and every one of them is rejected verbatim.
    statuses = [
        s.strip().casefold().replace("_", "-")
        for s in string_list(actor_input.get("pollStatuses"))
    ]
    unknown = [s for s in statuses if s not in POLL_STATUSES]
    if unknown:
        raise ValueError(
            f"Unknown poll status {unknown}. The API accepts: {', '.join(POLL_STATUSES)}"
        )
    for status in dedupe(statuses):
        params.append(("status[]", status))

    wanted_partners = dedupe(string_list(actor_input.get("partners")))
    partner_ids: list[str] = []
    if wanted_partners:
        directory = await fetch_partners(client, log)
        partner_ids, unmatched = resolve_partners(wanted_partners, directory)
        for miss, reason in unmatched:
            errors.append(
                error_record(
                    miss,
                    "partner_not_found",
                    f"{reason}. Run the actor in partners mode to list all "
                    f"{len(directory)} clubs with their exact names and symbols.",
                )
            )
        if not partner_ids:
            return [], errors
        log.info(
            f"Resolved {len(wanted_partners)} input(s) to {len(partner_ids)} partner id(s)."
        )
        # partnerIds[] (plural) is the parameter that actually filters.
        # partnerId[], partner[] and partners[] are accepted and ignored.
        for identifier in partner_ids:
            params.append(("partnerIds[]", identifier))

    order_by = (actor_input.get("pollOrderBy") or "").strip()
    if order_by:
        if order_by not in POLL_ORDER_BY:
            raise ValueError(
                f"Unknown pollOrderBy {order_by!r}. "
                f"The API accepts: {', '.join(POLL_ORDER_BY)}"
            )
        params.append(("orderBy", order_by))

    max_items = clamp(actor_input.get("maxItems"), 1, 100000, 1000)
    types = {t.strip().casefold() for t in string_list(actor_input.get("pollTypes"))}

    # Stop fetching at maxItems, but only when nothing is filtered afterwards:
    # a client-side type filter discards rows the server already counted, so
    # stopping early there would hand back fewer polls than were asked for.
    # Ordering is newest-first, so an early stop yields the newest maxItems.
    rows = await client.collect(
        SURVEYS_URL, params=params, max_items=None if types else max_items, log=log
    )

    # The server honours status[] and partnerIds[]; verify rather than trust,
    # because this API answers 200 to filters it silently ignores.
    if partner_ids:
        stray = {r.get("partnerId") for r in rows} - set(partner_ids)
        if stray:
            raise UnexpectedShape(
                "partnerIds[] no longer filters: the gateway returned polls from "
                f"{len(stray)} partner(s) that were not requested. Re-verify the "
                "filter parameter name before trusting this dataset."
            )

    # type[] is accepted and ignored upstream, so it is applied here instead.
    if types:
        unknown_types = types - {t.casefold() for t in POLL_TYPES}
        if unknown_types:
            raise ValueError(
                f"Unknown poll type {sorted(unknown_types)}. "
                f"Known: {', '.join(POLL_TYPES)}"
            )
        rows = [r for r in rows if str(r.get("type") or "").casefold() in types]

    rows = rows[:max_items]
    records = [
        envelope(
            r.get("partnerName") or r.get("id") or "poll",
            "POLL",
            {**r, **poll_extras(r)},
        )
        for r in rows
    ]
    return records, errors


async def run_partners(client: ChilizClient, actor_input: dict, log) -> list[dict]:
    partners = await fetch_partners(client, log)
    if actor_input.get("activePartnersOnly"):
        # status[] is ignored on this route, so 'active' is applied here.
        partners = [p for p in partners if str(p.get("status") or "").casefold() == "active"]
    max_items = clamp(actor_input.get("maxItems"), 1, 100000, 1000)
    return [
        envelope(p.get("name") or p.get("id") or "partner", "PARTNER", p)
        for p in partners[:max_items]
    ]


async def run_fan_tokens(client: ChilizClient, log) -> list[dict]:
    currencies, partners = await asyncio.gather(
        client.collect(CURRENCIES_URL, log=log), fetch_partners(client, log)
    )
    _, by_currency = _partner_indexes(partners)
    return [
        envelope(
            c.get("shortCode") or c.get("id") or "currency",
            "FAN_TOKEN",
            {**c, **token_extras(c, by_currency)},
        )
        for c in currencies
    ]


async def run_vote_tokens(client: ChilizClient, log) -> list[dict]:
    tokens, partners = await asyncio.gather(
        client.collect(VOTE_TOKENS_URL, log=log), fetch_partners(client, log)
    )
    by_id, _ = _partner_indexes(partners)
    out = []
    for token in tokens:
        partner = by_id.get(token.get("partnerId")) or {}
        out.append(
            envelope(
                token.get("tokenSymbol") or token.get("id") or "voteToken",
                "VOTE_TOKEN",
                {
                    **token,
                    "partnerName": partner.get("name"),
                    "partnerType": partner.get("type"),
                },
            )
        )
    return out


async def run_reference(client: ChilizClient, log) -> list[dict]:
    # These three carry no metadata and ignore ``page`` -- page 2 repeats page
    # 1 -- so ``limit`` is the only lever, and leagues hands back just 7 of its
    # 49 rows if it is left off. A few hundred rows between them, so ask for the
    # maximum and let the client's truncation guard catch it if they outgrow it.
    leagues, sports, countries = await asyncio.gather(
        client.collect(LEAGUES_URL, page_size=MAX_PAGE_SIZE, log=log),
        client.collect(SPORTS_URL, page_size=MAX_PAGE_SIZE, log=log),
        client.collect(COUNTRIES_URL, page_size=MAX_PAGE_SIZE, log=log),
    )
    by_sport = {s["id"]: s for s in sports if s.get("id")}
    by_country = {c["id"]: c for c in countries if c.get("id")}
    records = []
    for league in leagues:
        records.append(
            envelope(
                league.get("name") or "league",
                "LEAGUE",
                {
                    **league,
                    "sportName": (by_sport.get(league.get("sportId")) or {}).get("name"),
                    "countryName": (by_country.get(league.get("countryId")) or {}).get("name"),
                },
            )
        )
    records += [envelope(s.get("name") or "sport", "SPORT", s) for s in sports]
    records += [envelope(c.get("name") or "country", "COUNTRY", c) for c in countries]
    return records


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        log = Actor.log

        mode = (actor_input.get("mode") or "polls").strip()
        if mode not in MODES:
            raise input_error(f"Unknown mode {mode!r}. Choose one of: {', '.join(MODES)}")

        proxy_url = await proxy_url_from(Actor, actor_input)
        client = ChilizClient(proxy_url=proxy_url)

        selected = [m for m in MODES if m != "all"] if mode == "all" else [mode]
        log.info(f"Mode {mode!r} -> running: {', '.join(selected)}")

        pushed = 0
        try:
            for step in selected:
                try:
                    if step == "polls":
                        records, errors = await run_polls(client, actor_input, log)
                        records += errors
                    elif step == "partners":
                        records = await run_partners(client, actor_input, log)
                    elif step == "fanTokens":
                        records = await run_fan_tokens(client, log)
                    elif step == "voteTokens":
                        records = await run_vote_tokens(client, log)
                    else:
                        records = await run_reference(client, log)
                except Forbidden as exc:
                    # An ACL change is news, not a crash: the other modes still work.
                    log.error(f"{step}: {exc}")
                    records = [error_record(step, "forbidden_by_acl", str(exc))]
                except ChilizError as exc:
                    log.error(f"{step}: {exc}")
                    records = [error_record(step, "request_failed", str(exc))]

                if records:
                    await Actor.push_data(records)
                    pushed += len(records)
                log.info(f"{step}: pushed {len(records)} record(s)")
        finally:
            await client.close()

        log.info(f"Finished. {pushed} record(s) in the dataset.")
