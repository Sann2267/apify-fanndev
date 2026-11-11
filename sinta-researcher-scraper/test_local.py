"""Standalone local runner -- exercises all 3 modes without the Apify platform.

Usage:
    python test_local.py authors [query] [maxItems]
    python test_local.py author <sintaIdOrUrl> [...]
    python test_local.py affiliations [maxItems]
    python test_local.py all
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_affiliations, run_author, run_authors


def show(records, limit=2):
    for r in records[:limit]:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:900], "...")
    print(f"-> {len(records)} record(s)\n")


async def smoke():
    print("== authors (25 -> crosses page boundaries) ==")
    recs = await run_authors(None, 25, None)
    show(recs)
    cov = {k: sum(1 for r in recs if r.get(k) is not None)
           for k in ("sintaId", "name", "affiliation", "sintaScoreOverall", "scopusHIndex", "subjects")}
    print("   field coverage:", cov)
    print("   total available upstream:", recs[0].get("_totalRecordsAvailable"), "\n")

    print("== authors search q=zainul ==")
    show(await run_authors("zainul", 3, None), limit=1)

    print("== affiliations ==")
    aff = await run_affiliations(3, None)
    show(aff, limit=2)

    print("== author profile ==")
    sid = next((r["sintaId"] for r in recs if r.get("sintaId")), None)
    print(json.dumps(await run_author(sid, None), ensure_ascii=False, indent=2)[:1500], "...")

    print("\n== error path ==")
    print(await run_author("not-an-id", None))


async def main():
    args = sys.argv[1:] or ["all"]
    mode = args[0]
    if mode == "all":
        await smoke()
    elif mode == "authors":
        q = args[1] if len(args) > 1 and not args[1].isdigit() else None
        n = int(args[-1]) if args[-1].isdigit() else 10
        show(await run_authors(q, n, None), limit=3)
    elif mode == "author":
        for raw in args[1:]:
            print(json.dumps(await run_author(raw, None), ensure_ascii=False, indent=2)[:1800])
    elif mode == "affiliations":
        n = int(args[1]) if len(args) > 1 else 10
        show(await run_affiliations(n, None), limit=3)
    else:
        print(__doc__)


asyncio.run(main())
