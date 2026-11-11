"""Local smoke test against the live site."""

import asyncio
import json
import sys

from src.client import AmazonClient
from src.constants import DOMAINS, MOVE_DROPPED, MOVE_FALLING, MOVE_NEW, MOVE_RISING, MOVE_UNCHANGED
from src.ranking import (
    InvalidInput,
    build_records,
    build_url,
    detect_movement,
    dropped_out_records,
    pages_for,
    parse_faceouts,
    parse_recs_list,
    resolve_category,
    snapshot_key,
)

FULL = "--full" in sys.argv
CATEGORY = "electronics"

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

    # ---- offline -------------------------------------------------------
    print("\n=== category resolution ===")
    plain = resolve_category("electronics")
    failures += not check("slug", plain["category"] == "electronics" and not plain["explicit"])
    node = resolve_category("electronics/172541")
    failures += not check("node path", node["category"] == "electronics/172541",
                          node["category"])
    url = resolve_category("https://www.amazon.co.uk/Best-Sellers/zgbs/kitchen")
    failures += not check(
        "URL sets domain + list + category",
        url["domain"] == "co.uk" and url["listType"] == "bestsellers"
        and url["category"] == "kitchen" and url["explicit"],
        json.dumps({k: url[k] for k in ("domain", "listType", "category")}),
    )
    ms = resolve_category("https://www.amazon.com/gp/movers-and-shakers/toys-and-games")
    failures += not check("M&S URL detected", ms["listType"] == "movers-and-shakers",
                          ms["listType"])
    for bad in ("", "https://example.com/x", "https://www.amazon.com/dp/B01",
                "has space"):
        try:
            resolve_category(bad)
            failures += not check(f"rejects {bad[:26]!r}", False, "no exception")
        except InvalidInput:
            failures += not check(f"rejects {bad[:26]!r}", True)

    print("\n=== URL building + paging ===")
    failures += not check(
        "page 1 url",
        build_url("com", "bestsellers", "electronics", 1)
        == "https://www.amazon.com/Best-Sellers/zgbs/electronics",
    )
    failures += not check(
        "page 2 url carries pg",
        build_url("com", "bestsellers", "electronics", 2).endswith("?pg=2"),
    )
    failures += not check("co.uk base", build_url("co.uk", "bestsellers", "kitchen", 1)
                          .startswith(DOMAINS["co.uk"]))
    failures += not check("50 ranks -> 1 page", pages_for(50) == 1)
    failures += not check("100 ranks -> 2 pages", pages_for(100) == 2)
    failures += not check("capped at 2 pages", pages_for(500) == 2)

    print("\n=== movement detection ===")
    base = {"asin": "B01", "rank": 10}
    r = detect_movement(dict(base), None)
    failures += not check("no history -> NEW_ENTRY",
                          r["movementType"] == MOVE_NEW and r["isNewEntry"])
    r = detect_movement(dict(base), 25)
    failures += not check("climbed -> RISING", r["movementType"] == MOVE_RISING)
    failures += not check("rankChange positive when climbing", r["rankChange"] == 15,
                          str(r["rankChange"]))
    failures += not check("significant", r["isSignificantMove"] is True)
    r = detect_movement(dict(base), 3)
    failures += not check("slipped -> FALLING", r["movementType"] == MOVE_FALLING)
    failures += not check("rankChange negative when slipping", r["rankChange"] == -7)
    r = detect_movement(dict(base), 10)
    failures += not check("same rank -> UNCHANGED", r["movementType"] == MOVE_UNCHANGED)
    failures += not check("zero move not significant", r["isSignificantMove"] is False)
    r = detect_movement(dict(base), 12)
    failures += not check("2-rank wobble not significant", r["isSignificantMove"] is False)

    ctx = {"label": "com/bestsellers/electronics", "category": "electronics",
           "listType": "bestsellers", "domain": "com"}
    dropped = dropped_out_records({"B0AAAAAAAA": 5, "B0BBBBBBBB": 9}, {"B0AAAAAAAA"},
                                  ctx, DOMAINS["com"])
    failures += not check("drop-out detected", len(dropped) == 1, str(len(dropped)))
    failures += not check("drop-out shape",
                          dropped[0]["movementType"] == MOVE_DROPPED
                          and dropped[0]["previousRank"] == 9
                          and dropped[0]["rank"] is None)
    failures += not check("snapshot key stable",
                          snapshot_key(ctx) == "com|bestsellers|electronics",
                          snapshot_key(ctx))

    # ---- live -----------------------------------------------------------
    print("\n=== live best sellers ===")
    client = AmazonClient()
    try:
        base_url = DOMAINS["com"]
        page1 = await client.get_page(build_url("com", "bestsellers", CATEGORY, 1))
        spine = parse_recs_list(page1)
        details = parse_faceouts(page1, base_url)
        print(f"  page1: recs-list={len(spine)} rendered tiles={len(details)}")
        failures += not check("recs-list has 50", len(spine) == 50, str(len(spine)))
        failures += not check("ranks 1..50",
                              [e["rank"] for e in spine[:3]] == [1, 2, 3],
                              str([e["rank"] for e in spine[:3]]))
        failures += not check("tiles rendered", len(details) >= 25, str(len(details)))

        records = build_records(page1, base_url, ctx)
        failures += not check("records built", len(records) == 50)
        detailed = [r for r in records if r["hasDetails"]]
        failures += not check("hasDetails flags the split",
                              0 < len(detailed) < len(records),
                              f"{len(detailed)}/{len(records)}")
        failures += not check("every record has asin + url",
                              all(r["asin"] and r["productUrl"] for r in records))
        priced = [r for r in detailed if r.get("price")]
        rated = [r for r in detailed if r.get("rating")]
        failures += not check("detailed rows carry price",
                              len(priced) >= len(detailed) * 0.8,
                              f"{len(priced)}/{len(detailed)}")
        failures += not check("detailed rows carry rating",
                              len(rated) >= len(detailed) * 0.8,
                              f"{len(rated)}/{len(detailed)}")

        for record in records:
            detect_movement(record, None)
        failures += not check_schema(records, schema)
        top = records[0]
        print("  TOP1:", json.dumps({k: top.get(k) for k in (
            "rank", "asin", "title", "price", "rating", "reviewCount", "hasDetails")},
            ensure_ascii=False)[:280])

        print("\n=== page 2 gives ranks 51-100 ===")
        page2 = await client.get_page(build_url("com", "bestsellers", CATEGORY, 2))
        spine2 = parse_recs_list(page2)
        failures += not check("page2 recs-list has 50", len(spine2) == 50, str(len(spine2)))
        failures += not check("page2 starts at 51",
                              spine2[0]["rank"] == 51, str(spine2[0]["rank"]))
        combined = {e["asin"] for e in spine} | {e["asin"] for e in spine2}
        failures += not check("100 unique ASINs across both pages",
                              len(combined) == 100, str(len(combined)))

        print("\n=== movement across two real snapshots ===")
        previous = {e["asin"]: e["rank"] for e in spine}
        # Shift one product's stored rank to simulate a climb.
        shifted = dict(previous)
        target_asin = spine[10]["asin"]
        shifted[target_asin] = spine[10]["rank"] + 20
        moved = [detect_movement(dict(r), shifted.get(r["asin"])) for r in records]
        climber = next(r for r in moved if r["asin"] == target_asin)
        failures += not check("simulated climb detected",
                              climber["movementType"] == MOVE_RISING
                              and climber["rankChange"] == 20,
                              f"{climber['movementType']} {climber['rankChange']}")
        unchanged = [r for r in moved if r["movementType"] == MOVE_UNCHANGED]
        failures += not check("rest unchanged", len(unchanged) == len(moved) - 1,
                              f"{len(unchanged)}/{len(moved)}")
    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
