"""Local smoke test against live Amazon search."""

import asyncio
import json

from src.client import AmazonClient
from src.constants import RECORD_PRODUCT, TLS_PROFILE_LADDER
from src.serp import (
    InvalidInput,
    clean_keyword,
    extract_brand,
    has_next_page,
    normalise_target,
    paginate,
    parse_compact_number,
    parse_page,
    parse_price,
    search_url,
    split_items,
)

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


async def main() -> int:
    schema = load_output_schema()
    failures = 0

    # ---- offline --------------------------------------------------------
    print("\n=== keyword + URL handling ===")
    failures += not check("whitespace collapsed",
                          clean_keyword("  wireless   earbuds ") == "wireless earbuds")
    for bad in ("", "   ", "x" * 260):
        try:
            clean_keyword(bad)
            failures += not check(f"rejects {bad[:12]!r}", False, "no exception")
        except InvalidInput:
            failures += not check(f"rejects {bad[:12]!r}", True)
    failures += not check("URL encodes spaces",
                          search_url("com", "yoga mat") == "https://www.amazon.com/s?k=yoga+mat")

    print("\n=== target normalisation ===")
    kw = normalise_target("yoga mat", "com")
    failures += not check("keyword becomes a search URL",
                          kw["url"] == "https://www.amazon.com/s?k=yoga+mat" and kw["type"] == "keyword")
    with_k = normalise_target("https://www.amazon.com/s?k=yoga+mat&rh=n%3A3407731", "com")
    failures += not check("URL with k= accepted", with_k["type"] == "url")
    failures += not check("label taken from k=", with_k["label"] == "yoga mat", with_k["label"])
    # MEASURED: node-only URLs render a browse page with zero search results,
    # so they must fail loudly rather than quietly returning nothing.
    for bad_url in ("https://www.amazon.com/s?rh=n%3A3407731",
                    "https://www.amazon.com/s?node=3407731",
                    "https://www.amazon.com/b/?node=3407731"):
        try:
            normalise_target(bad_url, "com")
            failures += not check(f"rejects node-only {bad_url[-18:]!r}", False, "accepted")
        except InvalidInput as exc:
            failures += not check(f"rejects node-only {bad_url[-18:]!r}",
                                  "k=" in str(exc))
    try:
        normalise_target("https://www.ebay.com/s?k=x", "com")
        failures += not check("rejects non-amazon host", False, "accepted")
    except InvalidInput:
        failures += not check("rejects non-amazon host", True)

    print("\n=== pagination helper ===")
    failures += not check("page 1 leaves URL clean",
                          paginate("https://www.amazon.com/s?k=x", 1)
                          == "https://www.amazon.com/s?k=x")
    failures += not check("page appended",
                          paginate("https://www.amazon.com/s?k=x", 3)
                          == "https://www.amazon.com/s?k=x&page=3")
    failures += not check("existing page replaced, not duplicated",
                          paginate("https://www.amazon.com/s?k=x&page=2", 5)
                          == "https://www.amazon.com/s?k=x&page=5")
    failures += not check("next-page detection",
                          has_next_page('<a class="s-pagination-next" href="#">')
                          and not has_next_page("<div>no pagination</div>"))
    failures += not check("disabled next is not a next page",
                          not has_next_page(
                              '<span class="s-pagination-next s-pagination-disabled">'))

    print("\n=== number parsing ===")
    for text, want in (("$19.99", 19.99), ("IDR\xa0336,939.57", 336939.57),
                       ("£24.50", 24.5), ("€1.234,56", 1234.56)):
        amount, _ = parse_price(text)
        failures += not check(f"price {text[:14]!r}", abs((amount or 0) - want) < 0.01,
                              f"got {amount}")
    # The visible review count and the "bought in past month" figure are both
    # abbreviated on the page; reporting "10.5" for 10,500 would be wrong.
    for text, want in (("10.5K", 10500), ("6K", 6000), ("1.2M", 1200000),
                       ("153", 153), ("70.3K", 70300)):
        failures += not check(f"compact {text!r} -> {want}",
                              parse_compact_number(text) == want,
                              str(parse_compact_number(text)))
    failures += not check("compact rejects junk", parse_compact_number("abc") is None)

    print("\n=== brand heuristic (title-derived, not scraped) ===")
    failures += not check("leading brand word",
                          extract_brand("Gaiam Yoga Mat Classic Print, 4mm") == "Gaiam",
                          str(extract_brand("Gaiam Yoga Mat Classic Print, 4mm")))
    failures += not check("hyphenated brand kept",
                          extract_brand("BLACK+DECKER 12-Cup Drip Coffee Maker")
                          == "BLACK+DECKER")
    failures += not check("None-safe", extract_brand(None) is None)

    print("\n=== ladder guard ===")
    # Amazon SEARCH ladder -- NOT the /dp/ ladder (safari184 clears search
    # but is rejected on product pages).
    failures += not check(
        "ladder holds only search-verified profiles",
        set(TLS_PROFILE_LADDER) == {"chrome131", "chrome133a", "chrome136",
                                    "chrome150", "safari184"},
        str(TLS_PROFILE_LADDER))

    # ---- live -----------------------------------------------------------
    print("\n=== live search ===")
    client = AmazonClient(marketplace="com")
    try:
        html = await client.get_search(search_url("com", KEYWORD))
        failures += not check("page fetched", len(html) > 200_000, f"{len(html)}B")

        items = split_items(html)
        failures += not check("results parsed", len(items) >= 10, str(len(items)))
        asins = [a for a, _ in items]
        failures += not check("unique ASINs on a page",
                              len(asins) == len(set(asins)), f"{len(set(asins))}/{len(asins)}")

        context = {"label": KEYWORD, "url": search_url("com", KEYWORD),
                   "marketplace": "com", "page": 1, "offset": 0}
        records = parse_page(html, context)
        failures += not check("records built", len(records) == len(items))

        def coverage(field):
            return sum(1 for r in records if r.get(field) not in (None, False))

        print(f"    {len(records)} results | priced={coverage('price')} "
              f"rated={coverage('rating')} reviews={coverage('reviewCount')} "
              f"bought={coverage('boughtInPastMonth')} img={coverage('imageUrl')}")
        print(f"    sponsored={coverage('isSponsored')} bestSeller={coverage('isBestSeller')} "
              f"amazonsChoice={coverage('isAmazonsChoice')} prime={coverage('isPrime')}")

        failures += not check("every row has asin + url",
                              all(r["asin"] and r["productUrl"] for r in records))
        failures += not check("titles extracted",
                              coverage("title") >= len(records) * 0.9,
                              f"{coverage('title')}/{len(records)}")
        failures += not check("prices extracted",
                              coverage("price") >= len(records) * 0.5,
                              f"{coverage('price')}/{len(records)}")
        failures += not check("ratings extracted",
                              coverage("rating") >= len(records) * 0.5,
                              f"{coverage('rating')}/{len(records)}")
        # The exact count comes from the aria-label; if this collapses the
        # abbreviated fallback is silently taking over.
        failures += not check("review counts extracted",
                              coverage("reviewCount") >= len(records) * 0.5,
                              f"{coverage('reviewCount')}/{len(records)}")
        big = [r["reviewCount"] for r in records
               if isinstance(r["reviewCount"], int) and r["reviewCount"] > 1000]
        failures += not check("large review counts are exact, not abbreviated",
                              all(n % 100 != 0 or n % 1000 != 0 for n in big[:5]) or not big,
                              str(big[:5]))
        failures += not check("record type set",
                              all(r["recordType"] == RECORD_PRODUCT for r in records))
        failures += not check("positions are 1..n",
                              [r["position"] for r in records] == list(range(1, len(records) + 1)))
        failures += not check("no discount without a higher list price",
                              all(r["discountPercent"] is None
                                  or (r["listPrice"] and r["listPrice"] > r["price"])
                                  for r in records))
        failures += not check("prices are positive",
                              all(r["price"] is None or r["price"] > 0 for r in records))
        currencies = {r["currency"] for r in records if r["price"] is not None}
        failures += not check("currency pinned to marketplace",
                              currencies <= {"$"}, f"saw {currencies}")

        ships = {r["shipsTo"] for r in records if r["shipsTo"]}
        if ships:
            print(f"    NOTE: Amazon inferred delivery to {ships} from this IP -- "
                  "Prime/delivery need a US residential proxy to be meaningful.")

        problems = schema_violations(records, schema)
        failures += not check("matches output_schema.json", not problems,
                              "; ".join(problems[:4]))
        print("  SAMPLE:", json.dumps({k: records[0].get(k) for k in (
            "position", "asin", "title", "brandGuess", "price", "currency", "listPrice",
            "discountPercent", "rating", "reviewCount", "boughtInPastMonth",
            "isSponsored", "isBestSeller")}, ensure_ascii=False)[:330])
    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
