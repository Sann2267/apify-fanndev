import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import FijiROCClient, LoginRequired
from src.constants import GRID_PAGE_SIZE
from src.extractor import ResultSetTooBroad, build_search_record, extract_error
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def search_one_query(query: str, search_by: str, max_results: int, proxy_config) -> dict:
    """Runs one search session end-to-end: establish session -> POST search
    -> page through GetSearchResults up to max_results. Returns either
    `{"records": [...]}` or `{"error": <record>}`.
    """
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = FijiROCClient(proxy_url)
    try:
        token = await client.start_session()
        search_number = query if search_by == "entityNumber" else ""
        search_name = query if search_by == "entityName" else ""
        count = await client.search(token, search_number, search_name)
        if count == 0:
            return {"error": extract_error(query, search_by, "not_found")}

        to_fetch = min(count, max_results)
        records = []
        skip = 0
        while skip < to_fetch:
            take = min(GRID_PAGE_SIZE, to_fetch - skip)
            page = await client.get_results_page(skip, take)
            rows = page.get("Data") or []
            if not rows:
                # Real matches (count > 0) but the grid came back empty --
                # the confirmed upstream too-broad-result-set cap, not a
                # genuine zero-match. Fail loud instead of returning
                # whatever partial rows we already collected as if complete.
                raise ResultSetTooBroad(count)
            for row in rows:
                records.append(build_search_record(query, search_by, row))
            skip += len(rows)
            if len(rows) < take:
                break  # upstream ran out of rows before our requested take
        return {"records": records}
    except ResultSetTooBroad as e:
        return {
            "error": extract_error(
                query, search_by, "result_set_too_broad", f"search matched {e.count} entities; narrow the query"
            )
        }
    except LoginRequired as e:
        return {"error": extract_error(query, search_by, "login_required", repr(e))}
    except (RuntimeError, RequestException, ConnectionError) as e:
        # NOTE: curl_cffi's own ConnectionError does not inherit from the
        # builtin one (parallel MRO, same name) -- both listed.
        return {"error": extract_error(query, search_by, "blocked_or_transient", repr(e))}
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        queries = list(input_data.get("queries") or [])
        if input_data.get("query"):
            queries.insert(0, input_data["query"])
        if not queries:
            raise input_error("Provide 'query' or 'queries' -- a ROC entity number or entity/business name.")

        search_by = input_data.get("searchBy") or "entityNumber"
        if search_by not in ("entityNumber", "entityName"):
            raise input_error("searchBy must be 'entityNumber' or 'entityName'")
        max_results = min(int(input_data.get("maxResultsPerQuery", 20)), 500)
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_search(query: str):
            async with sem:
                return await search_one_query(query, search_by, max_results, proxy_config)

        Actor.log.info(
            f"Searching {len(queries)} quer(y/ies) by {search_by!r}, maxResultsPerQuery={max_results}"
        )
        if search_by == "entityName":
            Actor.log.warning(
                "searchBy='entityName' uses Fiji ROC's own fuzzy/phonetic name matching, not a "
                "substring search -- expect large, loosely-related result sets (a confirmed upstream "
                "quirk, see CRAWLING_METHOD.md). Prefer 'entityNumber' when the registration number is known."
            )

        outcomes = await asyncio.gather(*(_bounded_search(q) for q in queries))

        for outcome in outcomes:
            if "error" in outcome:
                await Actor.push_data(outcome["error"])
            else:
                for record in outcome["records"]:
                    await Actor.push_data(record)
