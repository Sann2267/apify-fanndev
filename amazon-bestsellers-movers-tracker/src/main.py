"""Amazon Best Sellers & Movers Tracker -- Apify Actor entrypoint."""

import asyncio
import logging

from apify import Actor

from src.client import AmazonClient, BlockedError, CaptchaError, NotFound
from src.constants import (
    DEFAULT_DELAY_SECONDS,
    DOMAINS,
    LIST_PATHS,
    MOVE_DROPPED,
    STATE_STORE_NAME,
)
from src.ranking import (
    InvalidInput,
    build_records,
    build_url,
    detect_movement,
    dropped_out_records,
    pages_for,
    resolve_category,
    snapshot_key,
)

logger = logging.getLogger(__name__)


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        raw_categories = actor_input.get("categories") or []
        default_domain = actor_input.get("marketplace", "com")
        default_list = actor_input.get("listType", "bestsellers")
        max_rank = actor_input.get("maxRank") or 100
        track_movement = actor_input.get("trackMovement", True)
        movers_only = bool(actor_input.get("onlyMovers"))
        include_dropped = actor_input.get("includeDroppedOut", True)
        state_store_name = actor_input.get("stateStoreName") or STATE_STORE_NAME
        delay = actor_input.get("delaySeconds")
        delay = DEFAULT_DELAY_SECONDS if delay is None else float(delay)

        proxy_config = None
        try:
            proxy_config = await Actor.create_proxy_configuration(
                actor_proxy_input=actor_input.get("proxyConfiguration")
            )
        except Exception as exc:  # noqa: BLE001
            Actor.log.warning("Proxy configuration unavailable (%s) -- going direct.", exc)

        proxy_url = await proxy_config.new_url() if proxy_config else None
        new_proxy_url = proxy_config.new_url if proxy_config else None
        if not proxy_url:
            Actor.log.warning(
                "Running without a proxy. Amazon serves a CAPTCHA to traffic it dislikes; "
                "residential proxy is recommended for scheduled runs."
            )

        client = AmazonClient(proxy_url=proxy_url, new_proxy_url=new_proxy_url)
        pushed = 0
        stats = {"lists": 0, "products": 0, "movers": 0, "new": 0, "dropped": 0, "failed": 0}

        try:
            if default_domain not in DOMAINS:
                raise InvalidInput(
                    f"Unknown marketplace {default_domain!r}. Expected one of {list(DOMAINS)}."
                )
            if default_list not in LIST_PATHS:
                raise InvalidInput(
                    f"Unknown listType {default_list!r}. Expected one of {list(LIST_PATHS)}."
                )
            if not raw_categories:
                raise InvalidInput(
                    '`categories` is empty. Provide category slugs like ["electronics"], '
                    'node paths like ["electronics/172541"], or full Amazon list URLs.'
                )

            targets = []
            for raw in raw_categories:
                try:
                    target = resolve_category(raw)
                except InvalidInput as exc:
                    Actor.log.error("Skipping %r: %s", raw, exc)
                    await Actor.push_data({
                        "_input": str(raw), "_source": "none",
                        "_error": "INVALID_INPUT", "_errorDetail": str(exc),
                    })
                    pushed += 1
                    stats["failed"] += 1
                    continue
                target["domain"] = target["domain"] or default_domain
                target["listType"] = target["listType"] or default_list
                target["label"] = (
                    f"{target['domain']}/{target['listType']}/{target['category']}"
                )
                targets.append(target)
            if not targets:
                raise InvalidInput("No usable categories among the provided inputs.")

            store = None
            previous_all: dict = {}
            if track_movement:
                store = await Actor.open_key_value_store(name=state_store_name)
                previous_all = await store.get_value("SNAPSHOT") or {}
                Actor.log.info(
                    "Loaded snapshot '%s' covering %d list(s)",
                    state_store_name, len(previous_all),
                )

            Actor.log.info(
                "Tracking %d list(s), top %d, movement=%s", len(targets), max_rank, track_movement
            )

            snapshot: dict = {}
            for index, target in enumerate(targets):
                base = DOMAINS[target["domain"]]
                key = snapshot_key(target)
                previous = previous_all.get(key) or {}
                records: list = []

                try:
                    for page in range(1, pages_for(max_rank) + 1):
                        url = build_url(
                            target["domain"], target["listType"], target["category"], page
                        )
                        page_html = await client.get_page(url)
                        page_records = build_records(page_html, base, target)
                        if not page_records:
                            # An empty recs-list is exactly what Amazon's
                            # Movers & Shakers pages return; say which list
                            # was empty rather than failing silently.
                            Actor.log.warning(
                                "%s page %d returned no ranked products", target["label"], page
                            )
                            break
                        records.extend(page_records)
                        if page < pages_for(max_rank) and delay:
                            await asyncio.sleep(delay)

                    records = [r for r in records if (r.get("rank") or 0) <= max_rank]
                    if not records:
                        raise NotFound(
                            f"{target['label']} returned no ranked products. Amazon's "
                            "Movers & Shakers lists were empty in every category tested; "
                            "use listType 'bestsellers' and let this actor compute movers."
                        )

                    seen = {r["asin"] for r in records}
                    if track_movement:
                        for record in records:
                            detect_movement(record, previous.get(record["asin"]))
                            if record["movementType"] == "NEW_ENTRY":
                                stats["new"] += 1
                            if record.get("isSignificantMove"):
                                stats["movers"] += 1
                        if include_dropped and previous:
                            records.extend(
                                dropped_out_records(previous, seen, target, base)
                            )
                            stats["dropped"] += sum(
                                1 for r in records if r["movementType"] == MOVE_DROPPED
                            )
                        snapshot[key] = {
                            r["asin"]: r["rank"] for r in records if r.get("rank")
                        }

                    for record in records:
                        if movers_only and track_movement and not record.get("isSignificantMove"):
                            continue
                        await Actor.push_data(record)
                        pushed += 1

                    stats["lists"] += 1
                    stats["products"] += len(records)
                    Actor.log.info(
                        "%s -> %d product(s), %d new, %d significant move(s)",
                        target["label"], len(records),
                        sum(1 for r in records if r.get("isNewEntry")),
                        sum(1 for r in records if r.get("isSignificantMove")),
                    )

                except (NotFound, BlockedError, CaptchaError) as exc:
                    stats["failed"] += 1
                    error_kind = {
                        NotFound: "NOT_FOUND",
                        BlockedError: "BLOCKED_AFTER_RETRIES",
                        CaptchaError: "CAPTCHA_ESCALATION",
                    }[type(exc)]
                    Actor.log.error("%s failed: %s", target["label"], exc)
                    await Actor.push_data({
                        "_input": target["label"], "_source": "none",
                        "category": target["category"], "listType": target["listType"],
                        "marketplace": target["domain"],
                        "_error": error_kind, "_errorDetail": str(exc),
                    })
                    pushed += 1

                if delay and index < len(targets) - 1:
                    await asyncio.sleep(delay)

            if track_movement and store is not None:
                # Lists not covered by this run keep their history.
                merged = {**previous_all, **snapshot}
                await store.set_value("SNAPSHOT", merged)
                Actor.log.info("Snapshot saved for %d list(s)", len(merged))

        except (InvalidInput, BlockedError, CaptchaError) as exc:
            error_kind = {
                InvalidInput: "INVALID_INPUT",
                BlockedError: "BLOCKED_AFTER_RETRIES",
                CaptchaError: "CAPTCHA_ESCALATION",
            }[type(exc)]
            Actor.log.exception("Run failed: %s", error_kind)
            await Actor.push_data({
                "_input": "input", "_source": "none",
                "_error": error_kind, "_errorDetail": str(exc),
            })
            await Actor.set_status_message(f"Failed: {error_kind}")
            raise
        finally:
            await client.close()

        if pushed == 0:
            Actor.log.warning("Run produced no records.")
            await Actor.push_data({
                "_input": "input", "_source": "none", "_error": "EMPTY_RESULT",
                "_errorDetail": (
                    "No ranked product returned. Check the category slugs, or turn off "
                    "onlyMovers -- on a first run nothing has moved yet."
                ),
            })

        Actor.log.info(
            "Done -- %d pushed | %d list(s), %d product(s), %d new, %d mover(s), "
            "%d dropped, %d failed",
            pushed, stats["lists"], stats["products"], stats["new"], stats["movers"],
            stats["dropped"], stats["failed"],
        )
        await Actor.set_status_message(
            f"{stats['products']} product(s) across {stats['lists']} list(s), "
            f"{stats['movers']} mover(s)"
        )
