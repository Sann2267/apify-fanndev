"""Standalone local runner -- exercises all 4 modes without the Apify platform.

Usage:
    python test_local.py fixtures [sportId] [dayOffset] [maxItems]
    python test_local.py live [sportId] [maxItems]
    python test_local.py match <matchIdOrUrl> [sportId]
    python test_local.py reference
    python test_local.py all           # smoke-test every mode
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_fixtures, run_live, run_match, run_reference


def show(records, limit=2, keys=None):
    for r in records[:limit]:
        if keys:
            print("   ", {k: r.get(k) for k in keys})
        else:
            print(json.dumps(r, ensure_ascii=False, indent=2)[:900], "...")
    print(f"-> {len(records)} record(s)\n")


SUMMARY_KEYS = ["matchId", "sportName", "country", "tournament", "homeTeam", "awayTeam",
                "score", "status", "startTime"]


async def smoke():
    print("== fixtures: football today ==")
    fx = await run_fixtures([1], [0], 40, None)
    show(fx, 3, SUMMARY_KEYS)
    assert fx and not fx[0].get("_error"), "fixtures returned no usable rows"
    assert fx[0].get("homeTeam") and fx[0].get("tournament"), "match row is missing team/tournament"

    print("== fixtures: 3 sports x 2 days (multi) ==")
    multi = await run_fixtures([1, 2, 3], [0, -1], 60, None)
    sports = sorted({r.get("sportName") for r in multi if r.get("sportName")})
    print(f"   sports covered: {sports}")
    show(multi, 2, SUMMARY_KEYS)

    print("== live: football ==")
    lv = await run_live([1], 10, None)
    print(f"   (empty is legitimate when nothing is in play right now)")
    show(lv, 2, SUMMARY_KEYS)

    print("== match detail (first finished football match of today) ==")
    finished = [r for r in fx if r.get("status") == "FINISHED"]
    target = (finished or fx)[0]["matchId"]
    det = await run_match(target, 1, {"summary": True, "statistics": True,
                                      "lineups": True, "headToHead": True}, None)
    print("   matchId:", det.get("matchId"), "| error:", det.get("_error"))
    print("   meta keys:", list((det.get("meta") or {}).keys())[:10])
    print("   incidents:", len(det.get("incidents") or []),
          "| statistics:", len(det.get("statistics") or []),
          "| lineups blocks:", len(det.get("lineups") or []),
          "| h2h blocks:", len(det.get("headToHead") or []))
    for s in (det.get("statistics") or [])[:6]:
        print("     stat:", s)
    for i in (det.get("incidents") or [])[:4]:
        print("     incident:", {k: i[k] for k in ("minute", "player", "side", "incidentTypeId")})

    print("\n== match detail with a MISMATCHED sportId ==")
    print("   (verified upstream behaviour: the sport segment is ignored, so this still")
    print("    returns the same data -- sportIds only labels the record in match mode)")
    bad = await run_match(target, 3, {"summary": False, "statistics": True}, None)
    print("   ", {"_error": bad.get("_error"), "statistics": len(bad.get("statistics") or [])})
    assert bad.get("_error") is None and bad.get("statistics"), \
        "sport segment started mattering upstream -- re-read CRAWLING_METHOD.md section 5"

    print("\n== reference ==")
    ref = await run_reference(None)
    for r in ref:
        print(f"   sport {r['sportId']:>2} {r['sportName']:<18} named={r['isNamed']} "
              f"matchesToday={r['matchesToday']:<4} {r['sampleTournament'][:40]}")
    print(f"-> {len(ref)} sport(s)\n")

    print("== error paths ==")
    print("   ", await run_match("not-a-real-id-!!", 1, {}, None))


async def main():
    if len(sys.argv) < 2 or sys.argv[1] == "all":
        await smoke()
        return
    mode = sys.argv[1]
    if mode == "fixtures":
        sport = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        day = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        show(await run_fixtures([sport], [day], n, None), 3, SUMMARY_KEYS)
    elif mode == "live":
        sport = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        show(await run_live([sport], n, None), 5, SUMMARY_KEYS)
    elif mode == "match":
        sport = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        rec = await run_match(sys.argv[2], sport, {"summary": True, "statistics": True,
                                                   "lineups": True, "headToHead": True}, None)
        print(json.dumps(rec, ensure_ascii=False, indent=2)[:3000])
    elif mode == "reference":
        show(await run_reference(None), 30)
    else:
        print(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
