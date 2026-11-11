"""Local smoke test against the live site.

    python test_local.py          # capped
    python test_local.py --full   # full deep catalogue on a large store
"""

import asyncio
import json
import sys

from curl_cffi import requests as creq

from src.client import BlibliClient
from src.constants import BASE_HEADERS, ORIGIN, TLS_PROFILE_LADDER
from src.merchant import (
    InvalidTarget,
    StoreNotFound,
    catalog_plan,
    count_products,
    fetch_catalog,
    fetch_followers,
    fetch_profile,
    fetch_review_summary,
    fetch_vouchers,
    profile_record,
    resolve_store,
)

FULL = "--full" in sys.argv
STORE = "COP-60023"
BIG_STORE = "ADS-12698"
ENVELOPE = ("_input", "_source", "_scrapedAt")

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
    return check("matches output_schema.json", not schema_violations(records, schema),
                 "; ".join(schema_violations(records, schema)[:4]))


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
        # ---- store resolution -------------------------------------------
        print("\n=== store resolution ===")
        for raw, want in [
            (f"https://www.blibli.com/merchant/colgate/{STORE}", STORE),
            (STORE, STORE),
            ("COP-60023-00933", STORE),                       # bare SKU
            (f"https://www.blibli.com/p/x/ps--{STORE}-00933", STORE),  # product URL
        ]:
            failures += not check(f"resolve {raw[:44]}", resolve_store(raw) == want,
                                  f"got {resolve_store(raw)}")
        for bad in ("", "nonsense", "https://example.com/x"):
            try:
                resolve_store(bad)
                failures += not check(f"rejects {bad!r}", False, "no exception")
            except InvalidTarget:
                failures += not check(f"rejects {bad!r}", True)

        # ---- the TLS-profile trap ----------------------------------------
        # The profile endpoint is blocked per-fingerprint; chrome124 gets a
        # Cloudflare 403 while every other endpoint works on it. Guard the
        # ladder so nobody "tidies" it back to a chrome-first default.
        print("\n=== TLS profile guard ===")
        failures += not check(
            "ladder leads with a non-chrome profile",
            not TLS_PROFILE_LADDER[0].startswith("chrome"),
            f"leads with {TLS_PROFILE_LADDER[0]}",
        )
        url = f"{ORIGIN}/backend/search/merchant/{STORE}/info"
        headers = {**BASE_HEADERS, "Referer": f"{ORIGIN}/merchant/x/{STORE}"}
        blocked = creq.get(url, headers=headers, impersonate="chrome124", timeout=30)
        allowed = creq.get(url, headers=headers, impersonate=TLS_PROFILE_LADDER[0], timeout=30)
        failures += not check(
            "chrome124 still blocked / ladder profile still allowed",
            blocked.status_code == 403 and allowed.status_code == 200,
            f"chrome124={blocked.status_code} {TLS_PROFILE_LADDER[0]}={allowed.status_code}",
        )

        # ---- nonexistent store must not yield a hollow row -----------------
        # Blibli answers 200 with a fully-shaped, all-zero profile for codes
        # that do not exist; without the name check that shipped as a valid
        # MERCHANT_PROFILE row full of zeros.
        print("\n=== nonexistent store ===")
        for bogus in ("ZZZ-99999", "COP-99999"):
            try:
                await fetch_profile(client, bogus)
                failures += not check(f"{bogus} rejected", False, "returned a profile")
            except StoreNotFound:
                failures += not check(f"{bogus} rejected as STORE_NOT_FOUND", True)

        # ---- profile ------------------------------------------------------
        print("\n=== merchant profile ===")
        profile = await fetch_profile(client, STORE)
        followers = await fetch_followers(client, STORE)
        review_summary = await fetch_review_summary(client, STORE)
        vouchers = await fetch_vouchers(client, STORE)
        total = await count_products(client, STORE)
        record = profile_record(STORE, profile, followers, review_summary, vouchers, total)

        failures += not check("envelope present", all(k in record for k in ENVELOPE))
        failures += not check("recordType", record["recordType"] == "MERCHANT_PROFILE")
        failures += not check("store name", bool(record.get("merchantName")))
        failures += not check("respond time rating", record.get("respondTimeRating") is not None)
        failures += not check("badge", bool(record.get("badgeId")))
        failures += not check("shipping city", bool(record.get("pickupPointCity")))
        failures += not check("shipping coords", bool(record.get("pickupPointLatLong")))
        failures += not check("business hours", bool(record.get("businessHours")))
        failures += not check("followers", (record.get("totalFollowers") or 0) > 0)
        failures += not check("review stats", (record.get("totalReviews") or 0) > 0)
        failures += not check("topic counts", len(record.get("reviewTopicCounts") or {}) >= 5)
        failures += not check("product count", (record.get("productCount") or 0) > 0)
        failures += not check("vouchers", (record.get("voucherCount") or 0) >= 0)
        failures += not check("activation date ISO", bool(record.get("activationDateIso")))
        failures += not check_schema([record], schema)
        print("  PROFILE:", json.dumps({k: record.get(k) for k in (
            "merchantName", "badgeId", "respondTimeRating", "productQualityRating",
            "pickupPointCity", "province", "totalFollowers", "totalReviews",
            "averageRating", "productCount", "voucherCount", "activationDateIso",
        )}, ensure_ascii=False)[:520])

        # ---- catalogue -----------------------------------------------------
        print("\n=== catalogue ===")
        failures += not check("standard plan = 1 slice", len(catalog_plan("standard")) == 1)
        failures += not check("deep plan = 1 + 3 sorts + 5 bands", len(catalog_plan("deep")) == 9)

        cap = None if FULL else 120
        products = await collect(
            fetch_catalog(client, STORE, "standard", cap or 0, record.get("merchantName")), cap
        )
        print(f"  products: {len(products)}")
        failures += not check("got products", bool(products))
        if products:
            sample = products[0]
            failures += not check("recordType", sample["recordType"] == "PRODUCT")
            failures += not check("raw passthrough kept", "merchantCode" in sample)
            skus = [p["sku"] for p in products]
            failures += not check("no duplicate SKUs", len(skus) == len(set(skus)))
            failures += not check(
                "all belong to the store",
                all(p.get("merchantCode") == STORE for p in products),
            )
            priced = [p for p in products if p.get("salePrice")]
            failures += not check(
                "prices resolved", len(priced) >= len(products) * 0.9,
                f"{len(priced)}/{len(products)} priced",
            )
            failures += not check(
                "product URLs absolute",
                all(str(p.get("productUrl", "")).startswith("https://") for p in products),
            )
            failures += not check_schema(products, schema)
            print("  SAMPLE:", json.dumps({k: sample.get(k) for k in (
                "sku", "name", "salePrice", "listPrice", "discountPercent",
                "rating", "soldCount", "storeLocation")}, ensure_ascii=False)[:400])

        # ---- deep coverage beats the 800 cap --------------------------------
        print("\n=== deep coverage on a large store ===")
        big_total = await count_products(client, BIG_STORE)
        print(f"  {BIG_STORE} catalogue size: {big_total}")
        limit = None if FULL else 1100
        big = await collect(fetch_catalog(client, BIG_STORE, "deep", limit or 0, None), limit)
        big_skus = {p["sku"] for p in big}
        print(f"  deep sweep: {len(big)} records, {len(big_skus)} unique")
        failures += not check("deep dedupes", len(big) == len(big_skus))
        failures += not check(
            "deep exceeds the 800 single-sweep cap", len(big_skus) > 800,
            f"{len(big_skus)} unique vs 800 cap",
        )
    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
