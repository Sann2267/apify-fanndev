"""Local smoke test against live Amazon product pages."""

import asyncio
import json

from src.client import AmazonClient, Blocked
from src.constants import (
    AMAZON_MERCHANT_ID,
    CHANGE_BUYBOX_FLIP,
    CHANGE_NEW,
    CHANGE_OUT_OF_STOCK,
    CHANGE_PRICE_DOWN,
    CHANGE_UNCHANGED,
    RECORD_PRODUCT,
    TLS_PROFILE_LADDER,
)
from src.product import (
    InvalidInput,
    clean_asin,
    detect_changes,
    extract_price,
    in_stock,
    is_blocked,
    parse_buybox,
    parse_price,
    parse_product,
    product_url,
    snapshot_key,
)

# One ASIN measured to serve the Buy Box block, one measured not to.
ASIN_WITH_BUYBOX = "B00XIKPUK4"
ASIN_WITHOUT_BUYBOX = "B0BJLBD427"

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
    print("\n=== ASIN validation ===")
    failures += not check("plain ASIN kept", clean_asin("B00XIKPUK4") == "B00XIKPUK4")
    failures += not check("lowercase upcased", clean_asin("b00xikpuk4") == "B00XIKPUK4")
    failures += not check("extracted from /dp/ URL",
                          clean_asin("https://www.amazon.com/dp/B00XIKPUK4?th=1") == "B00XIKPUK4")
    failures += not check("extracted from /gp/product/ URL",
                          clean_asin("https://www.amazon.com/gp/product/B06XX65GS1") == "B06XX65GS1")
    for bad in ("", "   ", "TOOLONG12345", "SHORT", "https://www.amazon.com/s?k=x"):
        try:
            clean_asin(bad)
            failures += not check(f"rejects {bad[:22]!r}", False, "no exception raised")
        except InvalidInput:
            failures += not check(f"rejects {bad[:22]!r}", True)

    print("\n=== price parsing (locale-aware) ===")
    for text, want in (("$19.99", 19.99), ("IDR\xa0336,939.57", 336939.57),
                       ("£24.50", 24.5), ("€1.234,56", 1234.56)):
        amount, _ = parse_price(text)
        failures += not check(f"parse {text[:16]!r}", abs((amount or 0) - want) < 0.01,
                              f"got {amount}")
    failures += not check("price None-safe", parse_price(None) == (None, None))

    print("\n=== canonical price extraction ===")
    # THE regression that motivated extract_price(). A page with no Buy Box
    # still carries a-offscreen spans for related products and other
    # variants; taking the first one invented a $2489.00 price for a $25
    # protein powder. No canonical container => no price.
    noise = ('<span class="a-offscreen">$59.99</span>'
             '<span class="a-offscreen">$1.48</span>'
             '<span class="a-offscreen">$54.99</span>') * 50
    amount, _ = extract_price(noise)
    failures += not check("unrelated a-offscreen spans yield NO price",
                          amount is None, f"got {amount}")
    failures += not check("priceAmount JSON preferred",
                          extract_price('"priceAmount":62.99' + noise)[0] == 62.99)
    failures += not check(
        "corePrice_feature_div used when JSON absent",
        extract_price('<div id="corePrice_feature_div">'
                      '<span class="a-offscreen">$24.89</span></div>' + noise)[0] == 24.89,
    )
    failures += not check("twister-plus value used",
                          extract_price('twister-plus-price-data-price" value="102.95"'
                                        + noise)[0] == 102.95)

    print("\n=== block detection (a /dp/ block is HTTP 200) ===")
    failures += not check("short body is blocked", is_blocked("x" * 5000))
    failures += not check("continue-shopping wall detected",
                          is_blocked("Click the button below to continue shopping" + "x" * 400_000))
    failures += not check("real page not blocked", not is_blocked("y" * 400_000))

    print("\n=== stock tri-state ===")
    failures += not check("'In Stock' -> True", in_stock("In Stock", False) is True)
    failures += not check("'Currently unavailable' -> False",
                          in_stock("Currently unavailable", True) is False)
    failures += not check("'Only 3 left in stock' -> True",
                          in_stock("Only 3 left in stock", False) is True)
    # Null must stay null: Amazon serving no signal is not the same as
    # "out of stock", and collapsing the two would invent OUT_OF_STOCK alerts.
    failures += not check("no signal at all -> None", in_stock(None, False) is None)
    # The cart button alone is not proof: the reduced page variant renders one
    # while serving no price or seller at all.
    failures += not check("cart button without offer block -> None",
                          in_stock(None, True, False) is None)
    failures += not check("cart button with offer block -> True",
                          in_stock(None, True, True) is True)

    print("\n=== Buy Box availability flag ===")
    empty = parse_buybox("<html>no offer block here</html>")
    failures += not check("absent Buy Box marked unavailable", empty["available"] is False)
    failures += not check("absent Buy Box has null isAmazonSeller",
                          empty["isAmazonSeller"] is None)
    amazon = parse_buybox(f'<input name="merchantID" value="{AMAZON_MERCHANT_ID}">')
    failures += not check("Amazon merchant id recognised", amazon["isAmazonSeller"] is True)
    failures += not check("Amazon seller named", amazon["sellerName"] == "Amazon.com")
    third = parse_buybox('<input name="merchantID" value="A2GB0T0Z517LEH">')
    failures += not check("3P seller not flagged as Amazon", third["isAmazonSeller"] is False)

    print("\n=== change detection ===")
    base = {"price": 50.0, "buyBoxSellerId": "A1", "inStock": True}
    failures += not check("no snapshot -> NEW",
                          detect_changes(base, None)["changeType"] == CHANGE_NEW)
    failures += not check("identical -> UNCHANGED",
                          detect_changes(base, {"price": 50.0, "buyBoxSellerId": "A1",
                                                "inStock": True})["changeType"] == CHANGE_UNCHANGED)
    drop = detect_changes({"price": 40.0, "buyBoxSellerId": "A1", "inStock": True},
                          {"price": 50.0, "buyBoxSellerId": "A1", "inStock": True})
    failures += not check("price drop detected", drop["changeType"] == CHANGE_PRICE_DOWN)
    failures += not check("delta signed", drop["priceDelta"] == -10.0, str(drop["priceDelta"]))
    failures += not check("delta percent", drop["priceDeltaPercent"] == -20.0,
                          str(drop["priceDeltaPercent"]))
    flip = detect_changes({"price": 50.0, "buyBoxSellerId": "A2", "inStock": True},
                          {"price": 50.0, "buyBoxSellerId": "A1", "inStock": True})
    failures += not check("Buy Box flip detected", flip["changeType"] == CHANGE_BUYBOX_FLIP)
    # THE false-alert guard: Amazon withholds the Buy Box block on ~half of
    # anonymous requests. A row whose seller is simply absent this run must
    # NOT be reported as a seller change, or half the portfolio would alert
    # on every run.
    withheld = detect_changes({"price": 50.0, "buyBoxSellerId": None, "inStock": True},
                              {"price": 50.0, "buyBoxSellerId": "A1", "inStock": True})
    failures += not check("withheld seller is NOT a Buy Box flip",
                          withheld["changeType"] == CHANGE_UNCHANGED, withheld["changeType"])
    stock = detect_changes({"price": 50.0, "buyBoxSellerId": "A1", "inStock": False},
                           {"price": 50.0, "buyBoxSellerId": "A1", "inStock": True})
    failures += not check("went out of stock", stock["changeType"] == CHANGE_OUT_OF_STOCK)
    # Likewise: unknown stock must not masquerade as a stock-out.
    unknown = detect_changes({"price": 50.0, "buyBoxSellerId": "A1", "inStock": None},
                             {"price": 50.0, "buyBoxSellerId": "A1", "inStock": True})
    failures += not check("unknown stock is NOT OUT_OF_STOCK",
                          unknown["changeType"] == CHANGE_UNCHANGED, unknown["changeType"])

    print("\n=== ladder guard ===")
    # Measured on /dp/ specifically; safari184 works on Amazon SEARCH but not
    # here, so this list must not be copied between actors.
    failures += not check(
        "ladder holds only /dp/-verified profiles",
        set(TLS_PROFILE_LADDER) == {"chrome131", "chrome133a", "chrome150", "chrome136"},
        str(TLS_PROFILE_LADDER),
    )

    # ---- live -----------------------------------------------------------
    print("\n=== live product fetch ===")
    client = AmazonClient(marketplace="com")
    records = []
    try:
        for asin in (ASIN_WITH_BUYBOX, ASIN_WITHOUT_BUYBOX):
            try:
                body = await client.get_product(product_url("com", asin))
            except Blocked as exc:
                failures += not check(f"{asin} fetched", False, str(exc))
                continue
            failures += not check(f"{asin} page fetched", len(body) > 250_000, f"{len(body)}B")
            record = parse_product(body, asin, "com")
            record["isVariationChild"] = False
            record.update(detect_changes(record, None))
            records.append(record)
            print(f"    {asin} | {(record['title'] or '?')[:50]}")
            print(f"      price={record['currency']}{record['price']} "
                  f"rating={record['rating']} reviews={record['reviewCount']} "
                  f"bsr={record['bestSellersRank']}")
            print(f"      buyBoxAvailable={record['buyBoxDataAvailable']} "
                  f"seller={record['buyBoxSellerName']} ({record['buyBoxSellerId']}) "
                  f"returns={record['returnPolicy']}")
            print(f"      variations={record['variationCount']} "
                  f"dims={record['variationDimensions']}")
            await asyncio.sleep(2)

        failures += not check("both ASINs returned rows", len(records) == 2, str(len(records)))
        if records:
            failures += not check("titles extracted", all(r["title"] for r in records))
            failures += not check("ratings extracted", all(r["rating"] for r in records))
            failures += not check("review counts extracted",
                                  all(r["reviewCount"] for r in records),
                                  str([r["reviewCount"] for r in records]))
            failures += not check("asin echoed on every row",
                                 all(r["asin"] and r["recordType"] == RECORD_PRODUCT
                                     for r in records))
            # Currency must be pinned by the i18n-prefs cookie regardless of
            # the machine's egress country.
            # A null price must never carry a currency, and a page with no
            # canonical price container must report null rather than a
            # neighbouring product's price.
            for r in records:
                if r["price"] is None:
                    failures += not check(f"{r['asin']}: null price has null currency",
                                          r["currency"] is None, str(r["currency"]))
                    failures += not check(f"{r['asin']}: null price has null condition",
                                          r["condition"] is None, str(r["condition"]))
            symbols = {r["currency"] for r in records if r["price"] is not None}
            failures += not check("currency pinned to marketplace", symbols <= {"$"},
                                  f"saw {symbols}")
            # The flag must never claim data it does not have.
            for r in records:
                if not r["buyBoxDataAvailable"]:
                    failures += not check(
                        f"{r['asin']}: unavailable Buy Box carries no seller",
                        r["buyBoxSellerId"] is None and r["buyBoxSellerName"] is None,
                    )
                else:
                    failures += not check(
                        f"{r['asin']}: available Buy Box carries a seller",
                        bool(r["buyBoxSellerId"] or r["buyBoxSellerName"]),
                    )
            failures += not check_schema(records, schema)

            print("\n=== snapshot round-trip ===")
            snap = snapshot_key(records[0])
            failures += not check("snapshot is JSON-serialisable",
                                  json.loads(json.dumps(snap)) == snap)
            again = detect_changes(records[0], snap)
            failures += not check("same data re-compares as UNCHANGED",
                                  again["changeType"] == CHANGE_UNCHANGED,
                                  again["changeType"])
    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
