"""Blibli Search Keyword Autocomplete & Suggester -- Apify Actor entrypoint."""

import asyncio
import logging

from apify import Actor

from src.client import BlibliClient, BlockedError, UpstreamShapeError
from src.constants import EXPANSION_MODES
from src.keywords import (
    InvalidInput,
    competition_level,
    curated_record,
    fetch_curated,
    fetch_trending,
    harvest,
    keyword_record,
    measure_competition,
    trending_record,
)

logger = logging.getLogger(__name__)


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        seeds = [str(s).strip() for s in (actor_input.get("seedKeywords") or []) if str(s).strip()]
        mode = actor_input.get("expansionMode", "alphabet")
        include_competition = actor_input.get("includeCompetition", True)
        include_trending = bool(actor_input.get("includeTrending"))
        include_curated = bool(actor_input.get("includeCurated"))
        max_keywords = actor_input.get("maxKeywordsPerSeed") or 0
        min_words = actor_input.get("minWordCount") or 0
        concurrency = max(1, min(int(actor_input.get("maxConcurrency") or 5), 10))

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
                "Running without a proxy. Blibli is behind Cloudflare and throttles "
                "sustained traffic from one IP -- residential proxy is recommended when "
                "expansion is on."
            )

        client = BlibliClient(proxy_url=proxy_url, new_proxy_url=new_proxy_url)
        semaphore = asyncio.Semaphore(concurrency)
        pushed = 0
        seen_global: set[str] = set()

        async def enrich(record: dict) -> dict:
            if include_competition:
                async with semaphore:
                    count = await measure_competition(client, record["keyword"])
                record["competingProducts"] = count
                record["competitionLevel"] = competition_level(count)
            return record

        async def flush(batch: list) -> int:
            if not batch:
                return 0
            done = await asyncio.gather(*(enrich(r) for r in batch))
            for record in done:
                await Actor.push_data(record)
            return len(done)

        try:
            if mode not in EXPANSION_MODES:
                raise InvalidInput(
                    f"Unknown expansionMode {mode!r}. Expected one of {list(EXPANSION_MODES)}."
                )
            if not seeds and not include_trending and not include_curated:
                raise InvalidInput(
                    "Provide at least one entry in `seedKeywords`, or enable "
                    "`includeTrending` / `includeCurated`."
                )

            Actor.log.info(
                "Harvesting from %d seed(s), expansion=%s, competition=%s",
                len(seeds), mode, include_competition,
            )

            for seed in seeds:
                batch: list = []
                found = 0
                async for term, source, position, prefix in harvest(
                    client, seed, mode, max_keywords
                ):
                    key = term.lower().strip()
                    if key in seen_global:
                        continue
                    seen_global.add(key)
                    record = keyword_record(term, seed, source, position, prefix)
                    if min_words and record["wordCount"] < min_words:
                        continue
                    batch.append(record)
                    found += 1
                    if len(batch) >= concurrency * 3:
                        pushed += await flush(batch)
                        batch = []
                pushed += await flush(batch)
                Actor.log.info("seed %r -> %d keyword(s) (%d pushed)", seed, found, pushed)

            if include_trending:
                terms = await fetch_trending(client)
                batch = []
                for position, term in enumerate(terms, start=1):
                    key = term.lower().strip()
                    if key in seen_global:
                        continue
                    seen_global.add(key)
                    batch.append(trending_record(term, position))
                pushed += await flush(batch)
                Actor.log.info("trending -> %d keyword(s)", len(batch))

            if include_curated:
                items = await fetch_curated(client)
                batch = []
                for position, item in enumerate(items, start=1):
                    key = str(item.get("keyword", "")).lower().strip()
                    if not key or key in seen_global:
                        continue
                    seen_global.add(key)
                    batch.append(curated_record(item, position))
                pushed += await flush(batch)
                Actor.log.info("curated -> %d keyword(s)", len(batch))

        except (InvalidInput, BlockedError, UpstreamShapeError) as exc:
            error_kind = {
                InvalidInput: "INVALID_INPUT",
                BlockedError: "BLOCKED_AFTER_RETRIES",
                UpstreamShapeError: "UPSTREAM_SHAPE_CHANGED",
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
                    "No keyword returned. Blibli's autocomplete gives nothing for very "
                    "narrow or misspelled seeds -- try a broader seed, or lower "
                    "minWordCount."
                ),
            })

        Actor.log.info("Done -- %d keyword(s) pushed.", pushed)
        await Actor.set_status_message(f"{pushed} keyword(s)")
