"""Local smoke test -- exercises all three modes against the live site.

Runs the extractor layer directly (no Apify platform), prints a compact
summary plus one sample record per mode, and asserts the invariants that
matter: envelope present, discount threshold honoured, pagination
terminating, no silent empties.

    python test_local.py            # quick pass, capped
    python test_local.py --full     # exhaust the current flash sale session
"""

import asyncio
import json
import sys

from src.client import BlibliClient
from src.modes import (
    fetch_schedules,
    run_discounted_products,
    run_flash_sale,
    run_promo_campaigns,
)

FULL = "--full" in sys.argv
ENVELOPE = ("_input", "_source", "_scrapedAt")

# Apify enforces .actor/output_schema.json against every pushed item, and a
# violation surfaces only as a generic "Schema validation failed" on the
# first cloud run -- `apify validate-schema` checks the schema document's
# own shape, not real data against it. This guard closes that gap locally.
# It caught nothing until a null `_categoryFilter` / float `57.0` discount
# broke the first cloud push; keep it in front of every mode.
_JSON_TYPES = {
    "string": str, "number": (int, float), "integer": int,
    "boolean": bool, "object": dict, "array": list,
}


def load_output_schema() -> dict:
    with open(".actor/output_schema.json", encoding="utf-8") as fh:
        return json.load(fh)["fields"]["properties"]


def schema_violations(records: list, schema: dict) -> list:
    """Every declared field must match its declared type where present."""
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
            types = tuple(
                _JSON_TYPES[a] if not isinstance(_JSON_TYPES.get(a), tuple) else _JSON_TYPES[a]
                for a in allowed if a in _JSON_TYPES
            )
            flat = tuple(
                t for group in types for t in (group if isinstance(group, tuple) else (group,))
            )
            # bool is a subclass of int in Python; don't let it satisfy "number"
            if flat and (
                not isinstance(value, flat)
                or (isinstance(value, bool) and bool not in flat)
            ):
                problems.append(f"{field}={value!r} ({type(value).__name__}) vs type {declared}")
    return sorted(set(problems))


def check(label: str, condition: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")
    return condition


def check_schema(records: list, schema: dict) -> bool:
    problems = schema_violations(records, schema)
    return check(
        "matches output_schema.json",
        not problems,
        "; ".join(problems[:4]) if problems else "",
    )


async def collect(stream, limit=None):
    out = []
    async for record in stream:
        out.append(record)
        if limit and len(out) >= limit:
            break
    return out


async def main() -> int:
    client = BlibliClient()
    schema = load_output_schema()
    failures = 0
    try:
        # ---- Mode 1: flash sale ------------------------------------------
        print("\n=== MODE 1: flashSale ===")
        schedules = await fetch_schedules(client)
        print(f"  schedules: {[s['id'] for s in schedules]}")
        cap = None if FULL else 60
        records = await collect(
            run_flash_sale(client, schedules[:1], [], "biggestDiscount", 0, cap or 0), cap
        )
        print(f"  records: {len(records)}")
        failures += not check("got records", bool(records))
        if records:
            sample = records[0]
            failures += not check_schema(records, schema)
            failures += not check("envelope present", all(k in sample for k in ENVELOPE))
            failures += not check("source tag", sample["_source"] == "S1-flashsale-v2")
            failures += not check(
                "raw passthrough kept", "sku" in sample and "flashsale" in sample
            )
            failures += not check(
                "discount flattened", isinstance(sample.get("_discountPercent"), (int, float))
            )
            failures += not check(
                "quota flattened", any(r.get("_quotaClaimedPercent") is not None for r in records)
            )
            failures += not check(
                "schedule window ISO", bool(sample.get("_scheduleStart"))
            )
            failures += not check(
                "product URL absolute",
                str(sample.get("_productUrl", "")).startswith("https://www.blibli.com"),
            )
            skus = [r["sku"] for r in records]
            failures += not check("no duplicate SKUs", len(skus) == len(set(skus)))
            priced = [r for r in records if r.get("_listPrice") and r.get("_offerPrice")]
            failures += not check(
                "prices resolved", len(priced) == len(records),
                f"{len(priced)}/{len(records)} rows priced",
            )
            failures += not check(
                "saving consistent with discount",
                all(r["_listPrice"] > r["_offerPrice"] for r in priced),
            )
            # Blibli omits `price.discount` for sub-1% reductions; the
            # fallback must leave no row without a discount figure.
            failures += not check(
                "discount on every row",
                all(r.get("_discountPercent") is not None for r in records),
            )
            failures += not check(
                "discount provenance labelled",
                all(r.get("_discountSource") in ("upstream", "computed") for r in records),
            )
            discounts = [r["_discountPercent"] for r in records if r.get("_discountPercent")]
            print(f"  discount range: {min(discounts)}%..{max(discounts)}%")
            print("  SAMPLE:", json.dumps(
                {k: sample[k] for k in ("name", "sku", "_discountPercent", "_listPrice",
                                        "_offerPrice", "_quotaClaimedPercent", "_campaignCode",
                                        "merchantName") if k in sample},
                ensure_ascii=False)[:400])

        # ---- min discount filter is honoured -----------------------------
        print("\n=== MODE 1 filter: minDiscountPercent=70 ===")
        strict = await collect(
            run_flash_sale(client, schedules[:1], [], "biggestDiscount", 70, 25), 25
        )
        print(f"  records: {len(strict)}")
        failures += not check(
            "all >= 70%",
            all(r["_discountPercent"] >= 70 for r in strict),
            f"min={min((r['_discountPercent'] for r in strict), default='n/a')}",
        )

        # ---- Mode 2: promo campaigns -------------------------------------
        print("\n=== MODE 2: promoCampaigns ===")
        promos = await collect(run_promo_campaigns(client, "ending_soon", 120), 120)
        print(f"  records: {len(promos)}")
        failures += not check("paged past page 1", len(promos) > 50)
        if promos:
            sample = promos[0]
            failures += not check("envelope present", all(k in sample for k in ENVELOPE))
            failures += not check("source tag", sample["_source"] == "S2-promotions")
            failures += not check_schema(promos, schema)
            failures += not check("window ISO", bool(sample.get("_endTime")))
            failures += not check("raw passthrough kept", "promoPeriod" in sample)
            print("  SAMPLE:", json.dumps(
                {k: sample[k] for k in ("title", "_promoUrl", "promoPeriod", "_endTime", "status")
                 if k in sample}, ensure_ascii=False)[:400])

        # ---- Mode 3: discounted products ---------------------------------
        print("\n=== MODE 3: discountedProducts (laptop, >=50%) ===")
        queries = [{"type": "searchTerm", "value": "laptop", "label": "laptop"}]
        deals = await collect(run_discounted_products(client, queries, 50, None, "relevance", 50), 50)
        print(f"  records: {len(deals)}")
        failures += not check("got records", bool(deals))
        if deals:
            sample = deals[0]
            failures += not check("envelope present", all(k in sample for k in ENVELOPE))
            failures += not check("source tag", sample["_source"] == "S3-search-discount")
            failures += not check(
                "all >= 50%",
                all(r["_discountPercent"] >= 50 for r in deals),
                f"min={min(r['_discountPercent'] for r in deals)}",
            )
            failures += not check_schema(deals, schema)
            failures += not check("rank recorded", sample.get("_rankInQuery") == 1)
            failures += not check("raw passthrough kept", "merchantCode" in sample)
            # Regression guard: the search backend names its price fields
            # differently from the flash sale backend, which silently
            # nulled every price here until it was caught.
            priced = [r for r in deals if r.get("_listPrice") and r.get("_offerPrice")]
            failures += not check(
                "prices resolved", len(priced) == len(deals),
                f"{len(priced)}/{len(deals)} rows priced",
            )
            failures += not check(
                "saving consistent with discount",
                all(r["_listPrice"] > r["_offerPrice"] for r in priced),
            )
            print("  SAMPLE:", json.dumps(
                {k: sample[k] for k in ("name", "sku", "_discountPercent",
                                        "_contextualDiscountPercent", "_listPrice", "_offerPrice",
                                        "_savingAmount", "_campaignName", "_rankInQuery",
                                        "merchantName") if k in sample}, ensure_ascii=False)[:460])

        # ---- Mode 3 with a promo tag -------------------------------------
        print("\n=== MODE 3: promoFilter=extraPromo ===")
        tagged = await collect(
            run_discounted_products(client, queries, 0, "extraPromo", "relevance", 20), 20
        )
        print(f"  records: {len(tagged)}")
        failures += not check("got records", bool(tagged))
        failures += not check(
            "promo filter recorded",
            all(r.get("_promoFilter") == "extraPromo" for r in tagged),
        )
    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
