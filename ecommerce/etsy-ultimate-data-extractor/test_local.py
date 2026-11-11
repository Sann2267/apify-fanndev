"""Local checks for the Etsy actor: offline parser tests, then optional live runs.

    python test_local.py             parsers only, against the saved fixtures
    python test_local.py --live      also hit Etsy (a handful of requests)
    python test_local.py --live shop run one live mode by name

The offline half needs no network and is the one that has to stay green: it
pins the parsers to real pages captured on 2026-09-21, so a change in Etsy's
markup shows up as a failing assertion rather than as a dataset full of nulls.
"""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from src import parsers as P  # noqa: E402
from src.client import EtsyClient  # noqa: E402
from src.modes import (  # noqa: E402
    MODES,
    Budget,
    _own_listings,
    classify,
    normalise_locale,
    split_locale,
    with_locale,
)

FIXTURES = pathlib.Path(__file__).parent / "tests" / "fixtures"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logging.getLogger("etsy").setLevel(logging.INFO)

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} {detail}")
        failures.append(label)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_url_handling() -> None:
    print("\n-- URL handling --")
    check("category classified", classify("https://www.etsy.com/c/jewelry/rings") == "category")
    check("locale-prefixed shop classified", classify("https://www.etsy.com/uk/shop/X") == "shop")
    check("shop reviews classified", classify("https://www.etsy.com/de-en/shop/X/reviews") == "shopReviews")
    check("listing classified", classify("https://www.etsy.com/listing/1/a-b") == "listing")
    check("shop search classified", classify("https://www.etsy.com/search/shops?q=x") == "shopSearch")
    check(
        "a category path is not mistaken for a locale",
        split_locale("https://www.etsy.com/c/jewelry/rings") == ("", "c/jewelry/rings"),
    )
    check(
        "an unknown two-letter segment stays in the path",
        split_locale("https://www.etsy.com/zz/shop/X") == ("", "zz/shop/X"),
    )
    check("locale rewrite", with_locale("https://www.etsy.com/uk/c/x", "de-en") == "https://www.etsy.com/de-en/c/x")
    check("US normalises to no prefix", normalise_locale("us") == "")


def test_category_grid() -> None:
    print("\n-- category grid --")
    cards = P.parse_listing_cards(fixture("category_grid.html"))
    check("64 cards", len(cards) == 64, f"got {len(cards)}")
    organic = [c for c in cards if not c["isAd"]]
    check("ads separated from organic", 0 < len(organic) < len(cards), f"{len(organic)}/{len(cards)}")
    first = organic[0]
    for field in ("listingId", "title", "url", "shopName", "price", "shopRating", "shopReviewCount", "imageUrl"):
        check(f"organic card has {field}", first.get(field) is not None, repr(first.get(field)))
    check("url carries the exact slug", "/listing/" in first["url"] and first["url"].count("/") >= 5)
    check("tracking stripped from url", "?" not in first["url"])
    check(
        "card stars are the precise value, not the rounded display",
        first["shopRating"] == 4.72, str(first["shopRating"]),
    )
    check(
        "card review count is the shop's, matching that shop's own page",
        first["shopReviewCount"] == 9023, str(first["shopReviewCount"]),
    )
    check("discount captured", any(c.get("discount") for c in organic))
    check(
        "a discount is never mistaken for a review count",
        all(
            c["shopReviewCount"] != 30 or "30%" not in (c.get("discount") or "")
            for c in cards
        ),
    )
    merged = P.parse_grid(fixture("category_grid.html"))
    check("merged grid keeps every card", len(merged) == 64, f"got {len(merged)}")
    check("merged grid gains the ISO currency", merged[0].get("currency") == "IDR", str(merged[0].get("currency")))
    check("next page detected", P.has_next_page(fixture("category_grid.html"), 1) is True)
    check("no next page past the end", P.has_next_page("<html></html>", 1) is False)


def test_shop_search() -> None:
    print("\n-- shop keyword search --")
    shops = P.parse_shop_search(fixture("shop_search.html"))
    check("12 shops per page", len(shops) == 12, f"got {len(shops)}")
    check("shop names unique", len({s["shopName"] for s in shops}) == len(shops))
    check("item counts parsed", all(isinstance(s["itemCount"], int) for s in shops))
    check("preview images captured", all(s["previewImages"] for s in shops))


def test_shop_profile() -> None:
    print("\n-- shop profile --")
    html = fixture("shop_profile.html")
    p = P.parse_shop_profile(html, "https://www.etsy.com/uk/shop/PBJewelryGift")
    check("shop name", p["shopName"] == "PBJewelryGift", str(p["shopName"]))
    check("exact sales, not the abbreviated header", p["totalSales"] == 59504, str(p["totalSales"]))
    check("on Etsy since", p["onEtsySince"] == 2017, str(p["onEtsySince"]))
    check("location", p["location"] == "California, United States", str(p["location"]))
    check("review count from JSON-LD", p["reviewCount"] == 9023, str(p["reviewCount"]))
    check(
        "both ratings kept and they differ",
        p["ratingAllTime"] == 4.5 and p["ratingRecencyWeighted"] == 4.7,
        f"{p['ratingAllTime']} / {p['ratingRecencyWeighted']}",
    )
    check("announcement is copy, not CSS", p["announcement"] and "opacity" not in p["announcement"])
    check("shop members", len(p["members"] or []) == 4)
    check("faqs", len(p["faqs"] or []) == 5)

    catalogue = P.parse_shop_catalogue(html)
    check("catalogue parsed", len(catalogue) >= 30, f"got {len(catalogue)}")
    check("catalogue carries an ISO currency", catalogue[0]["currency"] == "GBP", str(catalogue[0]["currency"]))

    merged = P.parse_grid(html)
    check("shop grid merges markup with JSON-LD", len(merged) >= len(catalogue), f"{len(merged)} vs {len(catalogue)}")
    check("merged shop card has both layers", merged[0].get("currency") == "GBP" and merged[0].get("isAd") is False)
    check(
        "shop cards carry no seller stars, so none are invented",
        all(c.get("shopReviewCount") is None for c in P.parse_listing_cards(html)),
    )
    check(
        "every catalogue row links back to a servable shop URL",
        all("/uk/shop/" in (c["shopUrl"] or "") for c in merged if c.get("shopName")),
    )
    check(
        "the page currency reaches cards the JSON-LD did not cover",
        all(c.get("currency") == "GBP" for c in merged),
        str({c.get("currency") for c in merged}),
    )
    check("shop id found for foreign-listing filtering", p["shopId"] == "14792900", str(p["shopId"]))
    own = _own_listings(merged, p["shopId"], "PBJewelryGift")
    check("this shop's own grid survives the filter intact", len(own) == len(merged))
    check(
        "a card from another shop is dropped",
        len(_own_listings(merged + [{"listingId": "1", "shopId": "999", "shopName": "Other"}],
                          p["shopId"], "PBJewelryGift")) == len(merged),
    )


def test_product_detail() -> None:
    print("\n-- product detail --")
    d = P.parse_product_detail(
        fixture("listing_detail.html"),
        "https://www.etsy.com/listing/4306368113/birth-flower-ring-925-sterling-silver",
    )
    check("listing id", d["listingId"] == "4306368113")
    check("full description", len(d["description"] or "") > 500, str(len(d["description"] or "")))
    check("taxonomy path", d["categoryPath"] == "Jewelry < Rings < Multi-Stone Rings")
    check("breadcrumbs", len(d["breadcrumbs"] or []) == 3)
    check("price range from the variant span", d["priceMin"] and d["priceMax"] and d["priceMax"] > d["priceMin"])
    check("strikethrough price", d["originalPrice"] == 783582.0, str(d["originalPrice"]))
    check("stock quantity", d["quantityAvailable"] == 431, str(d["quantityAvailable"]))
    check("availability", d["availability"] == "InStock")
    check("images with alt text", len(d["images"] or []) == 12)
    check("variations with options", len(d["variations"] or []) == 2)
    check(
        "highlights are copy, not shadow-DOM CSS",
        d["highlights"] and not any("opacity" in h for h in d["highlights"]),
        str((d["highlights"] or [None])[0])[:60],
    )
    check("shop sales", d["shopTotalSales"] == 59500, str(d["shopTotalSales"]))
    check("shop tenure", d["shopTenure"] == "9 years")
    check("listing badge read when Etsy renders one", d["listingBadge"] == "etsys_pick", str(d["listingBadge"]))
    check("AI review tags", len(d["reviewFeatureTags"] or []) == 7)
    check(
        "seller SEO tags reported absent rather than invented",
        d["sellerTags"] is None,
    )


def test_reviews() -> None:
    print("\n-- reviews --")
    shop_reviews = P.parse_reviews(
        fixture("shop_reviews.html"), source_url="https://www.etsy.com/uk/shop/PBJewelryGift/reviews"
    )
    check("14 reviews per shop page", len(shop_reviews) == 14, f"got {len(shop_reviews)}")
    check("every review has a rating", all(r["rating"] for r in shop_reviews))
    check("every review has a date", all(r["date"] for r in shop_reviews))
    check("every review names its buyer", all(r["buyerName"] for r in shop_reviews))
    check("every review names the item bought", all(r["purchasedListingId"] for r in shop_reviews))
    check("buyer photos found", any(r["photos"] for r in shop_reviews))
    check(
        "photos are buyer uploads, not listing images",
        all("/iap/" in p for r in shop_reviews if r["photos"] for p in r["photos"]),
    )
    check("low ratings not dropped", any(r["rating"] == 1 for r in shop_reviews))

    inline = P.parse_reviews(fixture("listing_detail.html"), source_url="https://www.etsy.com/listing/1/x")
    check("listing page renders a handful inline", len(inline) == 4, f"got {len(inline)}")
    check("inline reviews have text", all(r["text"] for r in inline))

    ld_only = P._reviews_from_json_ld(fixture("listing_detail.html"), source_url="https://www.etsy.com/listing/4306368113/x")
    check("JSON-LD fallback finds reviews too", len(ld_only) >= 4, f"got {len(ld_only)}")
    check("fallback rows are labelled as such", all(r["_source"] == "json-ld" for r in ld_only))
    check(
        "the fallback is not used when the markup has reviews",
        all("_source" not in r for r in inline),
    )

    sentiment = P.parse_review_sentiment(fixture("listing_detail.html"))
    check("sentiment tags", len(sentiment["tags"]) == 7)
    check("sentiment split", sentiment["positiveTagCount"] == 7 and sentiment["negativeTagCount"] == 0)
    check("tags typed by aspect", any(t["type"] for t in sentiment["taggedAspects"]))


def test_number_parsing() -> None:
    print("\n-- localised numbers --")
    check("en thousands", P._num("14,387,687") == 14387687.0)
    check("de thousands", P._num("14.387.687") == 14387687.0)
    check("en decimal", P._num("36.11") == 36.11)
    check("de decimal", P._num("36,11") == 36.11)
    check("mixed separators", P._num("1.234,56") == 1234.56)
    check("numeric input passes through", P._num(431) == 431.0)
    check("abbreviated sales", P._abbrev_to_int("59.5k") == 59500)
    check("abbreviated millions", P._abbrev_to_int("1.2M") == 1200000)


def test_budget() -> None:
    print("\n-- item budget --")
    b = Budget(3)
    check("takes up to the limit", [b.take() for _ in range(5)] == [True, True, True, False, False])
    check("unlimited when zero", all(Budget(0).take() for _ in range(50)))


async def run_live(which: str | None) -> None:
    print("\n-- live (hits Etsy) --")
    client = EtsyClient(request_delay=3.0)
    plans = {
        "search": {
            "mode": "search",
            "startUrls": ["https://www.etsy.com/c/jewelry/rings"],
            "maxPagesPerTarget": 1,
            "maxItems": 5,
        },
        "keyword": {
            "mode": "search",
            "searchKeywords": ["vintage ring"],
            "maxPagesPerTarget": 1,
            "shopsPerKeyword": 1,
            "maxItems": 6,
        },
        "shop": {
            "mode": "shop",
            "shopNames": ["PBJewelryGift"],
            "maxPagesPerTarget": 1,
            "maxItems": 5,
        },
        "reviews": {
            "mode": "reviews",
            "shopNames": ["PBJewelryGift"],
            "maxReviewPages": 1,
            "maxItems": 4,
        },
    }
    try:
        for name, opts in plans.items():
            if which and which != name:
                continue
            opts = {**opts, "locale": normalise_locale("uk")}
            budget = Budget(int(opts.get("maxItems") or 0))
            print(f"\n  == {name} ==")
            count = 0
            async for rec in MODES[opts["mode"]](client, opts, budget):
                count += 1
                body = json.dumps(rec["data"], ensure_ascii=False)
                print(f"    {rec['item_type']:16s} {str(rec['id']):14s} {body[:130]}")
            check(f"live {name} produced records", count > 0, f"got {count}")
    finally:
        client.close()


def main() -> int:
    test_url_handling()
    test_number_parsing()
    test_category_grid()
    test_shop_search()
    test_shop_profile()
    test_product_detail()
    test_reviews()
    test_budget()

    if "--live" in sys.argv:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        asyncio.run(run_live(args[0] if args else None))

    print()
    if failures:
        print(f"{len(failures)} FAILED: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
