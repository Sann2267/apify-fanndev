"""Local smoke test against live Amazon product pages."""

import asyncio
import base64
import json

from src.client import AmazonClient, Blocked
from src.constants import (
    RECORD_ASPECT,
    RECORD_PRODUCT,
    TLS_PROFILE_LADDER,
    VERIFIED_MARKETPLACES,
)
from src.insights import (
    InvalidInput,
    aspect_records,
    clean_asin,
    extract_aspects,
    extract_summary,
    is_blocked,
    looks_reduced,
    parse_insights,
    product_url,
)

ASINS = ["B00XIKPUK4", "B087F16GKW"]

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
    failures += not check("extracted from URL",
                          clean_asin("https://www.amazon.com/dp/B00XIKPUK4?th=1") == "B00XIKPUK4")
    for bad in ("", "TOOLONG12345", "SHORT"):
        try:
            clean_asin(bad)
            failures += not check(f"rejects {bad[:14]!r}", False, "no exception")
        except InvalidInput:
            failures += not check(f"rejects {bad[:14]!r}", True)

    print("\n=== aspect parsing ===")
    sample = (
        '<button aria-label="Positive aspect, quality, 2,185 mentions"></button>'
        '<button aria-label="Mixed aspect, mixability, 847 mentions"></button>'
        '<button aria-label="Negative aspect, texture, 389 mentions"></button>'
    )
    aspects = extract_aspects(sample)
    failures += not check("three aspects parsed", len(aspects) == 3, str(len(aspects)))
    failures += not check("thousands separator handled",
                          aspects[0]["mentions"] == 2185, str(aspects[0]["mentions"]))
    failures += not check("sentiments uppercased",
                          [a["sentiment"] for a in aspects] == ["POSITIVE", "MIXED", "NEGATIVE"])
    failures += not check("singular 'mention' also matches",
                          len(extract_aspects(
                              '<i aria-label="Negative aspect, smell, 1 mention"></i>')) == 1)

    # The click-tracking id is the fallback for localized pages, but it must
    # not duplicate an aspect the aria-label already provided.
    both = sample + '"cr-product-insights-detail-page_button_0_POSITIVE_quality"'
    failures += not check("csa id does not duplicate an aria aspect",
                          len(extract_aspects(both)) == 3, str(len(extract_aspects(both))))
    csa_only = '"cr-product-insights-detail-page_button_5_NEGATIVE_battery life"'
    fallback = extract_aspects(csa_only)
    failures += not check("csa fallback recovers aspect", len(fallback) == 1)
    if fallback:
        # Absent is not zero: a missing count must stay null or every
        # localized row would look like an aspect nobody mentioned.
        failures += not check("csa fallback leaves mentions null",
                              fallback[0]["mentions"] is None, str(fallback[0]["mentions"]))
        failures += not check("csa fallback keeps sentiment",
                              fallback[0]["sentiment"] == "NEGATIVE")
    failures += not check("no aspects on empty page", extract_aspects("<html></html>") == [])

    print("\n=== positive/negative split and per-aspect summary ===")
    # The payload the widget ships; `sentimentMentions` is the POSITIVE count
    # even on a negative aspect, which is the one way to get this wrong.
    payload = base64.b64encode(json.dumps({
        "k-component": "MainView-x",
        "k-data": {"aspectsFlattened": [
            {"label": "writing quality", "sentiment": "positive", "mentions": 634,
             "sentimentMentions": 617, "summary": "Customers praise the writing quality."},
            {"label": "texture", "sentiment": "negative", "mentions": 392,
             "sentimentMentions": 91, "summary": "Customers dislike the texture."},
        ]},
    }).encode()).decode()
    split = extract_aspects(f"<!-- k-injected k+b64 {payload} -->")
    by_name = {a["aspect"]: a for a in split}
    failures += not check("payload alone yields both aspects", len(split) == 2, str(len(split)))
    if "writing quality" in by_name:
        row = by_name["writing quality"]
        failures += not check("positive from sentimentMentions", row["positive"] == 617,
                              str(row["positive"]))
        failures += not check("negative is mentions - positive", row["negative"] == 17,
                              str(row["negative"]))
        failures += not check("per-aspect summary carried",
                              row["aspectSummary"] == "Customers praise the writing quality.")
    if "texture" in by_name:
        # 392 - 91 = 301 negative. Reading sentimentMentions as "mentions
        # matching the sentiment" would give 91 negative / 301 positive.
        row = by_name["texture"]
        failures += not check("negative aspect not inverted",
                              (row["positive"], row["negative"]) == (91, 301), str(row))

    # The screen-reader line must stand in when the payload is missing.
    aria_only = ('<button aria-label="Positive aspect, writing quality, 634 mentions"></button>'
                 '<span>634 customers mention writing quality, 617 positive, 17 negative</span>')
    recovered = extract_aspects(aria_only)
    failures += not check("split recovered from screen-reader line",
                          recovered and (recovered[0]["positive"], recovered[0]["negative"])
                          == (617, 17), str(recovered))
    failures += not check("no summary without the payload",
                          recovered and recovered[0]["aspectSummary"] is None)
    # Absent is not zero, here too.
    csa_split = extract_aspects('"cr-product-insights-detail-page_button_5_NEGATIVE_battery life"')
    failures += not check("unknown split stays null",
                          csa_split and csa_split[0]["positive"] is None
                          and csa_split[0]["negative"] is None)

    print("\n=== AI summary decoding ===")
    payload = base64.b64encode(json.dumps({
        "k-component": "FragmentTexts-x",
        "k-data": {"fragments": [{"inertText": "Customers love the taste."}]},
    }).encode()).decode()
    failures += not check("summary decoded from base64 blob",
                          extract_summary(f"<!-- k-injected k+b64 {payload} -->")
                          == "Customers love the taste.")
    failures += not check("no summary when absent", extract_summary("<html></html>") is None)
    failures += not check("corrupt blob does not raise",
                          extract_summary("k-injected k+b64 " + "!" * 100) is None)

    print("\n=== reduced-page detection ===")
    # Not a bot wall: full body, clean parse, widget simply absent. Only the
    # review count says whether that is credible.
    full = {"hasInsights": True, "reviewCount": 149157}
    reduced = {"hasInsights": False, "reviewCount": 149157}
    thin = {"hasInsights": False, "reviewCount": 7}
    unrated = {"hasInsights": False, "reviewCount": None}
    failures += not check("page with insights is never retried", not looks_reduced(full))
    failures += not check("no widget + 149k ratings is a reduced page",
                          looks_reduced(reduced))
    failures += not check("no widget + 7 ratings is the truth", not looks_reduced(thin))
    failures += not check("no widget + no review count is the truth",
                          not looks_reduced(unrated))
    failures += not check("floor is inclusive",
                          looks_reduced({"hasInsights": False, "reviewCount": 100})
                          and not looks_reduced({"hasInsights": False, "reviewCount": 99}))

    print("\n=== block detection ===")
    failures += not check("short body is blocked", is_blocked("x" * 5000))
    failures += not check("bot wall detected",
                          is_blocked("Click the button below to continue shopping" + "x" * 400_000))
    failures += not check("real page not blocked", not is_blocked("y" * 400_000))

    print("\n=== ladder guard ===")
    failures += not check(
        "ladder holds only /dp/-verified profiles",
        set(TLS_PROFILE_LADDER) == {"chrome131", "chrome133a", "chrome150", "chrome136"},
        str(TLS_PROFILE_LADDER),
    )
    failures += not check("verified marketplaces recorded",
                          set(VERIFIED_MARKETPLACES) == {"com", "ca"})

    # ---- live -----------------------------------------------------------
    print("\n=== live insight extraction ===")
    client = AmazonClient(marketplace="com")
    all_rows = []
    try:
        for asin in ASINS:
            try:
                body = await client.get_product(product_url("com", asin))
            except Blocked as exc:
                failures += not check(f"{asin} fetched", False, str(exc))
                continue
            product = parse_insights(body, asin, "com")
            # Mirror what the actor now does: a clean page with no widget is
            # the reduced variant, which this IP gets perhaps one run in
            # three. Without a proxy there is no exit to rotate, so just ask
            # again before calling it a failure.
            for _ in range(2):
                if not looks_reduced(product):
                    break
                print(f"    {asin}: reduced page ({product['reviewCount']} ratings, "
                      f"no widget) -- refetching")
                await asyncio.sleep(3)
                body = await client.get_product(product_url("com", asin))
                product = parse_insights(body, asin, "com")
            rows = aspect_records(product)
            all_rows.extend([product] + rows)

            print(f"    {asin} | {(product['title'] or '?')[:46]}")
            print(f"      rating={product['rating']} reviews={product['reviewCount']} "
                  f"aspects={product['aspectCount']} gaps={product['gapAspectCount']}")
            print(f"      gaps: {product['contentGaps']}")
            for a in (product["aspects"] or [])[:3]:
                print(f"      - {a['aspect']}: {a['sentiment']} {a['mentions']} "
                      f"({a['positive']}+/{a['negative']}-) {(a['aspectSummary'] or '')[:70]}")
            print(f"      summary: {(product['aiSummary'] or '')[:110]}...")

            failures += not check(f"{asin}: insights served", product["hasInsights"])
            failures += not check(f"{asin}: not flagged as a reduced page",
                                  not looks_reduced(product))
            failures += not check(f"{asin}: aspects found", bool(product["aspects"]))
            failures += not check(f"{asin}: AI summary found", bool(product["aiSummary"]))
            failures += not check(f"{asin}: title found", bool(product["title"]))
            if product["aspects"]:
                sentiments = {a["sentiment"] for a in product["aspects"]}
                failures += not check(
                    f"{asin}: sentiments are the known set",
                    sentiments <= {"POSITIVE", "MIXED", "NEGATIVE"}, str(sentiments))
                failures += not check(
                    f"{asin}: no duplicate aspects",
                    len({a["aspect"].lower() for a in product["aspects"]})
                    == len(product["aspects"]))
                failures += not check(
                    f"{asin}: counts are positive ints",
                    all(a["mentions"] is None or a["mentions"] > 0
                        for a in product["aspects"]))
                split = [a for a in product["aspects"]
                         if a["positive"] is not None and a["negative"] is not None]
                failures += not check(
                    f"{asin}: split published for every aspect",
                    len(split) == len(product["aspects"]),
                    f"{len(split)}/{len(product['aspects'])}")
                failures += not check(
                    f"{asin}: positive + negative == mentions",
                    all(a["positive"] + a["negative"] == a["mentions"] for a in split),
                    str([(a["aspect"], a["positive"], a["negative"], a["mentions"])
                         for a in split
                         if a["positive"] + a["negative"] != a["mentions"]][:2]))
                failures += not check(
                    f"{asin}: negative aspects skew negative",
                    all(a["negative"] > a["positive"] for a in split
                        if a["sentiment"] == "NEGATIVE"),
                    str([(a["aspect"], a["positive"], a["negative"]) for a in split
                         if a["sentiment"] == "NEGATIVE"]))
                summarised = [a for a in product["aspects"] if a["aspectSummary"]]
                failures += not check(
                    f"{asin}: per-aspect summary on every aspect",
                    len(summarised) == len(product["aspects"]),
                    f"{len(summarised)}/{len(product['aspects'])}")
                failures += not check(
                    f"{asin}: aspect summaries differ from aiSummary",
                    all(a["aspectSummary"] != product["aiSummary"] for a in summarised))
            await asyncio.sleep(2)

        aspect_rows = [r for r in all_rows if r["recordType"] == RECORD_ASPECT]
        product_rows = [r for r in all_rows if r["recordType"] == RECORD_PRODUCT]
        failures += not check("product rows emitted", len(product_rows) == len(ASINS))
        failures += not check("aspect rows emitted", len(aspect_rows) >= 8, str(len(aspect_rows)))

        if aspect_rows:
            # Rank must follow mentions, or "top complaint" ordering is a lie.
            for product in product_rows:
                rows = [r for r in aspect_rows if r["asin"] == product["asin"]]
                counted = [r for r in rows if r["mentions"] is not None]
                failures += not check(
                    f"{product['asin']}: rank ordered by mentions",
                    all(counted[i]["mentions"] >= counted[i + 1]["mentions"]
                        for i in range(len(counted) - 1)),
                    str([r["mentions"] for r in counted]))
                failures += not check(
                    f"{product['asin']}: ranks are 1..n",
                    [r["mentionRank"] for r in rows] == list(range(1, len(rows) + 1)))
            failures += not check(
                "gap flag matches sentiment",
                all(r["isContentGap"] == (r["sentiment"] in ("MIXED", "NEGATIVE"))
                    for r in aspect_rows))
            shares = [r["mentionSharePercent"] for r in aspect_rows
                      if r["mentionSharePercent"] is not None]
            failures += not check("shares within 0-100",
                                  all(0 < s <= 100 for s in shares), str(shares[:4]))
            print("  ASPECT:", json.dumps({k: aspect_rows[0].get(k) for k in (
                "asin", "aspect", "sentiment", "mentions", "positive", "negative",
                "mentionRank", "mentionSharePercent", "isContentGap",
                "aspectSummary")}, ensure_ascii=False))

        failures += not check_schema(all_rows, schema)
    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
