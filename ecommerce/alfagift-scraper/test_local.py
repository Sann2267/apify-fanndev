"""Local test harness: every mode against the live site, plus regressions.

Run it with the repo venv from inside this folder:

    ../.venv/Scripts/python.exe test_local.py            # everything
    ../.venv/Scripts/python.exe test_local.py search     # one mode

It talks to the real alfagift.id, so it is a smoke test rather than a unit
suite. Item counts are asserted as lower bounds, never exact, because the
catalogue moves.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import time
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from src.client import AlfagiftClient  # noqa: E402
from src.gate import decrypt, encrypt, new_fingerprint  # noqa: E402
from src.modes import MODES, Budget  # noqa: E402
from src.parsers import (  # noqa: E402
    enrich_product,
    error_record,
    record,
    resolve_brand_id,
    resolve_category_id,
    resolve_keyword,
    resolve_product_id,
    resolve_promotion_id,
)

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        PASSED.append(label)
        print(f"  [ok]   {label}")
    else:
        FAILED.append(f"{label} ({detail})" if detail else label)
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))
    return bool(condition)


async def run_mode(name: str, options: dict[str, Any], limit: int = 0) -> list[dict]:
    """Drive one mode the way src/main.py does, including the hard row cap.

    The cap is applied here and not left to the Budget alone because diagnostic
    rows do not reserve budget: a run asked for 60 rows that also emitted an
    error row would otherwise return 61, which is what this harness caught.
    """
    client = AlfagiftClient(request_delay=0.15)
    budget = Budget(limit)
    out: list[dict] = []
    try:
        async for rec in MODES[name](client, options, budget):
            if limit and len(out) >= limit:
                break
            out.append(rec)
    finally:
        client.close()
    return out


def kinds(records: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rec in records:
        counts[rec["item_type"]] = counts.get(rec["item_type"], 0) + 1
    return counts


def show(name: str, records: list[dict], elapsed: float) -> None:
    print(f"  -> {len(records)} record(s) in {elapsed:.1f}s: {kinds(records)}")
    sample = next((r for r in records if r["item_type"] != "error"), None)
    if sample:
        body = json.dumps(sample["data"], ensure_ascii=False)
        print(f"     sample {sample['item_type']} id={sample['id']}: {body[:220]}")
    for rec in records:
        if rec["item_type"] == "error":
            data = rec["data"]
            print(f"     error {data['_error']} [{data['_input']}]: "
                  f"{data['_errorDetail'][:120]}")


# -- unit-ish regressions ---------------------------------------------------

def test_gate() -> None:
    """The AES gate must round-trip and must be fresh per call."""
    print("\n[gate] AES-256-CBC round trip")
    check("encrypt/decrypt round trip", decrypt(encrypt("hello-alfagift")) == "hello-alfagift")
    # Fixed vector: proves the key and IV in constants.py have not drifted.
    check(
        "known plaintext encrypts deterministically",
        encrypt("afcfa3dbb0a4fbff4d8b") == "sJg47Or0ojnJplTESxbjvtQVGgtowL/RxTrxLRPmeMI=",
        encrypt("afcfa3dbb0a4fbff4d8b"),
    )
    check("fingerprints are per-call fresh", new_fingerprint() != new_fingerprint())


def test_input_resolution() -> None:
    """Pasted alfagift.id URLs must resolve to the ids the API wants."""
    print("\n[input] URL and id resolution")
    check(
        "product URL -> numeric id",
        resolve_product_id("https://alfagift.id/p/indomie-mi-instan-goreng-84-g-754971") == "754971",
    )
    check("bare product id passes through", resolve_product_id("754971") == "754971")
    check(
        "a SKU is rejected rather than sent",
        resolve_product_id("A13170001210") is None,
        "a SKU makes the detail endpoint answer HTTP 500",
    )
    check(
        "category URL -> ObjectId",
        resolve_category_id("https://alfagift.id/c/makanan-602f8240898b4705ec586ab3")
        == "602f8240898b4705ec586ab3",
    )
    check("brand URL -> numeric id", resolve_brand_id("https://alfagift.id/b/indomie-13207") == "13207")
    check(
        "search URL -> unslugified keyword",
        resolve_keyword("https://alfagift.id/find/susu-uht") == "susu uht",
    )
    check(
        "promotion URL -> promotion id",
        resolve_promotion_id("https://alfagift.id/promotion-products?id=6aacea5b144aa661216a3007")
        == "6aacea5b144aa661216a3007",
    )


def test_enrichment() -> None:
    """isBuyable has to catch the zero-priced delisted rows."""
    print("\n[enrich] derived product fields")
    live = enrich_product({
        "productId": "754971", "productName": "Indomie Mi Instan Goreng 84 g",
        "validFlag": True, "basePrice": 3500.0, "finalPrice": 3000.0,
    })
    check("live product is buyable", live["isBuyable"] is True)
    check("discount detected", live["isDiscounted"] is True)
    check("discount amount in rupiah", live["discountAmount"] == 500.0, str(live["discountAmount"]))
    check(
        "product URL rebuilt like the site does",
        live["productUrl"] == "https://alfagift.id/p/indomie-mi-instan-goreng-84-g-754971",
        live["productUrl"],
    )
    dead = enrich_product({
        "productId": "754973", "productName": "Indomie Mi Instan Goreng 80 g",
        "validFlag": False, "basePrice": 0.0, "finalPrice": 0.0,
    })
    check("delisted zero-priced row is not buyable", dead["isBuyable"] is False)
    check("delisted row reports no discount", dead["discountAmount"] == 0.0)


def test_dataset_schema() -> None:
    """Type-check real record shapes against .actor/output_schema.json.

    This exists because of a repeat failure elsewhere in the portfolio: Apify
    validates a whole push_data batch, so one row violating a declared type
    discards up to 99 good rows with it and the run exits 91 with zero
    records. Diagnostic rows carry id: null, so the batch checked here
    deliberately includes one.
    """
    print("\n[dataset schema] record shapes against .actor/output_schema.json")
    schema = json.loads(
        (pathlib.Path(__file__).parent / ".actor" / "output_schema.json")
        .read_text(encoding="utf-8")
    )
    props = schema["fields"]["properties"]
    py_types = {
        "string": str, "object": dict, "array": list,
        "number": (int, float), "integer": int, "boolean": bool,
    }

    def validate(rec: dict, label: str) -> None:
        for field, spec in props.items():
            declared = spec["type"]
            declared = declared if isinstance(declared, list) else [declared]
            value = rec.get(field)
            if value is None:
                check(
                    f"{label}: null {field} is declared nullable",
                    "null" in declared, f"schema says {declared}",
                )
                continue
            allowed = tuple(py_types[t] for t in declared if t in py_types)
            check(
                f"{label}: {field} is {declared}",
                isinstance(value, allowed), f"got {type(value).__name__}",
            )

    validate(
        record("product", 754971, {"productId": "754971"}, mode="search", rank=0),
        "product row",
    )
    # The row shape that has broken pushes before.
    validate(
        error_record("A13170001210", "unsupported_input", "a SKU", mode="productDetail"),
        "error row",
    )


# -- live mode smoke tests --------------------------------------------------

async def live_search() -> None:
    print("\n[search] keyword search")
    t = time.time()
    recs = await run_mode("search", {"searchKeywords": ["indomie", "https://alfagift.id/find/susu-uht"]}, limit=60)
    show("search", recs, time.time() - t)
    k = kinds(recs)
    check("search returns products", k.get("product", 0) > 10, str(k))
    check("search emits a summary per keyword", k.get("search_summary", 0) == 2, str(k))
    products = [r for r in recs if r["item_type"] == "product"]
    check("products carry a price", any(r["data"].get("finalPrice") for r in products))
    check("products carry a rebuilt URL", all(r["data"].get("productUrl") for r in products))
    check("ranks are unique within a keyword",
          len({(r["metadata"]["query"], r["metadata"]["rank"]) for r in products}) == len(products))


async def live_suggestions() -> None:
    print("\n[searchSuggestions] autocomplete")
    t = time.time()
    recs = await run_mode("searchSuggestions", {"searchKeywords": ["susu", "kopi"]})
    show("searchSuggestions", recs, time.time() - t)
    check("one row per seed", len(recs) == 2, str(len(recs)))
    check("suggestions are non-empty", all(r["data"]["suggestionCount"] > 0 for r in recs))


async def live_category_tree() -> None:
    print("\n[categoryTree] category tree")
    t = time.time()
    recs = await run_mode("categoryTree", {})
    show("categoryTree", recs, time.time() - t)
    check("tree has both levels", len(recs) > 50, str(len(recs)))
    levels = {r["data"]["categoryLevel"] for r in recs}
    check("levels 0 and 1 present", levels == {0, 1}, str(levels))
    check("every node has a URL", all(r["data"]["categoryUrl"] for r in recs))


async def live_category_products() -> None:
    print("\n[categoryProducts] products in a category, by URL and by bad id")
    t = time.time()
    recs = await run_mode(
        "categoryProducts",
        {"categoryIds": [
            "https://alfagift.id/c/pet-foods-5f6f8b6f3a1e2a0001e8a3d1",
            "5b857288a3834cdebbbc4389",
            "000000000000000000000000",
        ], "pageSize": 100},
        limit=120,
    )
    show("categoryProducts", recs, time.time() - t)
    k = kinds(recs)
    check("real category yielded products", k.get("product", 0) > 10, str(k))
    errs = {r["data"]["_error"] for r in recs if r["item_type"] == "error"}
    check("hollow 200 on an unknown id is reported as not_found",
          "not_found" in errs, str(errs))


async def live_paging() -> None:
    """The start-is-a-page-index regression, checked on real data.

    If `start` were treated as an item offset the walk would re-fetch page 0
    forever and every productId would repeat. A big keyword with two small
    pages proves the pages are genuinely different.
    """
    print("\n[paging] start is a page index, not an item offset")
    t = time.time()
    recs = await run_mode(
        "search", {"searchKeywords": ["susu"], "pageSize": 25, "maxPagesPerTarget": 3},
        limit=80,
    )
    show("paging", recs, time.time() - t)
    products = [r for r in recs if r["item_type"] == "product"]
    ids = [r["id"] for r in products]
    pages = {r["metadata"]["page"] for r in products}
    check("walked more than one page", len(pages) > 1, str(pages))
    check("no duplicate products across pages", len(ids) == len(set(ids)),
          f"{len(ids)} rows, {len(set(ids))} unique")


async def live_product_detail() -> None:
    print("\n[productDetail] full product payload, plus the SKU and dead-id traps")
    t = time.time()
    recs = await run_mode("productDetail", {"productIds": [
        "13585",
        "https://alfagift.id/p/indomie-mi-instan-goreng-84-g-754971",
        "A13170001210",
        "999999999",
    ]})
    show("productDetail", recs, time.time() - t)
    details = [r for r in recs if r["item_type"] == "product_detail"]
    check("two real products resolved", len(details) == 2, str(len(details)))
    check("detail carries a barcode", any(r["data"].get("barcode") for r in details))
    check("detail carries brand", any(r["data"].get("brandName") for r in details))
    check("detail carries the image gallery", any(r["data"].get("images") for r in details))
    errs = {r["data"]["_error"] for r in recs if r["item_type"] == "error"}
    check("SKU rejected as unsupported_input", "unsupported_input" in errs, str(errs))
    check("dead numeric id reported as not_found", "not_found" in errs, str(errs))


async def live_brand_directory() -> None:
    print("\n[brandDirectory] A-Z sweep, including a known-broken letter")
    t = time.time()
    recs = await run_mode("brandDirectory", {"brandLetters": ["I", "Q", "C"]})
    show("brandDirectory", recs, time.time() - t)
    k = kinds(recs)
    check("brands returned", k.get("brand", 0) > 30, str(k))
    errs = [r for r in recs if r["item_type"] == "error"]
    check("broken letter C reported, not retried into a crash",
          any(e["data"]["_error"] == "upstream_index_broken" for e in errs),
          str([e["data"]["_error"] for e in errs]))
    check("brands carry a URL", all(r["data"]["brandUrl"] for r in recs if r["item_type"] == "brand"))


async def live_brand_products() -> None:
    print("\n[brandProducts] products of a brand")
    t = time.time()
    recs = await run_mode("brandProducts", {"brandIds": ["13207", "https://alfagift.id/b/indofood-11571"]})
    show("brandProducts", recs, time.time() - t)
    k = kinds(recs)
    check("brand summaries emitted", k.get("brand_summary", 0) == 2, str(k))
    check("brand products returned", k.get("product", 0) > 20, str(k))


async def live_feeds() -> None:
    print("\n[newArrivals / recommendations] flat feeds and their ceilings")
    t = time.time()
    recs = await run_mode("newArrivals", {})
    show("newArrivals", recs, time.time() - t)
    check("new arrivals near the documented 198 ceiling", len(recs) > 100, str(len(recs)))

    t = time.time()
    recs2 = await run_mode("recommendations", {})
    show("recommendations", recs2, time.time() - t)
    check("recommendations near the documented 48 ceiling", 10 < len(recs2) <= 48, str(len(recs2)))


async def live_promo_banners() -> None:
    print("\n[promoBanners] live campaigns")
    t = time.time()
    recs = await run_mode("promoBanners", {}, limit=40)
    show("promoBanners", recs, time.time() - t)
    check("banners returned", len(recs) > 5, str(len(recs)))
    with_promo = [r for r in recs if r["data"].get("promotionId")]
    check("promotion ids dug out of the deep links", len(with_promo) > 3, str(len(with_promo)))
    check("banner id and promotion id are genuinely different",
          any(r["data"]["bannerId"] != r["data"]["promotionId"] for r in with_promo))
    check("campaigns carry run dates", all(r["data"].get("endDate") for r in recs))


async def live_promo_products() -> None:
    print("\n[promoProducts] products on promotion right now")
    t = time.time()
    recs = await run_mode("promoProducts", {"bannerLimit": 6}, limit=80)
    show("promoProducts", recs, time.time() - t)
    k = kinds(recs)
    check("campaigns discovered from the banner rail", k.get("promo_campaign", 0) > 0, str(k))
    check("promotional products returned", k.get("product", 0) > 5, str(k))
    products = [r for r in recs if r["item_type"] == "product"]
    check("promotional rows are tied back to their campaign",
          all(r["metadata"].get("parentId") for r in products))


async def live_poisoned_page() -> None:
    """The Lifestyle category, which Alfagift cannot serialise page 0 of.

    Asked for as one big page it returns HTTP 500 and nothing else, which is
    how a naive run loses all 1008 of its products. The rescue re-reads the
    failed page in smaller slices, so most of the category should come back
    and the summary row should admit what it could not reach.

    If Alfagift ever fixes the underlying record this test will simply see a
    clean walk, which is why it asserts on the recovered count rather than on
    the failure being present.
    """
    print("\n[rescue] a category whose first page Alfagift cannot serialise")
    t = time.time()
    recs = await run_mode(
        "categoryProducts",
        {"categoryIds": ["6034d15eb194ab1cdbbf3cad"], "pageSize": 1000},
    )
    show("rescue", recs, time.time() - t)
    products = [r for r in recs if r["item_type"] == "product"]
    summary = next((r for r in recs if r["item_type"] == "category_summary"), None)
    check("poisoned category still yielded most of its products",
          len(products) > 500, f"{len(products)} products")
    check("no duplicates came back from the rescue split",
          len({r["id"] for r in products}) == len(products),
          f"{len(products)} rows, {len({r['id'] for r in products})} unique")
    if summary and summary["data"].get("_warning"):
        print(f"     summary admits loss: {summary['data']['_warning']} "
              f"pages={summary['data']['unreadablePages']} "
              f"rows~{summary['data']['approxRowsLost']}")
        check("summary reports the unreadable pages",
              summary["data"]["approxRowsLost"] > 0)
    else:
        print("     note: Alfagift served this category cleanly this time")


async def live_full_catalog() -> None:
    """Capped hard -- the real thing is ~10,000 rows and megabytes of JSON."""
    print("\n[fullCatalog] capped sample of the whole catalogue")
    t = time.time()
    recs = await run_mode("fullCatalog", {"pageSize": 50}, limit=60)
    show("fullCatalog", recs, time.time() - t)
    k = kinds(recs)
    check("catalogue walk produced products", k.get("product", 0) > 20, str(k))
    check("budget respected", len(recs) <= 60, str(len(recs)))


LIVE = {
    "search": live_search,
    "searchSuggestions": live_suggestions,
    "categoryTree": live_category_tree,
    "categoryProducts": live_category_products,
    "paging": live_paging,
    "productDetail": live_product_detail,
    "brandDirectory": live_brand_directory,
    "brandProducts": live_brand_products,
    "feeds": live_feeds,
    "promoBanners": live_promo_banners,
    "promoProducts": live_promo_products,
    "rescue": live_poisoned_page,
    "fullCatalog": live_full_catalog,
}


async def main() -> int:
    wanted = sys.argv[1:]
    test_gate()
    test_input_resolution()
    test_enrichment()
    test_dataset_schema()

    for name, fn in LIVE.items():
        if wanted and name not in wanted:
            continue
        try:
            await fn()
        except Exception as exc:  # noqa: BLE001 - one bad mode must not hide the rest
            FAILED.append(f"{name} raised {type(exc).__name__}: {exc}")
            print(f"  [FAIL] {name} raised {type(exc).__name__}: {exc}")

    print(f"\n{'='*66}")
    print(f"PASSED {len(PASSED)}   FAILED {len(FAILED)}")
    for f in FAILED:
        print(f"  FAIL: {f}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
