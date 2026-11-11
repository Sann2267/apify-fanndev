"""Local smoke test: runs every mode against the live site, without Apify.

Usage:
    python test_local.py                # all cases
    python test_local.py idSearch sgSearch
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import sys
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.client import NinetyNineClient
from src.modes import MODES

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

CASES: dict[str, dict[str, Any]] = {
    "idSearch": {
        "idSearchTargets": ["jual/rumah"],
        "maxPages": 2,
    },
    "idSearchFiltered": {
        "_mode": "idSearch",
        "idSearchTargets": ["jual/rumah/jakarta-selatan"],
        "minPrice": 1000000000,
        "maxPrice": 3000000000,
        "maxPages": 2,
        "includeProjectPlacements": False,
    },
    "idLocations": {"idSearchTargets": ["jual/rumah"]},
    "idListingDetail": {
        "idListingSlugs": [
            "rumah-dijual-24miliar-cilandak-cp-54195423533",
            "slug-yang-pasti-tidak-ada-123456789",
        ]
    },
    "sgSearch": {"sgSearchTargets": ["rent"], "maxPages": 2},
    "sgListingDetail": {
        "sgListingUrls": [
            "https://www.99.co/singapore/rooms/property/"
            "335a-yishun-street-31-hdb-PBi5f6nP6qK47XRZKadBXm"
        ]
    },
    "sgHdbResalePrices": {},
    # Negative controls
    "_badTarget": {
        "_mode": "idSearch",
        "idSearchTargets": ["beli/rumah"],  # not jual/sewa
        "maxPages": 1,
    },
    "_ceiling": {
        # Proves the 9-page ceiling is handled as a clean stop, not a crash.
        "_mode": "idSearch",
        "idSearchTargets": ["jual/rumah"],
        "maxPages": 50,
        "maxItemsPerTarget": 400,
    },
}

KEY_FIELDS = {
    "idListing": ("id", "title", "url", "price"),
    "idListingDetail": ("id", "title", "price"),
    "idLocation": ("locationName", "urlSlug"),
    "sgListing": ("listingId", "listingUrl", "address"),
    "sgListingDetail": ("listingId", "listingUrl"),
    "sgHdbMedianPrice": ("columns", "values"),
}


async def run_case(name: str, spec: dict[str, Any]) -> tuple[int, int, bool]:
    mode = spec.pop("_mode", name)
    print("\n" + "=" * 72)
    print(f"CASE {name}  (mode={mode})")
    print("=" * 72)

    client = NinetyNineClient()
    records: list[dict[str, Any]] = []
    try:
        async for record in MODES[mode](client, spec):
            records.append(record)
    finally:
        client.close()

    errors = [r for r in records if r.get("_error")]
    print(f"  -> {len(records)} records ({len(records) - len(errors)} data, "
          f"{len(errors)} diagnostic)")

    if records:
        sample = next((r for r in records if not r.get("_error")), records[0])
        print("  sample:")
        print("    " + json.dumps(sample, ensure_ascii=False, indent=2)[:1100]
              .replace("\n", "\n    "))

    by_type: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        if not r.get("_error"):
            by_type.setdefault(r.get("recordType", "?"), []).append(r)

    healthy = True
    for rtype, rows in by_type.items():
        fields = KEY_FIELDS.get(rtype)
        if not fields:
            continue
        print(f"  coverage [{rtype}] over {len(rows)} rows:")
        for f in fields:
            filled = sum(1 for r in rows if r.get(f) not in (None, "", [], {}))
            pct = 100 * filled / len(rows)
            if pct < 90:
                healthy = False
            print(f"     {f:22s} {filled:4d}/{len(rows):<4d} ({pct:5.1f}%)"
                  f"{'   <-- LOW' if pct < 90 else ''}")

    warns: dict[str, int] = {}
    for r in records:
        if r.get("_warning"):
            warns[r["_warning"]] = warns.get(r["_warning"], 0) + 1
    if warns:
        print(f"  warnings: {warns}")

    for r in errors[:3]:
        print(f"  error row: {r['_error']} | {r.get('_errorDetail','')[:110]}")

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
        except Exception:  # noqa: BLE001 - keep testing the other modes
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
