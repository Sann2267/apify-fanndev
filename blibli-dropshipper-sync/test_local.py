"""Local smoke test against the live site.

    python test_local.py
"""

import asyncio
import json
import sys

from src.client import BlibliClient
from src.constants import (
    CHANGE_BACK_IN_STOCK,
    CHANGE_NAME_CHANGED,
    CHANGE_NEW,
    CHANGE_OUT_OF_STOCK,
    CHANGE_PRICE_DOWN,
    CHANGE_PRICE_UP,
    CHANGE_UNAVAILABLE,
    CHANGE_UNCHANGED,
    SYNC_NOT_FOUND,
    SYNC_OK,
)
from src.sync import (
    InvalidInput,
    chunked,
    clean_text,
    detect_changes,
    fetch_bulk,
    fetch_page,
    record_from_page,
    resolve_sku,
    snapshot_entry,
    sync_skus,
)

FULL = "--full" in sys.argv

# A live SanDisk card, a live Colgate item, and the SKU that exposed the
# bulk endpoint's silent-omission behaviour (live product, absent from bulk).
LIVE = "BLL-70058-00122"
LIVE2 = "COP-60023-00933"
BULK_OMITTED_BUT_LIVE = "VAM-43292-00654"
BOGUS = "ZZZ-99999-99999"

_JSON_TYPES = {"string": str, "number": (int, float), "integer": int,
               "boolean": bool, "object": dict, "array": list}


def load_output_schema() -> dict:
    with open(".actor/output_schema.json", encoding="utf-8") as fh:
        return json.load(fh)["fields"]["properties"]


def schema_violations(records: list, schema: dict) -> list:
    problems = []
    for record in records:
        for field, spec in schema.items():
            if field not in record:
                continue
            value = record[field]
            declared = spec.get("type")
            allowed = declared if isinstance(declared, list) else [declared]
            if value is None:
                if "null" not in allowed:
                    problems.append(f"{field}=null but type is {declared}")
                continue
            flat = []
            for name in allowed:
                mapped = _JSON_TYPES.get(name)
                if mapped is None:
                    continue
                flat.extend(mapped if isinstance(mapped, tuple) else (mapped,))
            if flat and (
                not isinstance(value, tuple(flat))
                or (isinstance(value, bool) and bool not in flat)
            ):
                problems.append(f"{field}={value!r} ({type(value).__name__}) vs {declared}")
    return sorted(set(problems))


def check(label: str, condition: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")
    return condition


def check_schema(records, schema) -> bool:
    problems = schema_violations(records, schema)
    return check("matches output_schema.json", not problems, "; ".join(problems[:4]))


async def collect(stream):
    return [r async for r in stream]


async def main() -> int:
    schema = load_output_schema()
    client = BlibliClient()
    failures = 0
    try:
        # ---- pure helpers (no network) -----------------------------------
        print("\n=== SKU resolution ===")
        for raw, want in [
            (LIVE, LIVE),
            (f"https://www.blibli.com/p/sandisk/ps--{LIVE}", LIVE),
            (f"https://www.blibli.com/p/sandisk/is--{LIVE}?ds=x&source=SEARCH", LIVE),
            (LIVE.lower(), LIVE),
        ]:
            failures += not check(f"resolve {raw[:46]}", resolve_sku(raw) == want,
                                  f"got {resolve_sku(raw)}")
        for bad in ("", "nonsense", "COP-60023", "https://example.com/x"):
            try:
                resolve_sku(bad)
                failures += not check(f"rejects {bad!r}", False, "no exception")
            except InvalidInput:
                failures += not check(f"rejects {bad!r}", True)

        failures += not check("chunking", [len(c) for c in chunked(list(range(120)), 50)] == [50, 50, 20])
        failures += not check(
            "description cleaned",
            clean_text("• A \n<br>• B") == "A\nB", repr(clean_text("• A \n<br>• B")),
        )
        failures += not check("clean_text None-safe", clean_text(None) is None)

        # ---- change detection (the core of a sync actor) -------------------
        print("\n=== change detection ===")
        cur = {"sku": LIVE, "syncStatus": SYNC_OK, "price": 239000,
               "inStock": True, "stockQuantity": 90, "name": "N"}

        r = detect_changes(dict(cur), None)
        failures += not check("no history -> NEW", r["changeType"] == [CHANGE_NEW] and r["hasChanged"])

        prev = {"price": 239000, "inStock": True, "stockQuantity": 90,
                "name": "N", "syncStatus": SYNC_OK}
        r = detect_changes(dict(cur), prev)
        failures += not check(
            "identical -> UNCHANGED",
            r["changeType"] == [CHANGE_UNCHANGED] and not r["hasChanged"],
        )

        r = detect_changes(dict(cur), {**prev, "price": 255000})
        failures += not check("price drop detected", CHANGE_PRICE_DOWN in r["changeType"])
        failures += not check(
            "delta computed",
            r["changes"]["price"]["from"] == 255000 and r["changes"]["price"]["to"] == 239000
            and r["changes"]["price"]["deltaPercent"] < 0,
            json.dumps(r["changes"]["price"]),
        )
        r = detect_changes(dict(cur), {**prev, "price": 200000})
        failures += not check("price rise detected", CHANGE_PRICE_UP in r["changeType"])

        r = detect_changes(dict(cur), {**prev, "inStock": False})
        failures += not check("back in stock", CHANGE_BACK_IN_STOCK in r["changeType"])
        r = detect_changes({**cur, "inStock": False}, prev)
        failures += not check("out of stock", CHANGE_OUT_OF_STOCK in r["changeType"])

        r = detect_changes(dict(cur), {**prev, "name": "Old name"})
        failures += not check("rename detected", CHANGE_NAME_CHANGED in r["changeType"])

        r = detect_changes({**cur, "syncStatus": SYNC_NOT_FOUND}, prev)
        failures += not check("became unavailable", CHANGE_UNAVAILABLE in r["changeType"])

        r = detect_changes({**cur, "price": 100000, "inStock": False}, prev)
        failures += not check(
            "multiple changes at once",
            CHANGE_PRICE_DOWN in r["changeType"] and CHANGE_OUT_OF_STOCK in r["changeType"],
            str(r["changeType"]),
        )
        failures += not check(
            "snapshot entry is compact",
            set(snapshot_entry(cur)) == {"price", "inStock", "stockQuantity", "name", "syncStatus"},
        )

        # ---- live bulk -----------------------------------------------------
        print("\n=== live bulk fetch ===")
        bulk = await fetch_bulk(client, [LIVE, LIVE2, BOGUS])
        failures += not check("bulk resolved live SKUs", LIVE in bulk and LIVE2 in bulk)
        failures += not check("bogus SKU omitted", BOGUS not in bulk)
        print(f"  bulk returned {len(bulk)} of 3 requested")

        # ---- the silent-omission trap ---------------------------------------
        print("\n=== bulk silently omits a LIVE product ===")
        omitted = await fetch_bulk(client, [BULK_OMITTED_BUT_LIVE])
        page = await fetch_page(client, BULK_OMITTED_BUT_LIVE)
        failures += not check(
            "SKU absent from bulk", BULK_OMITTED_BUT_LIVE not in omitted
        )
        failures += not check(
            "but alive on its product page",
            bool(page) and bool(page.get("name")),
            str((page or {}).get("name"))[:52],
        )
        print("  -> this is why `verifyMissing` defaults to on")
        failures += not check("bogus SKU page has no state", await fetch_page(client, BOGUS) is None)

        # ---- end-to-end sync -------------------------------------------------
        print("\n=== sync_skus (fast, with verification) ===")
        records = await collect(
            sync_skus(client, [LIVE, LIVE2, BULK_OMITTED_BUT_LIVE, BOGUS], False, True)
        )
        by_sku = {r["sku"]: r for r in records}
        failures += not check("one record per SKU", len(records) == 4, str(len(records)))
        failures += not check(
            "live SKUs OK",
            all(by_sku[s]["syncStatus"] == SYNC_OK for s in (LIVE, LIVE2)),
        )
        failures += not check(
            "bulk-omitted SKU rescued as OK (not NOT_FOUND)",
            by_sku[BULK_OMITTED_BUT_LIVE]["syncStatus"] == SYNC_OK,
            by_sku[BULK_OMITTED_BUT_LIVE]["syncStatus"],
        )
        failures += not check(
            "rescued via product page",
            by_sku[BULK_OMITTED_BUT_LIVE]["_source"] == "S2-product-page",
        )
        failures += not check(
            "genuinely absent SKU -> NOT_FOUND",
            by_sku[BOGUS]["syncStatus"] == SYNC_NOT_FOUND,
        )
        failures += not check(
            "prices present on live rows",
            all(by_sku[s].get("price") for s in (LIVE, LIVE2)),
        )
        failures += not check_schema(records, schema)
        print("  SAMPLE:", json.dumps({k: by_sku[LIVE].get(k) for k in (
            "sku", "name", "price", "listPrice", "discountPercent", "inStock",
            "rating", "merchantName")}, ensure_ascii=False)[:340])

        # ---- verifyMissing off is honest about it -----------------------------
        print("\n=== verifyMissing=False ===")
        unverified = await collect(
            sync_skus(client, [BULK_OMITTED_BUT_LIVE], False, False)
        )
        failures += not check(
            "reports NOT_FOUND but flags it as unconfirmed",
            unverified[0]["syncStatus"] == SYNC_NOT_FOUND
            and "NOT been confirmed" in unverified[0]["_errorDetail"],
        )

        # ---- detailed mode ----------------------------------------------------
        print("\n=== detailed mode ===")
        detailed = await collect(sync_skus(client, [LIVE], True, True))
        d = detailed[0]
        failures += not check("stock quantity present", isinstance(d.get("stockQuantity"), (int, float)),
                              str(d.get("stockQuantity")))
        failures += not check("description present", bool(d.get("description")))
        failures += not check("categories present", bool(d.get("categories")))
        failures += not check("images present", bool(d.get("images")))
        failures += not check_schema(detailed, schema)
        print("  STOCK:", d.get("stockQuantity"), "| price:", d.get("price"),
              "| warranty:", d.get("warrantyText"))
        print("  DESC :", (d.get("description") or "").replace("\n", " | ")[:170])
    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
