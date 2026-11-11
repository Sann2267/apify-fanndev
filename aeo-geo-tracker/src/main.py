import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import Client
from src.constants import BING_SEARCH_URL
from src.extractor import extract_bing_results, extract_error
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def run_bing_serp(query: str, target_domain: str | None, proxy_url: str | None) -> dict:
    client = Client(proxy_url=proxy_url)
    try:
        r = await client.get(BING_SEARCH_URL, params={"q": query, "count": 10})
        if r.status_code != 200:
            return extract_error(query, f"http_{r.status_code}")
        return extract_bing_results(r.text, query, target_domain)
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(query, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        target_domain = input_data.get("targetDomain")

        queries = list(input_data.get("queries") or [])
        if input_data.get("query"):
            queries.insert(0, input_data["query"])
        if not queries:
            raise input_error("Provide 'query' or 'queries'.")
        seen = set()
        queries = [q for q in queries if not (q in seen or seen.add(q))]

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        max_concurrency = int(input_data.get("maxConcurrency", 3))
        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(q: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                record = await run_bing_serp(q, target_domain, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(f"{len(queries)} quer(y/ies), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(q) for q in queries))
