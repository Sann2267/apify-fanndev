"""Standalone local runner -- exercises every mode without the Apify platform.

Usage:
    python test_local.py                 # smoke-test all 15 modes
    python test_local.py posts bsky.app  # one mode, custom input
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import BlueskyClient
from src.main import MODE_HANDLERS, MODE_INPUT_FIELD, run_one, run_profile_batch

POST_URL = "https://bsky.app/profile/bsky.app/post/3l6oveex3ii2l"
FEED_URL = "https://bsky.app/profile/did:plc:z72i7hdynmk6r22z27h6tvur/feed/whats-hot"

# (mode, inputs, per-input cap)
PLAN = [
    ("profile", ["bsky.app", "@jay.bsky.team", "did:plc:z72i7hdynmk6r22z27h6tvur",
                 "this-handle-does-not-exist-xyz.bsky.social"], 5),
    ("posts", ["bsky.app"], 12),
    ("followers", ["bsky.app"], 12),
    ("follows", ["bsky.app"], 12),
    ("lists", ["bsky.app"], 5),
    ("starter-packs", ["bsky.app"], 5),
    ("post-detail", [POST_URL], 15),
    ("post-likes", [POST_URL], 12),
    ("post-reposts", [POST_URL], 12),
    ("post-quotes", [POST_URL], 8),
    ("search-users", ["news"], 10),
    ("feed", [FEED_URL], 8),
    ("trends", ["__singleton__"], 5),
    ("popular-feeds", ["__singleton__"], 8),
    # Last on purpose: this is the IP-throttled endpoint.
    ("search-posts", ["jakarta"], 10),
]

REQUIRED_ENVELOPE = ("_input", "_source", "_scrapedAt", "recordType")


def audit(mode, records):
    """Verify the envelope contract rather than just counting rows."""
    problems = []
    if not records:
        problems.append("ZERO records")
    for r in records:
        missing = [k for k in REQUIRED_ENVELOPE if k not in r]
        if missing:
            problems.append("missing {} in {}".format(missing, list(r)[:6]))
            break
    errors = [r for r in records if r.get("recordType") == "ERROR"]
    payload = [r for r in records if r.get("recordType") != "ERROR"]
    # Every input in PLAN is chosen to have real data, so zero payload
    # rows is a regression -- not an acceptable "empty result". This is
    # the check that catches the handle-vs-DID silent-empty bug class,
    # which otherwise shows up as a tidy-looking empty_result row.
    if not payload:
        problems.append("ZERO payload rows (only diagnostics)")
    # A record with only envelope keys means we pushed an empty payload.
    for r in payload:
        if len(r) <= len(REQUIRED_ENVELOPE):
            problems.append("payload-less record: {}".format(r))
            break
    return problems, len(payload), errors


async def run_mode(client, mode, inputs, cap, cfg):
    if mode == "profile":
        return await run_profile_batch(client, inputs, cfg, cap)
    handler = MODE_HANDLERS[mode]
    out = []
    for item in inputs:
        out.extend(await run_one(client, handler, item, cfg, cap))
    return out


async def main():
    cfg = {"threadDepth": 4, "sort": "latest"}
    client = BlueskyClient()
    plan = PLAN
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode not in MODE_INPUT_FIELD:
            print("unknown mode", mode)
            return 2
        inputs = sys.argv[2:] or ["__singleton__"]
        plan = [(mode, inputs, 10)]

    failures = []
    try:
        for mode, inputs, cap in plan:
            try:
                records = await run_mode(client, mode, inputs, cap, cfg)
            except Exception as exc:  # noqa: BLE001 -- report, keep going
                print("{:16s} CRASH {!r}".format(mode, exc))
                failures.append(mode)
                continue

            problems, n_payload, errors = audit(mode, records)
            types = sorted({r.get("recordType") for r in records})
            status = "FAIL" if problems else "ok  "
            print("{:16s} {}  rows={:<4d} payload={:<4d} err={:<2d} types={}".format(
                mode, status, len(records), n_payload, len(errors), types))
            for p in problems:
                print("      ! {}".format(p[:160]))
            for e in errors:
                print("      - _error={} {}".format(
                    e.get("_error"), str(e.get("_errorDetail"))[:90]))
            if problems:
                failures.append(mode)
            if records:
                sample = next((r for r in records if r.get("recordType") != "ERROR"), records[0])
                print("      sample: {}".format(
                    json.dumps(sample, ensure_ascii=False)[:220]))
    finally:
        await client.close()

    print("\n{}/{} modes clean".format(len(plan) - len(failures), len(plan)))
    if failures:
        print("FAILED: {}".format(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
