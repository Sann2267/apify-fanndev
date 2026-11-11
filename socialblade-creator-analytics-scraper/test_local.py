"""Standalone local runner -- exercises both modes without the Apify platform.

Usage:
    python test_local.py profile <handleOrUrl> [platform]
    python test_local.py top [size] [maxItems]
    python test_local.py all
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_profile, run_top


def brief(rec):
    keep = ("recordType", "platform", "displayName", "country", "channelType",
            "subscribers", "views", "videos", "historyDays", "_error")
    return {k: rec.get(k) for k in keep if k in rec}


async def smoke():
    for platform, handle in [
        ("youtube", "pewdiepie"),
        ("tiktok", "charlidamelio"),
        ("twitch", "ninja"),
        ("instagram", "cristiano"),
    ]:
        rec = await run_profile(handle, platform, None)
        print(f"== {platform}/{handle} ==")
        print("  ", json.dumps(brief(rec), ensure_ascii=False))
        print("   ranks:", json.dumps(rec.get("ranks"), ensure_ascii=False)[:200])
        hist = rec.get("history") or []
        print("   history:", len(hist), "rows |", json.dumps(hist[:1], ensure_ascii=False)[:150], "\n")

    print("== URL form (a /@handle address) ==")
    rec = await run_profile("https://socialblade.com/youtube/@mrbeast", "youtube", None)
    print("  ", json.dumps(brief(rec), ensure_ascii=False), "\n")

    print("== top 100 ==")
    rows = await run_top(100, 5, None)
    for r in rows[:3]:
        print("  ", r.get("listRank"), r.get("displayName"), r.get("subscribers"), r.get("country"))
    print(f"   -> {len(rows)} record(s)\n")

    print("== error paths ==")
    print("  ", await run_profile("definitely-not-a-real-channel-xyz-123", "youtube", None))
    print("  ", (await run_top(250, 5, None))[0].get("_errorDetail"))
    print("  ", await run_profile("cocacola", "facebook", None))


async def main():
    args = sys.argv[1:] or ["all"]
    if args[0] == "all":
        await smoke()
    elif args[0] == "profile":
        platform = args[2] if len(args) > 2 else "youtube"
        print(json.dumps(await run_profile(args[1], platform, None), ensure_ascii=False, indent=2)[:2200])
    elif args[0] == "top":
        size = int(args[1]) if len(args) > 1 else 100
        n = int(args[2]) if len(args) > 2 else 10
        for r in await run_top(size, n, None):
            print(" ", r.get("listRank"), r.get("displayName"), r.get("subscribers"))
    else:
        print(__doc__)


asyncio.run(main())
