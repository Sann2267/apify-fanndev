"""Local smoke test -- exercises target resolution, sweeps and record shape
against the live site.

    python test_local.py           # capped, fast
    python test_local.py --full    # full deep sweep on one store
"""

import asyncio
import json
import sys

from src.client import BlibliClient
from src.constants import TYPE_BRAND, TYPE_MERCHANT, TYPE_PRODUCT
from src.reviews import (
    InvalidTarget,
    fetch_merchant_name,
    fetch_store_products,
    fetch_summary,
    resolve_target,
    run_target,
    summary_record,
    sweep_plan,
)

FULL = "--full" in sys.argv
STORE = "COP-60023"
PRODUCT = "BLL-70058-00122"
ENVELOPE = ("_input", "_source", "_scrapedAt")

# Same guard that caught the sibling actor's first cloud failure: Apify
# enforces output_schema.json against every pushed item, and a null in a
# non-nullable field only shows up as a generic "Schema validation failed"
# on the platform. `apify validate-schema` does not check real data.
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


async def collect(stream, limit=None):
    out = []
    async for record in stream:
        out.append(record)
        if limit and len(out) >= limit:
            break
    return out


async def main() -> int:
    schema = load_output_schema()
    client = BlibliClient()
    failures = 0
    try:
        # ---- target resolution (pure, no network) ------------------------
        print("\n=== target resolution ===")
        cases = [
            ("https://www.blibli.com/merchant/colgate/COP-60023", TYPE_MERCHANT, "COP-60023"),
            ("COP-60023", TYPE_MERCHANT, "COP-60023"),
            ("https://www.blibli.com/p/foo/ps--BLL-70058-00122", TYPE_PRODUCT, "BLL-70058-00122"),
            ("BLL-70058-00122", TYPE_PRODUCT, "BLL-70058-00122"),
            ("brand:SanDisk", TYPE_BRAND, "SanDisk"),
        ]
        for raw, want_type, want_value in cases:
            got = resolve_target(raw)
            failures += not check(
                f"resolve {raw[:46]}",
                got["type"] == want_type and got["value"] == want_value,
                f"got {got['type']}={got['value']}",
            )
        # A product SKU must not be mistaken for a store code (it starts with one).
        failures += not check(
            "SKU not misread as store code",
            resolve_target("COP-60023-00933")["type"] == TYPE_PRODUCT,
        )
        for bad in ("", "not a thing", "https://example.com/x"):
            try:
                resolve_target(bad)
                failures += not check(f"rejects {bad!r}", False, "no exception raised")
            except InvalidTarget:
                failures += not check(f"rejects {bad!r}", True)

        # ---- sweep plan --------------------------------------------------
        print("\n=== sweep plan ===")
        failures += not check("standard = 1 slice", len(sweep_plan("standard")) == 1)
        failures += not check("deep = 1 + 5 ratings", len(sweep_plan("deep")) == 6)
        failures += not check("maximum = 1 + 5 + 7 topics", len(sweep_plan("maximum")) == 13)

        # ---- store summary -----------------------------------------------
        print("\n=== store summary ===")
        target = resolve_target(STORE)
        name = await fetch_merchant_name(client, STORE)
        summary = await fetch_summary(client, target)
        record = summary_record(target, summary, name)
        failures += not check("merchant name resolved", bool(name), str(name))
        failures += not check("envelope present", all(k in record for k in ENVELOPE))
        failures += not check("totalReviews > 0", (record.get("totalReviews") or 0) > 0)
        failures += not check("rating histogram", len(record.get("ratingCounts") or {}) == 5)
        failures += not check("topic counts", len(record.get("topicCounts") or {}) >= 5)
        failures += not check(
            "shares sum to ~100",
            abs((record["negativeSharePercent"] + record["positiveSharePercent"]) - 100) < 100,
        )
        failures += not check_schema([record], schema)
        print("  SUMMARY:", json.dumps({k: record[k] for k in (
            "merchantName", "totalReviews", "averageRating", "negativeSharePercent",
            "topicCounts")}, ensure_ascii=False)[:400])

        # ---- review sweep (standard) --------------------------------------
        print("\n=== reviews: standard sweep ===")
        cap = None if FULL else 90
        reviews = await collect(
            run_target(client, target, "standard", "LATEST", cap or 0, 0, False, name, True), cap
        )
        print(f"  records: {len(reviews)}")
        failures += not check("got reviews", bool(reviews))
        if reviews:
            sample = reviews[0]
            failures += not check("envelope present", all(k in sample for k in ENVELOPE))
            failures += not check("recordType", sample["recordType"] == "REVIEW")
            failures += not check("raw passthrough kept", "verifiedBuyer" in sample)
            ids = [r["id"] for r in reviews]
            failures += not check("no duplicate review IDs", len(ids) == len(set(ids)))
            # With onlyWithText the server-side `hasComment` filter should
            # leave essentially no star-only rows -- the whole point of it.
            with_text = sum(1 for r in reviews if r.get("hasText"))
            failures += not check(
                "onlyWithText yields text rows",
                with_text >= len(reviews) * 0.95,
                f"{with_text}/{len(reviews)} have text",
            )
            failures += not check(
                "polarity labelled",
                all(r.get("ratingPolarity") in ("negative", "neutral", "positive")
                    for r in reviews),
            )
            failures += not check(
                "polarity matches rating",
                all((r["rating"] <= 2) == (r["ratingPolarity"] == "negative") for r in reviews),
            )
            failures += not check("createdAtIso present", all(r.get("createdAtIso") for r in reviews))
            failures += not check(
                "productSku present on store sweep",
                sum(1 for r in reviews if r.get("productSku")) > len(reviews) * 0.8,
            )
            failures += not check_schema(reviews, schema)
            print("  SAMPLE:", json.dumps({k: sample.get(k) for k in (
                "id", "rating", "ratingPolarity", "productSku", "verifiedBuyer",
                "createdAtIso", "reviewLength")}, ensure_ascii=False)[:340])
            print("  TEXT  :", (sample.get("reviewText") or "")[:180])

        # ---- deep sweep really finds NEW reviews ---------------------------
        print("\n=== reviews: deep sweep beats the ~600 cap ===")
        deep = await collect(
            run_target(client, target, "deep", "LATEST", 0 if FULL else 900, 0, False, name, True),
            None if FULL else 900,
        )
        deep_ids = {r["id"] for r in deep}
        print(f"  deep records: {len(deep)} unique: {len(deep_ids)}")
        failures += not check("deep dedupes", len(deep) == len(deep_ids))
        failures += not check(
            "deep exceeds one window", len(deep_ids) > 600 if FULL else len(deep_ids) > 300,
            f"{len(deep_ids)} unique",
        )
        neg = [r for r in deep if r["ratingPolarity"] == "negative"]
        print(f"  negative reviews captured: {len(neg)}")
        failures += not check("negative reviews captured", bool(neg))
        # The whole point of the actor: a CAPPED deep run must still surface
        # the scarce 1-2 star reviews, which only holds while the rating
        # slices are swept low-star first.
        capped = await collect(
            run_target(client, target, "deep", "LATEST", 700, 0, False, name, True), 700
        )
        capped_neg = [r for r in capped if r["ratingPolarity"] == "negative"]
        print(f"  capped run: {len(capped)} records, {len(capped_neg)} negative")
        failures += not check(
            "capped deep run still captures negatives",
            len(capped_neg) >= 50,
            f"{len(capped_neg)} negative in {len(capped)} records",
        )

        # ---- product target ------------------------------------------------
        print("\n=== reviews: product target ===")
        ptarget = resolve_target(PRODUCT)
        previews = await collect(
            run_target(client, ptarget, "standard", "LATEST", 30, 0, False, None, True), 30
        )
        print(f"  records: {len(previews)}")
        failures += not check("got product reviews", bool(previews))
        if previews:
            failures += not check(
                "targetType is productSku",
                all(r["targetType"] == TYPE_PRODUCT for r in previews),
            )
            failures += not check_schema(previews, schema)

        # ---- minRating filter ---------------------------------------------
        print("\n=== filter: minRating=4 ===")
        hi = await collect(
            run_target(client, target, "standard", "LATEST", 40, 4, False, name, True), 40
        )
        failures += not check(
            "all >= 4 stars", all(r["rating"] >= 4 for r in hi),
            f"min={min((r['rating'] for r in hi), default='n/a')}",
        )

        # ---- store catalogue ------------------------------------------------
        print("\n=== store product enumeration ===")
        products = await fetch_store_products(client, STORE, 20)
        print(f"  products: {len(products)}")
        failures += not check("enumerated products", bool(products))
        failures += not check(
            "products belong to the store",
            all(p.get("merchantCode") == STORE for p in products),
        )
    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
