"""Local smoke test -- real HTTP, no Apify platform involved.

    python test_local.py

Asserts on measurable facts, including the two upstream behaviours this Actor
is built around: the 20-per-page cap and the ignored filter parameters. If
either changes, this test says so instead of the Actor quietly changing shape.
"""

import asyncio
import json
import sys

from src.client import HimalayasClient
from src.constants import URL_JOBS
from src.extractor import aggregate_companies, matches, normalize_job
from src.main import walk_feed

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


async def main():
    client = HimalayasClient()
    failures: list[str] = []

    print("=" * 72)
    print("0. upstream behaviour re-check")
    small = await client.get_json(f"{URL_JOBS}?limit=3")
    big = await client.get_json(f"{URL_JOBS}?limit=100")
    print(f"   totalCount: {small.get('totalCount'):,}")
    print(f"   limit=100 returned: {len(big.get('jobs', []))} jobs (cap is 20)")
    if len(big.get("jobs", [])) > 20:
        print("   ! the page cap has been raised upstream -- PAGE_LIMIT can go up")
    filtered = await client.get_json(f"{URL_JOBS}?limit=3&categories=Design&minSalary=900000")
    same = [j["guid"] for j in small["jobs"]] == [j["guid"] for j in filtered["jobs"]]
    print(f"   filter params still ignored by the server: {same}")

    print("=" * 72)
    print("1. mode=jobs -- walk the feed")
    jobs, stats = await walk_feed(client, max_items=45, filters=None, max_scanned=200)
    print(f"   pages={stats['pages']} scanned={stats['scanned']} kept={len(jobs)} stop={stats['stopReason']}")
    if len(jobs) != 45:
        failures.append(f"asked for 45 jobs, got {len(jobs)}")
    guids = [j["guid"] for j in jobs]
    if len(set(guids)) != len(guids):
        failures.append("the cursor walk returned duplicate guids")
    sample = dict(jobs[0])
    sample["description"] = (sample.get("description") or "")[:120] + "..."
    sample["descriptionText"] = (sample.get("descriptionText") or "")[:120] + "..."
    print("   sample:", json.dumps(sample, ensure_ascii=False, indent=2)[:1200])
    for field in ("title", "companyName", "jobUrl", "pubDateIso", "_source"):
        if not jobs[0].get(field):
            failures.append(f"job record is missing {field}")

    print("=" * 72)
    print("2. mode=search -- local filtering")
    cases = [
        {"titleContains": "engineer"},
        {"seniority": ["Senior"]},
        {"minSalary": 150000},
        {"locationRestrictions": ["United States"]},
    ]
    for case in cases:
        found, st = await walk_feed(client, max_items=10, filters=case, max_scanned=400)
        ok = all(matches(j, case) for j in found)
        print(f"   {str(case):52s} -> {len(found):3d} match(es) scanned={st['scanned']:4d} allValid={ok}")
        if not ok:
            failures.append(f"a record failed its own filter: {case}")
        if not found:
            failures.append(f"no match at all for {case} within the scan budget")

    # A filter that must exclude: salary floor above anything published.
    absurd, _ = await walk_feed(client, max_items=5, filters={"minSalary": 99_000_000}, max_scanned=200)
    print(f"   minSalary=99,000,000 -> {len(absurd)} match(es) (expected 0)")
    if absurd:
        failures.append("an impossible salary floor still returned matches")

    print("=" * 72)
    print("3. mode=companies -- aggregation")
    companies = aggregate_companies(jobs)
    print(f"   {len(jobs)} jobs -> {len(companies)} companies")
    for c in companies[:5]:
        print(f"   {str(c['companyName'])[:32]:34s} jobsSeen={c['jobsSeen']} cats={c['categories'][:2]}")
    if sum(c["jobsSeen"] for c in companies) != len(jobs):
        failures.append("company jobsSeen does not add up to the jobs fetched")

    await client.close()

    print("=" * 72)
    if failures:
        print("FAILURES:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("ALL CHECKS PASSED")


asyncio.run(main())
