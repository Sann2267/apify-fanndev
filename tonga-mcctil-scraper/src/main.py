import asyncio
import logging

from apify import Actor

from src.client import PaTokenNotFound, RegistryApiError, TongaRegistryClient
from src.constants import MAX_PAGE_SIZE
from src.extractor import (
    UnexpectedShape,
    extract_error,
    extract_profile_record,
    extract_search_page,
    extract_search_record,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

# Errors that mean "this specific network/token round-trip failed" -- degrade
# to a per-item error record. UnexpectedShape (payload-shape drift) is NOT
# caught here -- it propagates and fails the run loudly (see
# .ai/conventions/error-handling.md, Category 3).
TRANSIENT_ERRORS = (RegistryApiError, PaTokenNotFound, RuntimeError)


async def process_search_term(
    term: str,
    max_results: int,
    fetch_profiles: bool,
    entity_type_id: int | None,
    proxy_url: str | None,
) -> list[dict]:
    client = TongaRegistryClient(proxy_url=proxy_url)
    out: list[dict] = []
    try:
        page = 1
        page_size = min(MAX_PAGE_SIZE, max(max_results, 1))
        collected = 0

        while collected < max_results:
            try:
                data = await client.search_corp(term, page, page_size, entity_type_id)
            except TRANSIENT_ERRORS as e:
                out.append(extract_error(term, "blocked_or_transient", repr(e)))
                return out

            # UnexpectedShape propagates -- schema drift must fail the run
            # loudly, not silently disappear into a per-item error record.
            records, total = extract_search_page(data, term)
            if not records:
                break

            for rec in records:
                if collected >= max_results:
                    break
                search_record = extract_search_record(rec, term)
                if fetch_profiles:
                    corp_id = rec.get("CorpId")
                    try:
                        profile = await client.get_corp_profile(corp_id)
                        record = extract_profile_record(
                            profile, term, "S1-searchcorp+profile", extra=search_record
                        )
                    except TRANSIENT_ERRORS as e:
                        record = extract_error(term, "blocked_or_transient", repr(e))
                        record["CorpId"] = corp_id
                else:
                    record = search_record
                out.append(record)
                collected += 1

            page += 1
            if collected >= total:
                break

        if not out:
            out.append(extract_error(term, "no_results"))
        return out
    finally:
        await client.close()


async def process_corp_id(corp_id: str, proxy_url: str | None) -> dict:
    client = TongaRegistryClient(proxy_url=proxy_url)
    try:
        try:
            profile = await client.get_corp_profile(corp_id)
        except TRANSIENT_ERRORS as e:
            return extract_error(corp_id, "blocked_or_transient", repr(e))
        return extract_profile_record(profile, corp_id, "S2-profile-direct")
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        search_terms = [t for t in (input_data.get("searchTerms") or []) if t and t.strip()]
        corp_ids = [c for c in (input_data.get("corpIds") or []) if c and c.strip()]
        if not search_terms and not corp_ids:
            raise input_error("Provide 'searchTerms' and/or 'corpIds'.")

        fetch_profiles = bool(input_data.get("fetchProfiles", True))
        max_results_per_term = max(1, min(int(input_data.get("maxResultsPerTerm", 20)), 200))
        entity_type_id_raw = input_data.get("entityTypeId")
        entity_type_id = int(entity_type_id_raw) if entity_type_id_raw else None
        max_concurrency = max(1, int(input_data.get("maxConcurrency", 4)))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_term(term: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                records = await process_search_term(
                    term, max_results_per_term, fetch_profiles, entity_type_id, proxy_url
                )
                await Actor.push_data(records)

        async def _bounded_corp(corp_id: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                record = await process_corp_id(corp_id, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(
            f"{len(search_terms)} search term(s), {len(corp_ids)} direct corp id(s), "
            f"fetchProfiles={fetch_profiles}, maxConcurrency={max_concurrency}"
        )
        await asyncio.gather(
            *(_bounded_term(t) for t in search_terms),
            *(_bounded_corp(c) for c in corp_ids),
        )
