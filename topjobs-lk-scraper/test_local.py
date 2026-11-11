"""Standalone local runner -- exercises both modes without the Apify platform.

Usage:
    python test_local.py search <keyword> [maxResults] [fetchFullDetails: 0|1]
    python test_local.py fa <functionalAreaCode> [maxResults]
    python test_local.py detail <job-detail-url> [<job-detail-url> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_detail, run_search


async def _no_proxy():
    return None


async def run_s(keyword: str, functional_area: str | None, max_results: int, fetch_full_details: bool):
    records = await run_search(keyword, functional_area, {}, max_results, fetch_full_details, 4, _no_proxy)
    for r in records[:5]:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
    print(f"\n-> {len(records)} record(s)")


async def run_d(urls: list[str]):
    for u in urls:
        record = await run_detail(u, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:1500], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "search"
    if mode == "search":
        keyword = sys.argv[2] if len(sys.argv) > 2 else "accountant"
        max_results = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        fetch_full_details = bool(int(sys.argv[4])) if len(sys.argv) > 4 else True
        asyncio.run(run_s(keyword, None, max_results, fetch_full_details))
    elif mode == "fa":
        fa = sys.argv[2] if len(sys.argv) > 2 else "SDQ"
        max_results = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        asyncio.run(run_s("", fa, max_results, True))
    elif mode == "detail":
        urls = sys.argv[2:] or [
            "https://topjobs.lk/employer/JobAdvertismentServlet?rid=0&ac=DEFZZZ&jc=0001541024&ec=DEFZZZ&pg=applicant/vacancybyfunctionalarea.jsp"
        ]
        asyncio.run(run_d(urls))
    else:
        print(__doc__)
        sys.exit(1)
