"""Local smoke test: runs every mode against the live site, no Apify platform.

Usage:  python test_local.py [mode ...]

Pushes are intercepted so records print to stdout instead of a dataset, which
keeps the run self-contained and lets the schema be eyeballed per mode.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

from src import main as M
from src.client import YellowPagesClient


class Log:
    def info(self, m): print(f"[info] {m}")
    def warning(self, m): print(f"[WARN] {m}")
    def debug(self, m): pass


RECORDS: list[dict] = []


async def fake_push(record):
    RECORDS.append(record)


CASES = {
    "search_businesses": dict(queries=["bank"], company_urls=[], province_codes=[], region="",
                              city="", max_items=30, enrich=False, concurrency=4),
    "search_businesses_region": dict(queries=["bank"], company_urls=[], province_codes=[],
                                     region="Bali", city="", max_items=15, enrich=False, concurrency=4),
    "search_businesses_enriched": dict(queries=["percetakan"], company_urls=[], province_codes=[],
                                       region="", city="", max_items=6, enrich=True, concurrency=4),
    "category_businesses": dict(queries=["bank"], company_urls=[], province_codes=[], region="",
                                city="", max_items=10, enrich=False, concurrency=4),
    "company_details": dict(queries=[], province_codes=[], region="", city="", max_items=10,
                            enrich=False, concurrency=4,
                            company_urls=["https://www.yellowpages.id/profil-185272-pt-bank-mandiri-persero-tbk-jakarta.html",
                                          "551113", "999999999"]),
    "search_products": dict(queries=["massage"], company_urls=[], province_codes=[], region="",
                            city="", max_items=12, enrich=False, concurrency=4),
    "market_insights": dict(queries=["bank"], company_urls=[], province_codes=[], region="",
                            city="", max_items=10, enrich=False, concurrency=4),
    "geo_directory": dict(queries=[], company_urls=[], province_codes=["02", "30", "23"], region="",
                          city="", max_items=10, enrich=False, concurrency=4),
}


async def run_case(name: str) -> None:
    mode = name.split("_region")[0].split("_enriched")[0]
    cfg = CASES[name]
    RECORDS.clear()
    print("\n" + "=" * 72)
    print(f"CASE {name}  (mode={mode})")
    print("=" * 72)
    async with YellowPagesClient(log=Log()) as client:
        await M.RUNNERS[mode](client, Log(), cfg)

    kinds = Counter(r["recordType"] for r in RECORDS)
    print(f"\n--> {len(RECORDS)} records {dict(kinds)}")
    if RECORDS:
        print("--> sample:")
        print(json.dumps(RECORDS[0], ensure_ascii=False, indent=1)[:1200])
    errs = [r for r in RECORDS if r["recordType"] == "ERROR"]
    if errs:
        print(f"--> {len(errs)} error rows:", [(e["_input"], e["_error"]) for e in errs])
    if not RECORDS:
        print("!!! NO RECORDS — investigate")


async def main() -> None:
    M.Actor.push_data = staticmethod(fake_push)
    wanted = sys.argv[1:] or list(CASES)
    for name in wanted:
        if name not in CASES:
            print(f"unknown case {name}; options: {', '.join(CASES)}")
            continue
        try:
            await run_case(name)
        except Exception as exc:
            print(f"!!! CASE {name} RAISED {type(exc).__name__}: {exc}")
            import traceback; traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
