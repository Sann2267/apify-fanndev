"""Smoke test every mode against live Instagram, without the Apify platform.

Run from the actor directory:

    python test_local.py              # all modes
    python test_local.py reels posts  # only the named modes

Uses no proxy, so it is subject to the same per-IP throttling a proxyless
production run would hit; a login wall here means the IP is cooling down, not
that the parser broke.
"""

import asyncio
import json
import sys

# Captions are full of emoji and the Windows console defaults to cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import InstagramClient
from src.constants import ALL_MODES
from src.modes import SCRAPERS

TARGETS = {
    "profile": "nasa",
    "posts": "nasa",
    "reels": "nasa",
    "post_detail": "DcOX3hWFiey",
    "location": "212988663",
}

OPTIONS = {"maxItems": 18, "includeComments": True, "locationTab": "recent"}

# Fields that must be present and non-null for a mode's happy path to count as
# a pass. A mode that returns rows of nulls is a failure, not a pass.
REQUIRED = {
    "profile": ("username", "followerCount", "biography"),
    "posts": ("shortcode", "url", "caption"),
    "reels": ("shortcode", "playCount", "likeCount"),
    "post_detail": ("shortcode", "likeCount", "commentCount", "takenAt"),
    "location": ("shortcode", "locationName", "latitude", "likeCount"),
}


async def run_mode(client: InstagramClient, mode: str) -> bool:
    target = TARGETS[mode]
    print(f"\n{'=' * 72}\n### mode={mode} target={target}")
    try:
        rows = await SCRAPERS[mode](client, target, OPTIONS)
    except Exception as exc:
        print(f"  FAIL - raised {type(exc).__name__}: {exc}")
        return False

    print(f"  rows: {len(rows)}")
    if not rows:
        print("  FAIL - no rows")
        return False

    first = rows[0]
    if first.get("_error"):
        print(f"  FAIL - {first['_error']}: {first.get('_errorDetail')}")
        return False

    missing = [field for field in REQUIRED[mode] if first.get(field) in (None, "")]
    pages = sorted({row.get("_page") for row in rows})
    sources = sorted({row.get("_source") for row in rows})
    print(f"  pages: {pages}  sources: {sources}")
    if first.get("_warning"):
        print(f"  warning: {first['_warning'][:150]}")

    preview = {k: v for k, v in first.items() if not k.startswith("_")}
    for key in ("caption", "biography"):
        if isinstance(preview.get(key), str):
            preview[key] = preview[key][:80] + "..."
    if isinstance(preview.get("comments"), list):
        preview["comments"] = f"[{len(preview['comments'])} comments] " + json.dumps(
            preview["comments"][:1], ensure_ascii=False
        )[:160]
    print("  sample:", json.dumps(preview, ensure_ascii=False, indent=2)[:1400])

    if missing:
        print(f"  FAIL - required fields empty: {missing}")
        return False
    print(f"  PASS ({len(rows)} rows)")
    return True


async def main() -> None:
    modes = [m for m in sys.argv[1:] if m in ALL_MODES] or list(ALL_MODES)
    client = InstagramClient()
    results = {}
    try:
        for mode in modes:
            results[mode] = await run_mode(client, mode)
            await asyncio.sleep(2.0)
    finally:
        await client.close()

    print(f"\n{'=' * 72}\nSUMMARY")
    for mode, ok in results.items():
        print(f"  {mode:14s} {'PASS' if ok else 'FAIL'}")
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
