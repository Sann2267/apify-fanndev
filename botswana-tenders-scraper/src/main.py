import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import BotswanaTendersClient
from src.extractor import build_record, extract_error, parse_finance_rss, parse_health_tenders
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def run_finance(client: BotswanaTendersClient, max_results: int) -> int:
    try:
        xml_text = await client.fetch_finance_rss()
        records = parse_finance_rss(xml_text)[:max_results]
    except (RuntimeError, RequestException, ConnectionError) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed.
        await Actor.push_data(extract_error("finance", "blocked_or_transient", repr(e)))
        return 0

    for fields in records:
        await Actor.push_data(build_record("finance", "S1-mof-procurement-rss", fields))
    Actor.log.info(f"finance: pushed {len(records)} procurement notice(s)")
    return len(records)


async def run_health(client: BotswanaTendersClient, max_results: int) -> int:
    try:
        html_text = await client.fetch_health_tenders_page()
        records = parse_health_tenders(html_text)[:max_results]
    except (RuntimeError, RequestException, ConnectionError) as e:
        await Actor.push_data(extract_error("health", "blocked_or_transient", repr(e)))
        return 0

    for fields in records:
        await Actor.push_data(build_record("health", "S2-moh-tenders-table", fields))
    Actor.log.info(f"health: pushed {len(records)} tender(s)")
    return len(records)


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        ministry = input_data.get("ministry") or "all"
        if ministry not in ("all", "finance", "health"):
            raise input_error(f"Invalid ministry {ministry!r} -- expected 'all', 'finance', or 'health'.")

        max_results = min(int(input_data.get("maxResultsPerMinistry", 100)), 500)

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        proxy_url = await proxy_config.new_url() if proxy_config else None

        client = BotswanaTendersClient(proxy_url)
        try:
            Actor.log.info(f"Running ministry={ministry!r} maxResultsPerMinistry={max_results}")
            total = 0
            if ministry in ("all", "finance"):
                total += await run_finance(client, max_results)
            if ministry in ("all", "health"):
                total += await run_health(client, max_results)
            Actor.log.info(f"Done -- pushed {total} tender record(s) total.")
        finally:
            await client.close()
