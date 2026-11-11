"""Local smoke test -- exercises every mode against the live API, no Apify SDK.

    python test_local.py            # fast pass over all 8 modes
    python test_local.py videos     # one mode only

Prints a per-mode PASS/FAIL table and a sample record, and exits non-zero if any
mode fails, so it can gate a deploy.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from unittest.mock import patch

# The actor module imports `apify`; stub the bits we touch so the test can run
# without an Apify environment.
RECORDS: list[dict] = []


class _FakeActor:
    @staticmethod
    async def push_data(record):
        RECORDS.append(record)

    @staticmethod
    async def set_value(*_a, **_k):
        return None


def _install_stub() -> None:
    import types

    module = types.ModuleType("apify")
    module.Actor = _FakeActor
    sys.modules.setdefault("apify", module)


_install_stub()

from src.client import HaystackClient  # noqa: E402
from src.main import (  # noqa: E402
    RunCounters,
    run_channels,
    run_discover,
    run_local_events,
    run_polls,
    run_search,
    run_taxonomy,
    run_video_detail,
    run_videos,
)
from src.targets import parse_target  # noqa: E402


async def _collect(coro) -> list[dict]:
    start = len(RECORDS)
    with patch("src.main.Actor", _FakeActor):
        await coro
    return RECORDS[start:]


async def mode_videos(client, counters):
    out = []
    for raw in ["news", "channel/abc7", "tag/trump", "location/houston-tx",
                "https://www.haystack.tv/sports"]:
        target = parse_target(raw)
        out += await _collect(run_videos(client, target, counters, 50, False))
    return out


async def mode_video_detail(client, counters):
    # Resolve a live video id first so the test never depends on a stale slug.
    target = parse_target("news")
    feed = await _collect(run_videos(client, target, counters, 3, False))
    videos = [r for r in feed if r.get("recordType") == "VIDEO" and r.get("slug")]
    if not videos:
        raise AssertionError("Could not find a live video to request detail for.")
    slug = videos[0]["slug"]
    print(f"      anchoring on live slug: {slug}")
    return await _collect(
        run_video_detail(client, parse_target(f"/v/{slug}"), counters)
    )


async def mode_search(client, counters):
    out = []
    for query in ["ukraine", "federal reserve"]:
        out += await _collect(run_search(client, query, counters, 50))
    return out


async def mode_discover(client, counters):
    out = []
    for query in ["trump", "houston"]:
        out += await _collect(run_discover(client, query, counters))
    return out


async def mode_channels(client, counters):
    return await _collect(run_channels(client, counters))


async def mode_taxonomy(client, counters):
    return await _collect(run_taxonomy(client, counters))


async def mode_polls(client, counters):
    return await _collect(run_polls(client, counters))


async def mode_local_events(client, counters):
    return await _collect(run_local_events(client, "houston-tx", counters, True))


MODES = {
    "videos": (mode_videos, 60),
    "video-detail": (mode_video_detail, 1),
    "search": (mode_search, 20),
    "discover": (mode_discover, 2),
    "channels": (mode_channels, 300),
    "taxonomy": (mode_taxonomy, 300),
    "polls": (mode_polls, 20),
    "local-events": (mode_local_events, 15),
}


def check(name: str, records: list[dict], min_rows: int) -> tuple[bool, str]:
    data = [r for r in records if r.get("recordType") != "ERROR"]
    errors = [r for r in records if r.get("recordType") == "ERROR"]
    if len(data) < min_rows:
        return False, f"only {len(data)} data rows (want >= {min_rows}); errors={len(errors)}"

    required = {"_input", "_source", "_scrapedAt", "recordType"}
    for record in data:
        missing = required - set(record)
        if missing:
            return False, f"record missing envelope keys {sorted(missing)}"

    types = Counter(r["recordType"] for r in records)
    detail = ", ".join(f"{k}={v}" for k, v in types.most_common())
    if errors:
        detail += f" | first error: {errors[0].get('_error')}: {errors[0].get('_errorDetail','')[:90]}"
    return True, detail


async def main() -> int:
    wanted = sys.argv[1:] or list(MODES)
    unknown = [m for m in wanted if m not in MODES]
    if unknown:
        print(f"Unknown mode(s): {unknown}. Valid: {list(MODES)}")
        return 2

    results: list[tuple[str, bool, str]] = []
    async with HaystackClient() as client:
        for name in wanted:
            fn, min_rows = MODES[name]
            counters = RunCounters()
            print(f"\n=== {name} ===")
            try:
                records = await fn(client, counters)
                ok, detail = check(name, records, min_rows)
            except Exception as exc:  # a crashing mode is a failing mode
                ok, detail, records = False, f"raised {type(exc).__name__}: {exc}", []
            results.append((name, ok, detail))
            print(f"  {'PASS' if ok else 'FAIL'}  {detail}")
            sample = next((r for r in records if r.get("recordType") != "ERROR"), None)
            if sample:
                preview = json.dumps(sample, ensure_ascii=False, default=str)
                print(f"  sample: {preview[:400]}")

    print("\n" + "=" * 72)
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:14s} {detail[:110]}")
    failed = [n for n, ok, _ in results if not ok]
    print("=" * 72)
    print(f"{len(results) - len(failed)}/{len(results)} modes passed."
          + (f"  FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
