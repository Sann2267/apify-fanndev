import asyncio
import logging
from urllib.parse import quote

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import PacraClient
from src.constants import SEARCH_API_URL
from src.extractor import UnexpectedShape, extract_error, extract_records
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def search_company(query: str, proxy_url: str | None) -> list[dict]:
    query = query.strip()
    client = PacraClient(proxy_url=proxy_url)
    try:
        url = (
            f"{SEARCH_API_URL}?Searchtext={quote(query)}"
            "&SortyBy=entity%20name&Direction=ASC"
        )
        r = await client.get(url)
        if r.status_code == 204:
            # The live API returns 204 (not an empty 200 array) only for an
            # empty Searchtext -- shouldn't happen since input validation
            # requires non-empty queries, but handled defensively.
            return [extract_error(query, "empty_query")]
        if r.status_code != 200:
            return [extract_error(query, f"http_{r.status_code}")]
        try:
            data = r.json()
        except ValueError:
            return [extract_error(query, "invalid_json", r.text[:500])]
        try:
            # UnexpectedShape propagates as a per-item error record here
            # (not a run-crashing raise) -- one bad query in a batch of many
            # shouldn't take down the whole run. See .ai/CLAUDE.md #6: this
            # still fails loud (an _error record, never a silently-dropped
            # or empty-looking success record).
            return extract_records(data, query)
        except UnexpectedShape as e:
            return [extract_error(query, "unexpected_shape", str(e))]
    except (RuntimeError, ConnectionError, RequestException) as e:
        # NOTE: curl_cffi's own `ConnectionError` (raised on a failed proxy
        # CONNECT tunnel, DNS failure, etc.) does NOT inherit from Python's
        # builtin `ConnectionError` -- its MRO is RequestException ->
        # CurlError -> OSError, a parallel hierarchy with the same class
        # name. Both are caught explicitly here so a transient proxy/network
        # hiccup degrades to a per-item error record instead of crashing the
        # whole run (see guardian-nigeria-scraper/CRAWLING_METHOD.md for the
        # live incident this fix traces back to).
        return [extract_error(query, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        queries = list(input_data.get("companyNames") or [])
        if input_data.get("companyName"):
            queries.insert(0, input_data["companyName"])
        queries = [q.strip() for q in queries if q and q.strip()]
        if not queries:
            raise input_error("Provide 'companyName' or 'companyNames' (registered business name to search for).")

        max_concurrency = int(input_data.get("maxConcurrency", 4))
        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(query: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                records = await search_company(query, proxy_url)
                await Actor.push_data(records)

        Actor.log.info(f"{len(queries)} search quer(y/ies), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(q) for q in queries))
