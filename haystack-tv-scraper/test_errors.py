"""Negative-path test -- bad inputs must produce error records, not crashes."""

from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import patch

RECORDS: list[dict] = []


class _FakeActor:
    @staticmethod
    async def push_data(record):
        RECORDS.append(record)

    @staticmethod
    async def set_value(*_a, **_k):
        return None


_module = types.ModuleType("apify")
_module.Actor = _FakeActor
sys.modules.setdefault("apify", _module)

from src.client import HaystackClient  # noqa: E402
from src.main import (  # noqa: E402
    RunCounters,
    run_discover,
    run_local_events,
    run_search,
    run_video_detail,
    run_videos,
)
from src.targets import InvalidTarget, parse_target, parse_targets  # noqa: E402


async def collect(coro):
    start = len(RECORDS)
    with patch("src.main.Actor", _FakeActor):
        await coro
    return RECORDS[start:]


async def main() -> int:
    failures = []

    # --- parser rejects junk without touching the network --------------------
    for junk in ["", "   ", "https://example.com/news", "a b c", "https://youtube.com/x"]:
        try:
            target = parse_target(junk)
            failures.append(f"parse_target({junk!r}) should have raised, got {target}")
        except InvalidTarget:
            pass
    good, bad = parse_targets(["news", "", "https://evil.com/x", {"url": "channel/abc7"}])
    print(f"parse_targets -> {len(good)} good, {len(bad)} bad  (expect 2 / 2)")
    if len(good) != 2 or len(bad) != 2:
        failures.append(f"parse_targets split wrong: good={good} bad={bad}")

    counters = RunCounters()
    async with HaystackClient() as client:
        cases = [
            (
                "nonexistent category",
                run_videos(client, parse_target("thiscategorydoesnotexist12345"), counters, 50, False),
            ),
            (
                "nonexistent channel",
                run_videos(client, parse_target("channel/notarealchannel12345"), counters, 50, False),
            ),
            (
                "nonexistent tag",
                run_videos(client, parse_target("tag/zzzznotarealtag12345"), counters, 50, False),
            ),
            (
                "nonexistent video",
                run_video_detail(client, parse_target("/v/definitely-not-a-real-video-zzz999"), counters),
            ),
            (
                "gibberish search",
                run_search(client, "zzqqxx99nonsensequery", counters, 50),
            ),
            (
                "gibberish discover",
                run_discover(client, "zzqqxx99nonsensequery", counters),
            ),
            (
                "nonexistent location",
                run_local_events(client, "notarealcity-zz", counters, False),
            ),
        ]
        for name, coro in cases:
            records = await collect(coro)
            errors = [r for r in records if r.get("recordType") == "ERROR"]
            data = [r for r in records if r.get("recordType") != "ERROR"]
            kinds = sorted({r.get("_error") for r in errors})
            print(f"  {name:24s} -> {len(data)} data, {len(errors)} error {kinds}")
            if not records:
                failures.append(f"{name}: emitted NOTHING (input vanished silently)")

    print("\n" + "=" * 70)
    if failures:
        for f in failures:
            print("  FAIL:", f)
        return 1
    print("  All negative paths emitted a record instead of crashing or vanishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
