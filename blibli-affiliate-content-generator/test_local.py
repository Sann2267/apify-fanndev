"""Local smoke test against the live site.

    python test_local.py         # capped
    python test_local.py --full  # larger sourcing run
"""

import asyncio
import json
import sys

from src.client import BlibliClient
from src.constants import SORT_OPTIONS
from src.content import (
    InvalidInput,
    build_caption,
    build_search_params,
    build_tracked_url,
    clean_product_url,
    finalize,
    mint_share_link,
    parse_selling_points,
    passes_filters,
    resize_image,
    run_query,
    short_description,
)

FULL = "--full" in sys.argv
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
        # ---- pure content parsing (no network) ---------------------------
        print("\n=== content parsing ===")
        raw = "• Processor : Intel i3 \n<br>• Memory : 8GB \n<br>• Storage : 512GB SSD"
        bullets = parse_selling_points(raw)
        failures += not check("selling points split", len(bullets) == 3, str(bullets[:2]))
        failures += not check("markup stripped", not any("<" in b for b in bullets))
        failures += not check("bullet glyph stripped", not any(b.startswith("•") for b in bullets))
        failures += not check("empty input -> []", parse_selling_points(None) == [])
        failures += not check(
            "short description joins", "·" in (short_description(bullets, "X") or "")
        )
        failures += not check(
            "short description falls back to name",
            short_description([], "Fallback Name") == "Fallback Name",
        )

        img = ("https://www.static-src.com/wcsstore/Indraprastha/images/catalog/medium/"
               "catalog-image/1/MTA-1/x_full01.webp")
        failures += not check("image resize to full", "/catalog/full/" in resize_image(img, "full"))
        failures += not check("image resize None-safe", resize_image(None, "full") is None)

        dirty = "/p/foo/ps--BLL-1?ds=X&source=SEARCH&sid=abc&metaData=zz"
        cleaned = clean_product_url(dirty)
        failures += not check(
            "product URL cleaned", cleaned == "https://www.blibli.com/p/foo/ps--BLL-1", cleaned
        )
        tracked = build_tracked_url(cleaned, "aff-me", "instagram", "social")
        failures += not check(
            "UTM appended",
            all(k in tracked for k in ("utm_campaign=aff-me", "utm_source=instagram",
                                       "utm_medium=social")),
            tracked,
        )
        failures += not check(
            "no UTM values -> plain URL", build_tracked_url(cleaned, "", "", "") == cleaned
        )

        # ---- caption -----------------------------------------------------
        print("\n=== caption ===")
        rec = {"name": "Laptop X", "salePrice": 3799000, "listPrice": 4599000,
               "discountPercent": 17, "rating": 4.9, "soldCount": 1513,
               "shortDescription": "Intel i3 · 8GB", "shareLink": "https://x.co/1"}
        cap = build_caption(rec, "{name} Rp{price} diskon {discount} {rating}* {sold} terjual {link}")
        failures += not check("caption rendered", "Rp3.799.000" in cap and "17%" in cap, cap[:90])
        # Regression: the value must not carry its own "Rp" prefix, or the
        # default template ("Rp{price}") renders "RpRp3.799.000".
        failures += not check("no double Rp prefix", "RpRp" not in cap)
        try:
            build_caption(rec, "{nope}")
            failures += not check("bad placeholder raises", False)
        except InvalidInput:
            failures += not check("bad placeholder raises InvalidInput", True)
        failures += not check("no template -> None", build_caption(rec, None) is None)

        # ---- filter construction ------------------------------------------
        print("\n=== filters ===")
        params = build_search_params(
            {"type": "searchTerm", "value": "laptop"},
            {"sort": "16", "min_rating": 4, "official_warranty": True, "min_discount": 30}, 1,
        )
        failures += not check("sort pushed", params["sort"] == "16")
        failures += not check("rating pushed", params["rating"] == "4")
        failures += not check("warranty pushed", params["warrantyType"] == "Garansi Resmi")
        failures += not check("discount snapped to bucket", params["discount"] == "25")
        good = {"review": {"absoluteRating": 4.8, "count": 50}, "soldCountTotal": 100,
                "officialMerchant": True, "price": {"discount": 40}}
        failures += not check("passes when qualifying", passes_filters(good, {"min_rating": 4.5}))
        failures += not check(
            "rejects below rating", not passes_filters(good, {"min_rating": 4.9})
        )
        failures += not check(
            "rejects below sold", not passes_filters(good, {"min_sold": 500})
        )

        # ---- live sourcing --------------------------------------------------
        print("\n=== live sourcing (bestselling, 4+, official warranty) ===")
        filters = {
            "sort": SORT_OPTIONS["bestSelling"], "min_rating": 4, "min_reviews": 10,
            "min_sold": 0, "min_discount": 0, "official_warranty": True,
            "official_store": False, "top_rated_seller": False, "image_size": "full",
            "campaign": "aff-demo", "source": "instagram", "medium": "social",
            "generate_share_link": True, "enrich": True,
            "caption_template": "{name}\nRp{price} ({discount}) {rating}* {sold} terjual\n{link}",
        }
        cap = None if FULL else 8
        records = await collect(
            run_query(client, {"type": "searchTerm", "value": "laptop", "label": "laptop"},
                      filters, cap or 0), cap
        )
        print(f"  sourced: {len(records)}")
        failures += not check("got products", bool(records))

        sem = asyncio.Semaphore(4)
        finished = await asyncio.gather(
            *(finalize(client, r, filters, sem) for r in records)
        )
        if finished:
            sample = finished[0]
            failures += not check("envelope present", all(k in sample for k in ENVELOPE))
            failures += not check("raw passthrough kept", "merchantCode" in sample)
            failures += not check(
                "all rated >= 4",
                all(r["rating"] >= 4 for r in finished if r.get("rating")),
            )
            failures += not check(
                "clean product URLs (no session query)",
                all("source=SEARCH" not in (r.get("productUrl") or "") for r in finished),
            )
            failures += not check(
                "tracked URL on every row",
                all("utm_campaign=aff-demo" in (r.get("trackedUrl") or "") for r in finished),
            )
            minted = [r for r in finished if r.get("shareLink")]
            failures += not check(
                "share links minted",
                len(minted) >= len(finished) * 0.8,
                f"{len(minted)}/{len(finished)}",
            )
            failures += not check(
                "share links are onelink",
                all("onelink.me" in r["shareLink"] for r in minted),
            )
            failures += not check(
                "images full-size",
                all("/catalog/full/" in (r.get("primaryImage") or "/catalog/full/")
                    for r in finished),
            )
            failures += not check(
                "captions rendered", all(r.get("caption") for r in finished)
            )
            enriched = [r for r in finished if r.get("warrantyText")]
            failures += not check(
                "warranty text from enrichment", bool(enriched),
                f"{len(enriched)}/{len(finished)} enriched",
            )
            failures += not check_schema(finished, schema)
            print("  SAMPLE:", json.dumps({k: sample.get(k) for k in (
                "sku", "name", "salePrice", "discountPercent", "rating", "soldCount",
                "warrantyText", "isOfficialStore", "shareLink")}, ensure_ascii=False)[:420])
            print("  DESC  :", (sample.get("shortDescription") or "")[:170])
            print("  CAPTION:\n   ", (sample.get("caption") or "").replace("\n", "\n    ")[:340])

        # ---- share-link determinism -----------------------------------------
        print("\n=== share link determinism ===")
        url = "https://www.blibli.com/p/x/ps--BLL-70058-00122"
        a = await mint_share_link(client, url, "c", "s", "m")
        b = await mint_share_link(client, url, "c", "s", "m")
        failures += not check("same payload -> same link", a == b and bool(a), str(a))
    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
