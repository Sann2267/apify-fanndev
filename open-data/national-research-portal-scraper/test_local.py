"""Standalone local runner.

Usage:
    python test_local.py documents [portal] [query]
    python test_local.py journals [query]
    python test_local.py authors [query]
    python test_local.py reference
    python test_local.py all
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_portal, run_reference


def show(records, limit=3, keys=None):
    for r in records[:limit]:
        print("   ", {k: r.get(k) for k in keys} if keys else json.dumps(r, ensure_ascii=False)[:420])
    print(f"-> {len(records)} record(s)\n")


ART_KEYS = ["portal", "title", "authorNames", "source", "year", "url", "totalResults"]
JOU_KEYS = ["portal", "title", "publisher", "issn", "eissn", "url"]
AUT_KEYS = ["portal", "name", "affiliation", "documentCount", "url"]


async def smoke():
    print("== reference: which portals are live ==")
    ref = await run_reference(None)
    for r in ref:
        print("   ", r.get("portal"), r.get("isAvailable"), r.get("detail"), r.get("sample"))
    assert all(r["isAvailable"] for r in ref), "a portal is not answering"

    print("\n== documents: Garuda ==")
    g = await run_portal("garuda", "documents", "machine learning", 12, 2, False, None)
    show(g, 2, ART_KEYS)
    assert g and not g[0].get("_error"), "garuda documents failed"
    assert g[0]["title"] and g[0]["url"], "garuda article missing title or url"
    assert g[0]["authorNames"], "garuda article missing authors"
    assert g[0]["totalResults"] and g[0]["totalResults"] > 1000, "garuda total not parsed"
    assert len({r["page"] for r in g}) > 1, "garuda pagination did not advance"

    print("== documents: CiNii ==")
    c = await run_portal("cinii", "documents", "machine learning", 8, 2, False, None)
    show(c, 2, ART_KEYS)
    assert c and not c[0].get("_error"), "cinii documents failed"
    assert c[0]["title"] and c[0]["url"], "cinii article missing title or url"
    assert c[0]["totalResults"] and c[0]["totalResults"] > 100, "cinii total not parsed"

    print("== documents: KCI ==")
    k = await run_portal("kci", "documents", "machine learning", 8, 1, False, None)
    show(k, 2, ART_KEYS)
    assert k and not k[0].get("_error"), "kci documents failed"
    assert k[0]["title"] and k[0]["documentId"], "kci article missing title or id"

    print("== journals: Garuda ==")
    j = await run_portal("garuda", "journals", "teknologi", 10, 1, False, None)
    show(j, 2, JOU_KEYS)
    assert j and not j[0].get("_error"), "garuda journals failed"
    assert j[0]["title"] and j[0]["url"], "journal row missing title or url"

    print("== authors: Garuda ==")
    a = await run_portal("garuda", "authors", "budi", 10, 1, False, None)
    show(a, 2, AUT_KEYS)
    assert a and not a[0].get("_error"), "garuda authors failed"
    assert a[0]["name"] and a[0]["authorId"], "author row missing name or id"

    print("== unsupported combination must say so ==")
    u = await run_portal("cinii", "authors", "smith", 5, 1, False, None)
    show(u, 1, ["portal", "_error", "_errorDetail"])
    assert u[0]["_error"] == "unsupported_mode", "unsupported mode was not reported"

    print("== nonsense query still answers cleanly ==")
    n = await run_portal("garuda", "documents", "zzqqxxnonsensequery12345", 5, 1, False, None)
    show(n, 1, ["portal", "_error", "_errorDetail"])
    assert n[0].get("_error") == "no_results", "empty result set was not reported"

    print("\nALL MODES OK")


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "all":
        await smoke()
    elif mode == "reference":
        show(await run_reference(None), 5)
    elif mode == "documents":
        portal = sys.argv[2] if len(sys.argv) > 2 else "garuda"
        query = sys.argv[3] if len(sys.argv) > 3 else "machine learning"
        show(await run_portal(portal, "documents", query, 20, 2, False, None), 5, ART_KEYS)
    elif mode in ("journals", "authors"):
        query = sys.argv[2] if len(sys.argv) > 2 else "teknologi"
        show(await run_portal("garuda", mode, query, 20, 1, False, None), 5,
             JOU_KEYS if mode == "journals" else AUT_KEYS)
    else:
        print(__doc__)


asyncio.run(main())
