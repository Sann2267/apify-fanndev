import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import SBRClient
from src.constants import REGISTERS
from src.extractor import NoResultsFound, build_detail_record, build_summary_record, extract_error
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def search_one_query(query: str, register: str, max_results: int, proxy_config) -> dict:
    """Runs one guest search session end-to-end: search -> click each match
    to resolve its entity detail page. Returns either
    `{"matches": [{"query", "row", "entityUrl", "detailState", "detailHtml"}, ...]}`
    or `{"error": <record>}`."""
    proxy_url = await proxy_config.new_url() if proxy_config else None
    client = SBRClient(proxy_url)
    try:
        session = await client.start_search(register)
        try:
            rows = await client.search(session, query)
        except NoResultsFound:
            return {"error": extract_error(query, "not_found")}
        rows = rows[:max_results]
        matches = []
        for row in rows:
            try:
                entity_url, detail_state, detail_html = await client.open_entity(session, query, row["nodeId"])
            except (RuntimeError, RequestException, ConnectionError) as e:
                # NOTE: curl_cffi's own ConnectionError does not inherit from
                # the builtin one (parallel MRO, same name) -- both listed.
                log.warning(f"open_entity failed for {row.get('label')!r} ({query!r}): {e!r}")
                matches.append({"query": query, "row": row, "entityUrl": None, "openError": repr(e)})
                continue
            matches.append(
                {
                    "query": query,
                    "row": row,
                    "entityUrl": entity_url,
                    "detailState": detail_state,
                    "detailHtml": detail_html,
                    "client": client,
                }
            )
        return {"matches": matches, "client": client}
    except (RuntimeError, RequestException, ConnectionError) as e:
        await client.close()
        return {"error": extract_error(query, "blocked_or_transient", repr(e))}


async def fetch_detail_record(client: SBRClient, query: str, entity_url: str, detail_state, detail_html: str) -> dict:
    try:
        detail = await client.fetch_entity_detail(detail_state, detail_html)
        return build_detail_record(query, entity_url, detail)
    except (RuntimeError, RequestException, ConnectionError) as e:
        return extract_error(query, "detail_fetch_failed", repr(e))


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        queries = list(input_data.get("queries") or [])
        if input_data.get("query"):
            queries.insert(0, input_data["query"])
        if not queries:
            raise input_error(
                "Provide 'query' or 'queries' -- a company/business name or Solomon Islands "
                "registration number (e.g. 20111873, BN20030195)."
            )

        register_key = input_data.get("register") or "any"
        register = REGISTERS.get(register_key, "")
        max_results = min(int(input_data.get("maxResultsPerQuery", 20)), 200)
        fetch_details = bool(input_data.get("fetchDetails", True))
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_search(query: str):
            async with sem:
                return await search_one_query(query, register, max_results, proxy_config)

        Actor.log.info(
            f"Searching {len(queries)} quer(y/ies), register={register_key!r}, "
            f"maxResultsPerQuery={max_results}, fetchDetails={fetch_details}"
        )
        search_outcomes = await asyncio.gather(*(_bounded_search(q) for q in queries))

        all_matches = []
        clients_to_close = []
        for outcome in search_outcomes:
            if "error" in outcome:
                await Actor.push_data(outcome["error"])
            else:
                all_matches.extend(outcome["matches"])
                clients_to_close.append(outcome["client"])

        if not fetch_details:
            for m in all_matches:
                if m["entityUrl"] is None:
                    await Actor.push_data(extract_error(m["query"], "click_failed", m.get("openError")))
                else:
                    await Actor.push_data(build_summary_record(m["query"], m["row"]))
            for client in clients_to_close:
                await client.close()
            return

        matched_with_url = [m for m in all_matches if m["entityUrl"] is not None]
        for m in all_matches:
            if m["entityUrl"] is None:
                await Actor.push_data(extract_error(m["query"], "click_failed", m.get("openError")))

        Actor.log.info(f"Fetching full profiles for {len(matched_with_url)} matched entit(y/ies)")

        # Each match's detail fetch reuses the SAME client/session that
        # opened it (the detail page's tabs are fragment-POSTed against that
        # exact view-instance) -- concurrency is naturally bounded by how
        # many independent search sessions ran above.
        async def _detail_task(m: dict):
            record = await fetch_detail_record(m["client"], m["query"], m["entityUrl"], m["detailState"], m["detailHtml"])
            await Actor.push_data(record)

        await asyncio.gather(*(_detail_task(m) for m in matched_with_url))
        for client in clients_to_close:
            await client.close()
