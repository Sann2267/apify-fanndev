"""Local smoke test against live Amazon search."""

import asyncio
import json
import sys

from src.ads import (
    InvalidInput,
    clean_keyword,
    clean_title,
    is_sponsored,
    parse_page,
    parse_price,
    search_url,
    slot_band,
    split_items,
    summary_record,
)
from src.client import AmazonClient
from src.constants import RECORD_AD, RECORD_SUMMARY, TLS_PROFILE_LADDER

KEYWORD = "yoga mat"

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


async def main() -> int:
    schema = load_output_schema()
    failures = 0

    # ---- offline --------------------------------------------------------
    print("\n=== keyword + URL ===")
    failures += not check("whitespace collapsed",
                          clean_keyword("  wireless   earbuds ") == "wireless earbuds")
    for bad in ("", "   ", "x" * 260):
        try:
            clean_keyword(bad)
            failures += not check(f"rejects {bad[:14]!r}", False, "no exception")
        except InvalidInput:
            failures += not check(f"rejects {bad[:14]!r}", True)
    failures += not check(
        "URL encodes spaces",
        search_url("com", "yoga mat") == "https://www.amazon.com/s?k=yoga+mat",
        search_url("com", "yoga mat"),
    )
    failures += not check("co.uk base", search_url("co.uk", "x").startswith("https://www.amazon.co.uk"))

    print("\n=== price parsing (locale-aware) ===")
    for text, want_amount, want_cur in (
        ("$19.99", 19.99, "$"),
        ("IDR\xa0336,939.57", 336939.57, "IDR"),
        ("£24.50", 24.50, "£"),
        ("List: $28.99", 28.99, None),
        ("€1.234,56", 1234.56, "€"),
    ):
        amount, currency = parse_price(text)
        ok = abs((amount or 0) - want_amount) < 0.01
        failures += not check(f"parse {text[:18]!r}", ok, f"got {amount} {currency}")
    failures += not check("price None-safe", parse_price(None) == (None, None))

    print("\n=== slot bands ===")
    for pos, want in ((1, "TOP"), (4, "TOP"), (5, "MID"), (20, "MID"), (21, "LOWER")):
        failures += not check(f"position {pos} -> {want}", slot_band(pos) == want)

    print("\n=== sponsored marker discipline ===")
    failures += not check("real label detected",
                          is_sponsored('<span class="puis-sponsored-label-text">Sponsored</span>'))
    # These strings appear on the page OUTSIDE result tiles; counting them
    # would inflate every keyword's ad share.
    failures += not check("feedback-widget string NOT counted",
                          not is_sponsored('<div class="s-sponsored-label-info-icon"></div>'))
    failures += not check("AdHolder alone NOT counted", not is_sponsored('<div class="AdHolder">'))

    print("\n=== title cleaning ===")
    # Amazon prefixes sponsored aria-labels with "Sponsored Ad - "; leaving it
    # in would make an ad row's title differ from the same product organically.
    failures += not check(
        "ad-label prefix stripped",
        clean_title("Sponsored Ad - COOLMOON Yoga Mat") == "COOLMOON Yoga Mat",
        clean_title("Sponsored Ad - COOLMOON Yoga Mat"),
    )
    failures += not check("organic title untouched",
                          clean_title("COOLMOON Yoga Mat") == "COOLMOON Yoga Mat")
    failures += not check("entities unescaped",
                          clean_title("Yoga Mat 72&quot;x24&quot;") == 'Yoga Mat 72"x24"')

    print("\n=== ladder guard ===")
    failures += not check(
        "ladder holds only verified profiles",
        set(TLS_PROFILE_LADDER) == {"chrome131", "chrome133a", "chrome136", "chrome150",
                                    "safari184"},
        str(TLS_PROFILE_LADDER),
    )

    # ---- live -----------------------------------------------------------
    print("\n=== live search ===")
    client = AmazonClient(marketplace="com")
    try:
        html = await client.get_search(search_url("com", KEYWORD))
        failures += not check("page fetched", len(html) > 200_000, f"{len(html)}B")

        items = split_items(html)
        failures += not check("results parsed", len(items) >= 10, str(len(items)))
        asins = [a for a, _ in items]
        failures += not check("unique ASINs per page", len(asins) == len(set(asins)),
                              f"{len(set(asins))}/{len(asins)}")

        ctx = {"keyword": KEYWORD, "marketplace": "com", "sample": 1}
        records = parse_page(html, ctx)
        ads = [r for r in records if r["isSponsored"]]
        print(f"  {len(records)} results, {len(ads)} sponsored "
              f"({len(ads)/max(len(records),1)*100:.1f}%)")
        failures += not check("every row has asin + url",
                              all(r["asin"] and r["productUrl"] for r in records))
        titled = [r for r in records if r.get("title")]
        failures += not check("titles extracted", len(titled) >= len(records) * 0.9,
                              f"{len(titled)}/{len(records)}")
        priced = [r for r in records if r.get("price")]
        failures += not check("prices extracted", len(priced) >= len(records) * 0.5,
                              f"{len(priced)}/{len(records)}")
        # The i18n-prefs cookie must force the marketplace currency even
        # though this machine's IP is not in the US.
        currencies = {r["currency"] for r in priced if r.get("currency")}
        failures += not check(
            "currency forced to marketplace (not egress geo)",
            currencies <= {"$"}, f"saw {currencies} (expected $ for .com)",
        )
        failures += not check("record types set",
                              all(r["recordType"] in ("SPONSORED_AD", "ORGANIC")
                                  for r in records))
        if ads:
            failures += not check("ads carry a slot band",
                                  all(a["slotBand"] for a in ads))
            failures += not check("ads typed SPONSORED_AD",
                                  all(a["recordType"] == RECORD_AD for a in ads))
            failures += not check(
                "no ad-label prefix leaks into titles",
                not any(str(a.get("title", "")).lower().startswith("sponsored ad")
                        for a in ads),
            )
            print("  AD:", json.dumps({k: ads[0].get(k) for k in (
                "position", "slotBand", "asin", "title", "price", "currency",
                "rating", "reviewCount")}, ensure_ascii=False)[:250])
        else:
            print("  NOTE: 0 sponsored this impression -- legitimate; density measured "
                  "0-21.7% across keywords.")
        failures += not check_schema(records, schema)

        print("\n=== summary roll-up ===")
        summary = summary_record(records, {"keyword": KEYWORD, "marketplace": "com"}, 1)
        failures += not check("summary type", summary["recordType"] == RECORD_SUMMARY)
        failures += not check("counts add up",
                              summary["sponsoredCount"] + summary["organicCount"]
                              == summary["totalResults"])
        failures += not check("share computed",
                              summary["sponsoredSharePercent"] is not None)
        failures += not check("summary emitted even with zero ads",
                              isinstance(summary["sponsoredCount"], int))
        failures += not check_schema([summary], schema)
        print("  SUMMARY:", json.dumps({k: summary.get(k) for k in (
            "totalResults", "sponsoredCount", "sponsoredSharePercent", "topSlotAdCount",
            "uniqueAdvertisedAsins", "avgAdPrice")}, ensure_ascii=False)[:280])
        if summary["mostPersistentAsins"]:
            print("  TOP ADVERTISERS:",
                  json.dumps(summary["mostPersistentAsins"][:3], ensure_ascii=False))
    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
