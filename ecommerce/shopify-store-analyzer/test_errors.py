"""Negative-path test -- bad inputs must produce labelled rows, never silence."""

from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import patch

RECORDS: list[dict] = []


class _FakeStore:
    async def get_value(self, key, default=None):
        return default

    async def set_value(self, *_a, **_k):
        return None


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
from src.extractor import price_summary  # noqa: E402
from src.main import RunCounters, process_store  # noqa: E402
from src.resolver import InvalidStoreUrl, normalise_input, parse_theme  # noqa: E402

OPTS = {"maxProducts": 20, "newWithinDays": 7, "newestProducts": 3, "explodeVariants": False}


async def collect(coro):
    start = len(RECORDS)
    with patch("src.main.Actor", _FakeActor):
        await coro
    return RECORDS[start:]


def unit_checks() -> list[str]:
    """Pure-function edge cases that must not need the network."""
    fails = []

    for junk in ["", "   ", "not a url", "http://", "://x"]:
        try:
            normalise_input(junk)
            fails.append(f"normalise_input({junk!r}) should have raised")
        except InvalidStoreUrl:
            pass

    # Apify's start-URL object form and bare hostnames must both work.
    for good, want in [
        ("allbirds.com", "https://allbirds.com"),
        ("https://www.allbirds.com/collections/x", "https://www.allbirds.com"),
        ({"url": "colourpop.com"}, "https://colourpop.com"),
        ("HTTPS://WWW.Allbirds.COM", "https://www.allbirds.com"),
    ]:
        got = normalise_input(good)
        if got != want:
            fails.append(f"normalise_input({good!r}) = {got!r}, want {want!r}")

    # Prices arrive as decimal STRINGS; compare_at == price is not a sale.
    summary = price_summary(
        [
            {"price": "24.00", "compare_at_price": "30.00", "available": True},
            {"price": "26.50", "compare_at_price": None, "available": False},
        ]
    )
    if not (summary["minPrice"] == 24.0 and summary["maxPrice"] == 26.5):
        fails.append(f"price range wrong: {summary}")
    if not summary["onSale"]:
        fails.append("onSale should be True when compare_at > price")
    if summary["availableVariantCount"] != 1 or not summary["inStock"]:
        fails.append(f"stock counting wrong: {summary}")

    equal = price_summary([{"price": "10.00", "compare_at_price": "10.00", "available": True}])
    if equal["onSale"]:
        fails.append("compare_at == price must NOT count as on sale")

    junk_prices = price_summary([{"price": None, "compare_at_price": "abc", "available": True}])
    if junk_prices["minPrice"] is not None:
        fails.append(f"unparseable prices must yield None, got {junk_prices}")

    if price_summary([])["variantCount"] != 0:
        fails.append("empty variant list must not crash")

    if parse_theme("<html>no theme here</html>") is not None:
        fails.append("parse_theme should return None when absent")
    if parse_theme('Shopify.theme = {broken json;') is not None:
        fails.append("parse_theme should return None on broken JSON")

    theme = parse_theme(
        'x Shopify.theme = {"name":"UTK | Production","id":1,"schema_name":null,'
        '"schema_version":null,"theme_store_id":null,"role":"main"}; y'
    )
    if not theme or theme["themeName"] != "UTK | Production":
        fails.append(f"theme name should fall back to label when schema_name null: {theme}")
    if theme and theme["isThemeStoreTheme"]:
        fails.append("theme_store_id null must mean isThemeStoreTheme False")
    return fails


async def main() -> int:
    failures = unit_checks()
    print(f"unit checks: {len(failures)} failure(s)")
    for f in failures:
        print("   FAIL:", f)

    counters = RunCounters()
    cases = [
        ("empty string", ""),
        ("garbage text", "not a url at all"),
        ("non-shopify site", "nike.com"),
        ("shopify w/o public api", "bombas.com"),
        ("nonexistent domain", "thisdomaindoesnotexist-zzq99.com"),
        ("non-store url path", "https://allbirds.com/pages/about"),
    ]
    async with ShopifyClient() as client:
        for name, url in cases:
            records = await collect(
                process_store(client, url, "store-analysis", counters, OPTS)
            )
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
    print("  All negative paths emitted a record; all unit edge cases correct.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
