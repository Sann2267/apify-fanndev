"""Standalone local runner -- exercises every mode without the Apify platform.

Usage:
    python test_local.py profile [username]
    python test_local.py spotlight [username]
    python test_local.py highlights [username]
    python test_local.py lenses [username]
    python test_local.py related [username] [depth]
    python test_local.py trending
    python test_local.py top-lenses
    python test_local.py reference
    python test_local.py all          # smoke-test every mode
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.constants import DEFAULT_LOCALE
from src.main import (
    run_related,
    run_reference,
    run_top_lenses,
    run_trending,
    run_usernames,
)


async def _no_proxy():
    return None


def show(records, limit=2, keys=None):
    for r in records[:limit]:
        if keys:
            print("   ", {k: r.get(k) for k in keys})
        else:
            print(json.dumps(r, ensure_ascii=False, indent=2)[:900], "...")
    print(f"-> {len(records)} record(s)\n")


async def collect(mode, usernames, max_items=50, concurrency=2):
    out = []

    async def push(records):
        out.extend(records)

    await run_usernames(mode, usernames, DEFAULT_LOCALE, max_items, concurrency, _no_proxy, push)
    return out


PROFILE_KEYS = ["username", "displayName", "subscriberCount", "isVerified", "category",
                "spotlightCount", "lensCount", "relatedAccountCount"]
SPOTLIGHT_KEYS = ["username", "title", "viewCount", "durationMs", "uploadedAt", "snapCount"]
HIGHLIGHT_KEYS = ["username", "highlightKind", "storyTypeName", "title", "snapCount", "firstSnapAt"]
LENS_KEYS = ["lensName", "creatorDisplayName", "isOfficialSnapLens", "lensId", "category"]


async def smoke():
    print("== profile: nasa + netflix ==")
    profiles = await collect("profile", ["nasa", "https://www.snapchat.com/add/netflix"])
    show(profiles, 2, PROFILE_KEYS)
    assert profiles and not profiles[0].get("_error"), "profile mode returned no usable row"
    assert profiles[0].get("subscriberCount") is not None, "subscriberCount missing"
    assert profiles[0].get("relatedAccounts"), "relatedAccounts missing -- the discovery path is broken"

    print("== profile: nonexistent username must fail loud ==")
    missing = await collect("profile", ["zzqqxx_not_a_real_user_123"])
    show(missing, 1, ["_input", "_error", "_errorDetail"])
    assert missing[0].get("_error") == "not_found", "unknown username did not produce not_found"

    print("== spotlight: nasa ==")
    spot = await collect("spotlight", ["nasa"])
    show(spot, 2, SPOTLIGHT_KEYS)
    assert spot and not spot[0].get("_error"), "spotlight mode returned no usable row"
    assert any(r.get("viewCount") for r in spot), "no Spotlight row carried a view count"
    assert any(r.get("videoUrl") for r in spot), "no Spotlight row carried a video URL"

    print("== highlights: nasa ==")
    hl = await collect("highlights", ["nasa"])
    show(hl, 2, HIGHLIGHT_KEYS)
    assert hl and not hl[0].get("_error"), "highlights mode returned no usable row"
    assert any((r.get("snaps") or [{}])[0].get("mediaUrl") for r in hl), "no highlight carried snap media"
    # Snapchat boxes some scalars as {"value": ...}; a dict here means an
    # unwrap was missed and the dataset schema would reject the row upstream.
    assert all(isinstance(r.get("title"), (str, type(None))) for r in hl), "highlight title is not a plain string"

    print("== lenses: netflix (nasa has 3, netflix has ~16) ==")
    lenses = await collect("lenses", ["netflix"])
    show(lenses, 2, LENS_KEYS)
    assert lenses and not lenses[0].get("_error"), "lenses mode returned no usable row"

    print("== related: depth 1 from nasa ==")
    rel = []

    async def push(records):
        rel.extend(records)

    await run_related(["nasa"], DEFAULT_LOCALE, 1, 8, 2, _no_proxy, push)
    show(rel, 3, PROFILE_KEYS + ["relatedDepth"])
    assert len(rel) > 1, "related mode did not expand beyond the seed"

    print("== trending: public Spotlight feed ==")
    tr = await run_trending(DEFAULT_LOCALE, 10, None)
    show(tr, 2, ["feedIndex", "title", "creatorUsername", "viewCount", "snapCount"])
    assert tr and not tr[0].get("_error"), "trending mode returned no usable row"

    print("== top-lenses: Lens hub chart ==")
    tl = await run_top_lenses(DEFAULT_LOCALE, 10, None)
    show(tl, 2, LENS_KEYS)
    assert tl and not tl[0].get("_error"), "top-lenses mode returned no usable row"

    print("== reference: probe every surface ==")
    ref = await run_reference(DEFAULT_LOCALE, None)
    for r in ref:
        print("   ", r.get("surface"), r.get("isAvailable"), r.get("detail"), r.get("sample"))
    assert all(r.get("isAvailable") for r in ref), "a public surface stopped answering"

    print("\nALL MODES OK")


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    if mode == "all":
        await smoke()
    elif mode in ("profile", "spotlight", "highlights", "lenses"):
        show(await collect(mode, [arg or "nasa"]), 3)
    elif mode == "related":
        out = []

        async def push(records):
            out.extend(records)

        depth = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        await run_related([arg or "nasa"], DEFAULT_LOCALE, depth, 20, 2, _no_proxy, push)
        show(out, 5, PROFILE_KEYS + ["relatedDepth"])
    elif mode == "trending":
        show(await run_trending(DEFAULT_LOCALE, 25, None), 3)
    elif mode == "top-lenses":
        show(await run_top_lenses(DEFAULT_LOCALE, 25, None), 3)
    elif mode == "reference":
        show(await run_reference(DEFAULT_LOCALE, None), 5)
    else:
        print(__doc__)


asyncio.run(main())
