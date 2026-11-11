"""Local smoke test -- exercises every mode against live Shopify stores.

    python test_local.py            # all modes
    python test_local.py products   # one mode

Prints a PASS/FAIL table and exits non-zero if any mode fails.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from collections import Counter
from unittest.mock import patch

RECORDS: list[dict] = []
KV: dict = {}


class _FakeStore:
    async def get_value(self, key, default=None):
        return KV.get(key, default)

    async def set_value(self, key, value, **_k):
        KV[key] = value


class _FakeActor:
    @staticmethod
    async def push_data(record):
        RECORDS.append(record)

    @staticmethod
    async def set_value(*_a, **_k):
        return None

    @staticmethod
    async def open_key_value_store(*_a, **_k):
        return _FakeStore()


_module = types.ModuleType("apify")
_module.Actor = _FakeActor
sys.modules.setdefault("apify", _module)

from src.client import ShopifyClient  # noqa: E402
from src.main import RunCounters, process_store  # noqa: E402

OPTS = {
    "maxProducts": 300,
    "newWithinDays": 45,
    "newestProducts": 5,
    "explodeVariants": False,
}

# A deliberately mixed list: classic Liquid themes, a headless store that needs
# the myshopify rescue, an apex/www quirk, and a non-Shopify control.
CLASSIC = ["allbirds.com", "brooklinen.com"]
HEADLESS = ["ruggable.com"]


async def collect(coro):
    start = len(RECORDS)
    with patch("src.main.Actor", _FakeActor):
        await coro
    return RECORDS[start:]


async def run_mode(mode, urls, opts=None):
    counters = RunCounters()
    out = []
    async with ShopifyClient() as client:
        for url in urls:
            out += await collect(
                process_store(client, url, mode, counters, {**OPTS, **(opts or {})})
            )
    return out


MODES = {
    "detect":         (lambda: run_mode("detect", CLASSIC + HEADLESS + ["nike.com"]), 3, {"STORE"}),
    "store-analysis": (lambda: run_mode("store-analysis", CLASSIC), 2, {"STORE", "NEW_PRODUCT"}),
    "products":       (lambda: run_mode("products", ["allbirds.com"], {"maxProducts": 40}), 40, {"PRODUCT"}),
    "products-var":   (lambda: run_mode("products", ["brooklinen.com"], {"maxProducts": 10, "explodeVariants": True}), 10, {"PRODUCT", "VARIANT"}),
    "new-products":   (lambda: run_mode("new-products", ["colourpop.com"], {"newWithinDays": 90}), 1, {"NEW_PRODUCT"}),
    "collections":    (lambda: run_mode("collections", ["brooklinen.com"]), 5, {"COLLECTION"}),
    "headless":       (lambda: run_mode("store-analysis", HEADLESS, {"maxProducts": 30}), 2, {"STORE", "NEW_PRODUCT"}),
    "changes":        (None, 0, set()),      # handled specially (needs two runs)
}


async def changes_mode():
    """Two consecutive runs: first stores a baseline, second diffs against it."""
    KV.clear()
    first = await run_mode("changes", ["allbirds.com"], {"maxProducts": 60})
    second = await run_mode("changes", ["allbirds.com"], {"maxProducts": 60})
    types_first = {r.get("recordType") for r in first}
    types_second = {r.get("recordType") for r in second}
    ok = "SNAPSHOT_BASELINE" in types_first and "CHANGE_SUMMARY" in types_second
    warn = next((r.get("_warning") for r in first if r.get("_warning")), None)
    detail = f"run1={sorted(types_first)} warn={warn} | run2={sorted(types_second)}"
    return ok, detail, first + second


def check(records, min_rows, want_types):
    data = [r for r in records if r.get("recordType") != "ERROR"]
    errors = [r for r in records if r.get("recordType") == "ERROR"]
    if len(data) < min_rows:
        kinds = [e.get("_error") for e in errors]
        return False, f"only {len(data)} data rows (want >= {min_rows}); errors={kinds[:3]}"

    required = {"_input", "_source", "_scrapedAt", "recordType"}
    for record in data:
        missing = required - set(record)
        if missing:
            return False, f"record missing envelope keys {sorted(missing)}"

    seen = {r["recordType"] for r in data}
    if want_types and not (want_types & seen):
        return False, f"expected any of {sorted(want_types)}, got {sorted(seen)}"

    counts = Counter(r["recordType"] for r in records)
    detail = ", ".join(f"{k}={v}" for k, v in counts.most_common())
    if errors:
        detail += f" | err: {errors[0].get('_error')}"
    return True, detail


async def main() -> int:
    wanted = sys.argv[1:] or list(MODES)
    unknown = [m for m in wanted if m not in MODES]
    if unknown:
        print(f"Unknown mode(s): {unknown}. Valid: {list(MODES)}")
        return 2

    results = []
    for name in wanted:
        print(f"\n=== {name} ===")
        try:
            if name == "changes":
                ok, detail, records = await changes_mode()
            else:
                fn, min_rows, want = MODES[name]
                records = await fn()
                ok, detail = check(records, min_rows, want)
        except Exception as exc:
            ok, detail, records = False, f"raised {type(exc).__name__}: {exc}", []
        results.append((name, ok, detail))
        print(f"  {'PASS' if ok else 'FAIL'}  {detail}")
        sample = next((r for r in records if r.get("recordType") != "ERROR"), None)
        if sample:
            print(f"  sample: {json.dumps(sample, ensure_ascii=False, default=str)[:360]}")

    print("\n" + "=" * 74)
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:15s} {detail[:108]}")
    failed = [n for n, ok, _ in results if not ok]
    print("=" * 74)
    print(f"{len(results) - len(failed)}/{len(results)} checks passed."
          + (f"  FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
