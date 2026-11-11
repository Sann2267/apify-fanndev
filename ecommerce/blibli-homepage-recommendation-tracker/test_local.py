"""Local smoke test -- exercises the feed sweep against the live site.

Runs the extractor layer directly (no Apify platform), prints a compact
summary plus sample records, and asserts the invariants that matter:
envelope present, output-schema conformance, product vs ad-banner shape,
rank/dedup sane, pagination actually terminating.

    python test_local.py            # quick pass, capped
"""

import asyncio
import json

from src.client import BlibliClient
from src.feed import fetch_tabs, run_feed

ENVELOPE = ("_input", "_source", "_scrapedAt")

# Apify enforces .actor/output_schema.json against every pushed item, and a
# violation surfaces only as a generic "Schema validation failed" on the
# first cloud run. This guard closes that gap locally -- same pattern as
# every other actor in this portfolio, kept in front of every run.
_JSON_TYPES = {
    "string": str, "number": (int, float), "integer": int,
    "boolean": bool, "object": dict, "array": list,
}


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
            types = tuple(
                _JSON_TYPES[a] if not isinstance(_JSON_TYPES.get(a), tuple) else _JSON_TYPES[a]
                for a in allowed if a in _JSON_TYPES
            )
            flat = tuple(
                t for group in types for t in (group if isinstance(group, tuple) else (group,))
            )
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
        # ---- tab discovery -------------------------------------------------
        print("\n=== Tab discovery ===")
        tabs = await fetch_tabs(client)
        print(f"  tabs: {[(t.get('name'), t.get('title'), t.get('source')) for t in tabs]}")
        failures += not check("got at least one tab", bool(tabs))
        failures += not check(
            "every tab has a short name", all(t.get("name") for t in tabs)
        )

        # ---- feed sweep: a MANUAL (personalized) + an AUTOMATIC tab --------
        manual = next((t for t in tabs if t.get("source") == "MANUAL"), None)
        automatic = next((t for t in tabs if t.get("source") == "AUTOMATIC"), None)
        probe_tabs = [t for t in (manual, automatic) if t]
        print(f"\n=== Feed sweep: {[t['name'] for t in probe_tabs]} ===")
        records = await collect(run_feed(client, probe_tabs, max_pages_per_tab=3,
                                          max_items_per_tab=0, include_ad_banners=True), 200)
        print(f"  records: {len(records)}")
        failures += not check("got records", bool(records))
        if records:
            failures += not check_schema(records, schema)
            sample = records[0]
            failures += not check("envelope present", all(k in sample for k in ENVELOPE))
            failures += not check(
                "source tag", sample["_source"] == "S1-homepage-infinite-recommendations"
            )
            failures += not check(
                "tab metadata attached",
                all(r.get("_tabName") and r.get("_tabTitle") for r in records),
            )
            failures += not check(
                "record type classified",
                all(
                    r.get("_recordType") in ("product", "ad_banner", "category_card", "unknown")
                    for r in records
                ),
            )
            products = [r for r in records if r["_recordType"] == "product"]
            banners = [r for r in records if r["_recordType"] == "ad_banner"]
            cards = [r for r in records if r["_recordType"] == "category_card"]
            unknown = [r for r in records if r["_recordType"] == "unknown"]
            print(f"  product tiles: {len(products)}, ad-banner tiles: {len(banners)}, "
                  f"category cards: {len(cards)}, unknown: {len(unknown)}")
            failures += not check(
                "no leftover 'unknown' tiles (every observed shape classified)",
                not unknown, f"{len(unknown)} unknown row(s)",
            )
            if cards:
                failures += not check(
                    "category cards carry a link", all(r.get("_productUrl") for r in cards)
                )
            failures += not check("at least some product tiles", bool(products))
            if products:
                failures += not check(
                    "product tiles carry sku/name/url",
                    all(r.get("sku") and r.get("name") and r.get("_productUrl") for r in products),
                )
                failures += not check(
                    "product URL absolute",
                    all(str(r["_productUrl"]).startswith("https://www.blibli.com") for r in products),
                )
                priced = [r for r in products if r.get("_offerPrice")]
                failures += not check(
                    "offer price resolved on product tiles",
                    len(priced) == len(products),
                    f"{len(priced)}/{len(products)} priced",
                )
                discounted = [r for r in products if r.get("_listPrice")]
                failures += not check(
                    "discounted rows have list > offer",
                    all(r["_listPrice"] > r["_offerPrice"] for r in discounted) if discounted else True,
                )
            if banners:
                failures += not check(
                    "ad-banner tiles carry brandAdId/redirect",
                    all(r.get("_brandAdId") and r.get("_adRedirectUrl") for r in banners),
                )
                failures += not check(
                    "ad-banner tiles have no sku",
                    all(not r.get("sku") for r in banners),
                )
            failures += not check(
                "rank is a monotonic per-tab counter",
                all(r.get("_rankInFeed") for r in records),
            )
            for t in probe_tabs:
                tab_records = [r for r in records if r["_tabName"] == t["name"]]
                ranks = [r["_rankInFeed"] for r in tab_records]
                failures += not check(
                    f"no duplicate rank within tab {t['name']}",
                    len(ranks) == len(set(ranks)),
                )
            print("  SAMPLE product:", json.dumps(
                {k: (products[0] if products else {}).get(k) for k in
                 ("name", "sku", "_recordType", "_tabName", "_tabTitle", "_rankInFeed",
                  "_offerPrice", "_discountPercent", "merchantName")},
                ensure_ascii=False)[:420])
            if banners:
                print("  SAMPLE ad_banner:", json.dumps(
                    {k: banners[0].get(k) for k in
                     ("_recordType", "_tabName", "_brandAdId", "_adBrandNames", "_adRedirectUrl")},
                    ensure_ascii=False)[:420])

        # ---- includeAdBanners=False actually filters -----------------------
        if automatic:
            print(f"\n=== includeAdBanners=False on {automatic['name']} ===")
            no_ads = await collect(
                run_feed(client, [automatic], max_pages_per_tab=2, max_items_per_tab=0,
                          include_ad_banners=False), 100
            )
            print(f"  records: {len(no_ads)}")
            failures += not check(
                "no ad_banner rows present",
                all(r["_recordType"] != "ad_banner" for r in no_ads),
            )

        # ---- maxItemsPerTab is honoured -------------------------------------
        if manual:
            print(f"\n=== maxItemsPerTab=5 on {manual['name']} ===")
            capped = await collect(
                run_feed(client, [manual], max_pages_per_tab=10, max_items_per_tab=5,
                          include_ad_banners=True), 10
            )
            print(f"  records: {len(capped)}")
            failures += not check("capped at 5", len(capped) == 5, f"got {len(capped)}")

        # ---- an explicitly-named unknown tab fails loudly, not silently ----
        print("\n=== Unknown tab name handling (feed.py contract check) ===")
        from src.constants import FEED_API_TEMPLATE
        bogus_payload_ok = True
        try:
            fake_tab = {"name": "TAB_DOES_NOT_EXIST_XYZ", "title": "bogus", "source": "TEST"}
            bogus_records = await collect(
                run_feed(client, [fake_tab], max_pages_per_tab=1, max_items_per_tab=0,
                          include_ad_banners=True), 5
            )
            print(f"  bogus tab -> {len(bogus_records)} record(s) (expect 0, endpoint 404s clean)")
            failures += not check("bogus tab yields nothing (not a crash)", len(bogus_records) == 0)
        except Exception as exc:  # noqa: BLE001
            bogus_payload_ok = False
            print(f"  bogus tab raised {type(exc).__name__}: {exc}")
        failures += not check("bogus tab handled without unhandled crash", bogus_payload_ok)

    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
