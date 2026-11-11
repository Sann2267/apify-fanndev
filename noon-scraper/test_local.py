"""Local test harness for the noon.com scraper.

Runs every mode against the live site without the Apify platform, so a failure
points at this actor's logic rather than at deployment. Each check asserts on
the SHAPE of what came back, not just on "no exception" -- a mode that returns
zero rows, or rows with no price, is a failure here even though the HTTP call
succeeded.

Usage:
    python test_local.py            # all modes
    python test_local.py search     # one mode
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

sys.stdout.reconfigure(encoding="utf-8")

from src.client import NoonClient
from src.modes import MODES, Budget
from src.parsers import locale_of

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

SKU = "N70211544V"          # iPhone 17 Pro Max, multi-seller
BASE = {
    "country": "ae",
    "language": "en",
    "locale": locale_of("ae", "en"),
    "concurrency": 4,
    "limitPerPage": 200,
    "maxPages": 2,
}

CASES: dict[str, dict] = {
    "search": {**BASE, "searchKeywords": ["iphone"], "maxItems": 60},
    "category": {**BASE, "categoryPaths": ["electronics-and-mobiles"], "maxItems": 60},
    "brand": {**BASE, "brandCodes": ["apple"], "maxItems": 60},
    "product": {**BASE, "productSkus": [SKU]},
    "offers": {**BASE, "productSkus": [SKU]},
    "categoryTree": {**BASE, "categoryPaths": ["electronics-and-mobiles"], "maxItems": 80},
    "facets": {**BASE, "searchKeywords": ["laptop"], "maxItems": 40},
    "minutesSearch": {**BASE, "searchKeywords": ["milk"], "maxItems": 40},
    # Deliberate failures: the actor must emit a diagnostic row, not crash and
    # not silently return nothing.
    "product_bad": {**BASE, "productSkus": ["N00000000X"], "_mode": "product"},
    "product_garbage": {**BASE, "productSkus": ["not-a-sku-at-all"], "_mode": "product"},
    "search_nonsense": {**BASE, "searchKeywords": ["zzqqxx-no-such-product-zzz"],
                        "_mode": "search", "maxItems": 20},
    # URL input rather than a bare SKU.
    "product_url": {
        **BASE, "_mode": "product",
        "productSkus": [f"https://www.noon.com/uae-en/some-slug/{SKU}/p/"],
    },
    # A second storefront, to prove the locale switch really changes prices.
    "search_sa": {**BASE, "_mode": "search", "country": "sa",
                  "locale": locale_of("sa", "en"),
                  "searchKeywords": ["iphone"], "maxItems": 10},
}

# What each case must produce to count as passing.
EXPECT = {
    "search": {"min_rows": 50, "type": "PRODUCT", "need": ("sku", "name", "price")},
    "category": {"min_rows": 50, "type": "PRODUCT", "need": ("sku", "name", "price")},
    "brand": {"min_rows": 50, "type": "PRODUCT", "need": ("sku", "name", "price")},
    "product": {"min_rows": 1, "type": "PRODUCT_DETAIL",
                "need": ("sku", "product_title", "specifications")},
    "offers": {"min_rows": 2, "type": "OFFER", "need": ("store_name", "price", "offerRank")},
    "categoryTree": {"min_rows": 20, "type": "CATEGORY", "need": ("code", "id_category")},
    "facets": {"min_rows": 5, "type": "FACET", "need": ("code", "optionCount")},
    "minutesSearch": {"min_rows": 10, "type": "INSTANT_PRODUCT", "need": ("sku", "title", "price")},
    "product_bad": {"min_rows": 1, "type": "ERROR", "need": ("_error",)},
    "product_garbage": {"min_rows": 1, "type": "ERROR", "need": ("_error",)},
    "search_nonsense": {"min_rows": 0, "type": None, "need": ()},
    "product_url": {"min_rows": 1, "type": "PRODUCT_DETAIL", "need": ("sku",)},
    "search_sa": {"min_rows": 5, "type": "PRODUCT", "need": ("sku", "price")},
}


async def run_case(name: str, options: dict) -> tuple[bool, str]:
    mode = options.pop("_mode", name)
    budget = Budget(int(options.get("maxItems") or 0))
    client = NoonClient()
    rows: list[dict] = []
    try:
        async for rec in MODES[mode](client, options, budget):
            rows.append(rec)
            if budget.exhausted:
                break
    except Exception as exc:  # noqa: BLE001 - the harness reports, never hides
        await client.close()
        return False, f"raised {type(exc).__name__}: {exc}"
    finally:
        await client.close()

    exp = EXPECT[name]
    if len(rows) < exp["min_rows"]:
        return False, f"got {len(rows)} rows, expected >= {exp['min_rows']}"
    if not rows:
        return True, "0 rows (allowed for this case)"

    data_rows = [r for r in rows if r.get("recordType") != "ERROR"]
    check = data_rows or rows
    if exp["type"] and check[0].get("recordType") != exp["type"]:
        return False, f"recordType {check[0].get('recordType')!r}, expected {exp['type']!r}"
    missing = [f for f in exp["need"] if check[0].get(f) in (None, "", [])]
    if missing:
        return False, f"first row missing {missing}; keys={sorted(check[0])[:14]}"
    for env in ("_input", "_source", "_scrapedAt", "recordType"):
        if env not in rows[0]:
            return False, f"envelope field {env} missing"

    sample = check[0]
    bits = [f"{len(rows)} rows"]
    for key in ("sku", "name", "title", "product_title", "store_name", "code", "price"):
        if sample.get(key) not in (None, "", []):
            bits.append(f"{key}={str(sample[key])[:42]!r}")
    if sample.get("currency"):
        bits.append(f"currency={sample['currency']}")
    return True, " | ".join(bits)


async def main() -> None:
    wanted = sys.argv[1:] or list(CASES)
    results: dict[str, tuple[bool, str]] = {}
    for name in wanted:
        if name not in CASES:
            print(f"!! unknown case {name}")
            continue
        print(f"\n{'='*72}\n### {name}\n{'='*72}")
        ok, detail = await run_case(name, dict(CASES[name]))
        results[name] = (ok, detail)
        print(f"{'PASS' if ok else 'FAIL'}: {detail}")

    print(f"\n{'='*72}\nSUMMARY\n{'='*72}")
    for name, (ok, detail) in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name:18s} {detail[:100]}")
    failed = [n for n, (ok, _) in results.items() if not ok]
    print(f"\n{len(results)-len(failed)}/{len(results)} passed")
    if failed:
        print("FAILED:", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
