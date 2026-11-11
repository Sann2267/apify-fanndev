"""Smoke test every mode against live TikTok, without the Apify platform.

Run from the actor directory:

    python test_local.py                  # all modes
    python test_local.py video profile    # only the named modes

Uses no proxy, so it is subject to the same per-IP throttle a proxyless
production run would hit. TikTok answers that with HTTP 503 after a handful of
requests -- a BLOCKED_AFTER_RETRIES here means the IP is cooling down, not that
the parser broke. The delay between modes is deliberately generous for that
reason.
"""

import asyncio
import json
import sys

# Captions are full of emoji and the Windows console defaults to cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import TikTokClient
from src.constants import ALL_MODES
from src.modes import SCRAPERS

TARGETS = {
    "video": "7626254334065511711",
    "profile": "complex",
    "hashtag": "nasa",
    "music": "7301919715965077506",
    "oembed": "https://www.tiktok.com/@complex/video/7626254334065511711",
}

OPTIONS = {"maxItems": 0}

# Fields that must be present and non-null for a mode's happy path to count as a
# pass. A mode that returns rows of nulls is a failure, not a pass -- that is the
# exact trap the consumer-page shells set during recon.
REQUIRED = {
    "video": ("videoId", "playCount", "diggCount", "authorUniqueId", "authorFollowerCount"),
    "profile": ("uniqueId", "followerCount", "heartCount"),
    "hashtag": ("videoId", "playlistType", "videoUrl"),
    "music": ("videoId", "playlistType", "entityVideoCount"),
    "oembed": ("videoId", "title", "authorUniqueId", "thumbnailUrl"),
}


async def run_mode(client: TikTokClient, mode: str) -> bool:
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

    if first.get("_warning"):
        print(f"  warning: {first['_warning'][:160]}")

    preview = {k: v for k, v in first.items() if not k.startswith("_")}
    for key in ("description", "signature", "authorSignature", "title"):
        if isinstance(preview.get(key), str) and len(preview[key]) > 80:
            preview[key] = preview[key][:80] + "..."
    for key in list(preview):
        if isinstance(preview[key], str) and preview[key].startswith("http") and len(preview[key]) > 90:
            preview[key] = preview[key][:90] + "..."
    print("  sample:", json.dumps(preview, ensure_ascii=False, indent=2)[:1600])

    missing = [field for field in REQUIRED[mode] if first.get(field) in (None, "")]
    if missing:
        print(f"  FAIL - required fields empty: {missing}")
        return False
    print(f"  PASS ({len(rows)} rows)")
    return True


async def main() -> None:
    modes = [m for m in sys.argv[1:] if m in ALL_MODES] or list(ALL_MODES)
    client = TikTokClient()
    results = {}
    try:
        for index, mode in enumerate(modes):
            results[mode] = await run_mode(client, mode)
            if index < len(modes) - 1:
                await asyncio.sleep(5.0)
    finally:
        await client.close()

    print(f"\n{'=' * 72}\nSUMMARY")
    for mode, ok in results.items():
        print(f"  {mode:10s} {'PASS' if ok else 'FAIL'}")
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
