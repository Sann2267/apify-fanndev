"""Local smoke test: runs every mode against the live site, without Apify.

Usage:
    python test_local.py            # all modes
    python test_local.py categoryProducts productDetail
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import sys
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.client import IndotradingClient
from src.modes import MODES

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
)

CASES: dict[str, dict[str, Any]] = {
    "categoryTree": {},
    "categoryProducts": {
        "categories": ["jual-pressure-washer"],
        "maxPages": 2,
        "includeContact": True,
        "includeLastLogin": True,
    },
    "searchProducts": {
        "searchTerms": ["excavator komatsu pc200"],
        "maxPages": 1,
    },
    "productDetail": {
        "productUrls": [
            "https://www.indotrading.com/solusijaya10/"
            "high-pressure-cleaner-w250-18dpt-with-engine-yanmar-p1146289.aspx",
            "https://www.indotrading.com/nosuchsupplier/nope-p999999999.aspx",
        ],
        "includeContact": True,
    },
    "supplierProfile": {
        "suppliers": ["lavorpro", "https://www.indotrading.com/devsaanindustech"],
        "includeSupplierProducts": True,
        "includeLastLogin": True,
        "maxPages": 2,
    },
    "supplierDirectory": {
        "categories": ["jual-pressure-washer"],
        "maxPages": 2,
    },
    "searchSuppliers": {
        "searchTerms": ["pompa"],
        "maxPages": 1,
    },
    # Negative controls: a dead category slug and a dead supplier slug must
    # each produce exactly one not_found row, never a silent empty dataset.
    "_deadCategory": {
        "_mode": "categoryProducts",
        "categories": ["jual-zzzz-tidak-ada-kategori-ini"],
        "maxPages": 1,
    },
    "_deadSupplier": {
        "_mode": "supplierProfile",
        "suppliers": ["zzzz-supplier-tidak-ada"],
    },
}

KEY_FIELDS = {
    "product": ("productId", "productName", "priceText", "companyName"),
    "supplier": ("companyName", "companyUrl", "membershipTier"),
    "category": ("categorySlug", "categoryName"),
}


async def run_case(name: str, spec: dict[str, Any]) -> tuple[int, int, bool]:
    mode = spec.pop("_mode", name)
    print("\n" + "=" * 72)
    print(f"CASE {name}  (mode={mode})")
    print("=" * 72)

    client = IndotradingClient()
    records: list[dict[str, Any]] = []
    try:
        async for record in MODES[mode](client, spec):
            records.append(record)
    finally:
        client.close()

    errors = [r for r in records if r.get("_error")]
    ok = len(records) - len(errors)
    print(f"  -> {len(records)} records ({ok} data, {len(errors)} diagnostic)")

    if records:
        sample = next((r for r in records if not r.get("_error")), records[0])
        print("  sample:")
        print("    " + json.dumps(sample, ensure_ascii=False, indent=2)[:1400]
              .replace("\n", "\n    "))

    # Field-coverage check on the data rows: a parser that quietly stops
    # matching shows up here as a column of zeros, not as a crash.
    by_type: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if record.get("_error"):
            continue
        by_type.setdefault(record.get("recordType", "?"), []).append(record)

    healthy = True
    for record_type, rows in by_type.items():
        fields = KEY_FIELDS.get(record_type)
        if not fields:
            continue
        print(f"  coverage [{record_type}] over {len(rows)} rows:")
        for field in fields:
            filled = sum(1 for r in rows if r.get(field) not in (None, ""))
            pct = 100 * filled / len(rows)
            flag = "" if pct >= 90 else "   <-- LOW"
            if pct < 90:
                healthy = False
            print(f"     {field:24s} {filled:4d}/{len(rows):<4d} ({pct:5.1f}%){flag}")

    # Enrichment is opt-in and best-effort, so it is reported rather than
    # graded: a low WhatsApp rate usually means sellers with no WhatsApp
    # button, not a broken lookup, and the two are told apart by _warning.
    if spec.get("includeContact") or spec.get("includeLastLogin"):
        rows = [r for r in records if r.get("recordType") == "product"] or records
        for field in ("whatsappNumber", "lastLoginMinutesAgo"):
            present = [r for r in rows if field in r]
            if not present:
                continue
            filled = sum(1 for r in present if r.get(field) not in (None, ""))
            print(
                f"  enrichment {field:22s} {filled:4d}/{len(present):<4d} "
                f"({100 * filled / len(present):5.1f}%)"
            )
        warns: dict[str, int] = {}
        for r in rows:
            if r.get("_warning"):
                warns[r["_warning"]] = warns.get(r["_warning"], 0) + 1
        if warns:
            print(f"  warnings: {warns}")

    for record in errors[:3]:
        print(f"  error row: {record['_error']} | {record.get('_errorDetail','')[:110]}")

    return len(records), len(errors), healthy


async def main() -> None:
    wanted = sys.argv[1:] or list(CASES)
    summary: list[tuple[str, int, int, bool]] = []
    for name in wanted:
        if name not in CASES:
            print(f"Unknown case {name!r}; known: {', '.join(CASES)}")
            continue
        try:
            total, errs, healthy = await run_case(name, dict(CASES[name]))
            summary.append((name, total, errs, healthy))
        except Exception as exc:  # noqa: BLE001 - keep testing the other modes
            logging.exception("Case %s blew up", name)
            summary.append((name, 0, -1, False))

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    for name, total, errs, healthy in summary:
        status = "FAIL" if (errs < 0 or total == 0 or not healthy) else "ok"
        print(f"  {status:5s} {name:22s} records={total:<5d} errors={errs}")


if __name__ == "__main__":
    asyncio.run(main())
