"""Standalone local runner -- exercises the search flow without the Apify
platform.

Usage:
    python test_local.py <query> [<query> ...]                # searchBy=entityNumber (default)
    python test_local.py --name <query> [<query> ...]          # searchBy=entityName
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import FijiROCClient
from src.constants import GRID_PAGE_SIZE
from src.extractor import ResultSetTooBroad, build_search_record, extract_error


async def run(queries: list[str], search_by: str, max_results: int = 10):
    for query in queries:
        client = FijiROCClient()
        try:
            token = await client.start_session()
            search_number = query if search_by == "entityNumber" else ""
            search_name = query if search_by == "entityName" else ""
            count = await client.search(token, search_number, search_name)
            print(f"\n=== {query!r} (searchBy={search_by}) -> count={count} ===")
            if count == 0:
                print(json.dumps(extract_error(query, search_by, "not_found"), ensure_ascii=False))
                continue

            to_fetch = min(count, max_results)
            skip = 0
            shown = 0
            try:
                while skip < to_fetch:
                    take = min(GRID_PAGE_SIZE, to_fetch - skip)
                    page = await client.get_results_page(skip, take)
                    rows = page.get("Data") or []
                    if not rows:
                        raise ResultSetTooBroad(count)
                    for row in rows:
                        record = build_search_record(query, search_by, row)
                        print(json.dumps(record, ensure_ascii=False, indent=2))
                        shown += 1
                    skip += len(rows)
                    if len(rows) < take:
                        break
            except ResultSetTooBroad as e:
                print(
                    json.dumps(
                        extract_error(
                            query,
                            search_by,
                            "result_set_too_broad",
                            f"search matched {e.count} entities; narrow the query",
                        ),
                        ensure_ascii=False,
                    )
                )
            print(f"-> shown {shown} of {count} total match(es)")
        finally:
            await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    search_by = "entityNumber"
    if args and args[0] == "--name":
        search_by = "entityName"
        args = args[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(args, search_by))
