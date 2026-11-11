"""Local smoke test against the live site.

Instagram throttles anonymous traffic, so the network portion is
deliberately small and paced. The parsing layer is tested offline against a
saved page where possible.
"""

import asyncio
import json
import sys

from src.client import InstagramClient
from src.constants import SOURCE_API, SOURCE_HTML, SOURCE_META
from src.profile import (
    InvalidInput,
    classify_link,
    enrich,
    from_api,
    from_html,
    from_meta,
    normalise_bio_links,
    parse_count,
    resolve_username,
    unwrap_link,
)

LIVE_USER = "cottonink"

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

    # ---- offline parsing ----------------------------------------------
    print("\n=== username resolution ===")
    for raw, want in [
        ("cottonink", "cottonink"), ("@Nike", "nike"),
        ("https://www.instagram.com/hijup/", "hijup"),
        ("instagram.com/erigostore", "erigostore"),
        ("https://www.instagram.com/nike/?hl=en", "nike"),
    ]:
        failures += not check(f"resolve {raw[:40]}", resolve_username(raw) == want,
                              f"got {resolve_username(raw)}")
    for bad in ("", "https://example.com/x", "has space", "a" * 40):
        try:
            resolve_username(bad)
            failures += not check(f"rejects {bad[:22]!r}", False, "no exception")
        except InvalidInput:
            failures += not check(f"rejects {bad[:22]!r}", True)

    print("\n=== counts + links ===")
    for text, want in (("680K", 680_000), ("7,483", 7483), ("1.2M", 1_200_000), ("150", 150)):
        failures += not check(f"parse {text}", parse_count(text) == want, str(parse_count(text)))
    failures += not check("parse_count None-safe", parse_count(None) is None)

    wrapped = ("https://l.instagram.com/?u=http%3A%2F%2Flinktr.ee%2FCOTTONINK&e=AUB")
    failures += not check("lynx unwrapped", unwrap_link(wrapped) == "http://linktr.ee/COTTONINK",
                          str(unwrap_link(wrapped)))
    failures += not check("plain URL untouched",
                          unwrap_link("https://shopee.co.id/x") == "https://shopee.co.id/x")
    for url, want in (("https://shopee.co.id/shop", "SHOPEE"),
                      ("https://tokopedia.com/x", "TOKOPEDIA"),
                      ("https://wa.me/62812", "WHATSAPP"),
                      ("http://linktr.ee/x", "LINK_AGGREGATOR"),
                      ("https://mystore.com", "OTHER")):
        failures += not check(f"classify {url[:30]}", classify_link(url) == want,
                              str(classify_link(url)))

    links = normalise_bio_links(
        [{"url": "http://linktr.ee/COTTONINK", "title": "Shop Now!", "link_type": "external"},
         {"url": "http://linktr.ee/COTTONINK", "title": "dupe", "link_type": "external"},
         {"lynx_url": wrapped, "title": None, "link_type": "external"}],
        "https://shopee.co.id/cottonink",
    )
    failures += not check("bio links deduped", len(links) == 2, str(len(links)))
    failures += not check("external_url appended", links[-1]["platform"] == "SHOPEE")
    failures += not check("title kept", links[0]["title"] == "Shop Now!")

    print("\n=== enrichment ===")
    rec = enrich({
        "followers": 1000, "postCount": 100,
        "bioLinks": [{"url": "https://shopee.co.id/x", "platform": "SHOPEE"},
                     {"url": "https://wa.me/62", "platform": "WHATSAPP"}],
        "recentPosts": [{"likes": 100, "comments": 20}, {"likes": 80, "comments": 0}],
    })
    failures += not check("marketplaces detected", rec["marketplaces"] == ["SHOPEE"])
    failures += not check("whatsapp detected", rec["hasWhatsApp"] is True)
    failures += not check("sellsOnMarketplace", rec["sellsOnMarketplace"] is True)
    failures += not check("avg engagement", rec["avgEngagementPerPost"] == 100.0,
                          str(rec["avgEngagementPerPost"]))
    failures += not check("engagement rate %", rec["engagementRatePercent"] == 10.0,
                          str(rec["engagementRatePercent"]))
    empty = enrich({"followers": None, "postCount": None, "bioLinks": [], "recentPosts": []})
    failures += not check("no links -> no crash",
                          empty["marketplaces"] == [] and empty["primaryShopLink"] is None)
    failures += not check("no posts -> null engagement",
                          empty["avgEngagementPerPost"] is None)

    # ---- live ----------------------------------------------------------
    print("\n=== live profile (single account, paced) ===")
    client = InstagramClient()
    try:
        page_html = await client.warm_profile(LIVE_USER)
        failures += not check("profile page loaded", len(page_html) > 100_000, f"{len(page_html)}B")

        html_rec = from_html(LIVE_USER, page_html)
        failures += not check("S2 HTML strategy parses", html_rec is not None)
        if html_rec:
            failures += not check("S2 source tag", html_rec["_source"] == SOURCE_HTML)
            failures += not check("S2 has followers",
                                  isinstance(html_rec.get("followers"), int),
                                  str(html_rec.get("followers")))
            failures += not check("S2 has bio links", bool(html_rec.get("bioLinks")))

        meta_rec = from_meta(LIVE_USER, page_html)
        failures += not check("S3 meta strategy parses", meta_rec is not None)
        if meta_rec:
            failures += not check("S3 source tag", meta_rec["_source"] == SOURCE_META)
            failures += not check("S3 warns counts are rounded",
                                  meta_rec.get("_warning") == "counts_are_rounded_og_values")
            failures += not check("S3 has followers",
                                  isinstance(meta_rec.get("followers"), int),
                                  str(meta_rec.get("followers")))

        user = await client.profile_api(LIVE_USER)
        if user:
            api_rec = enrich(from_api(LIVE_USER, user, 12))
            failures += not check("S1 source tag", api_rec["_source"] == SOURCE_API)
            failures += not check("S1 has followers", isinstance(api_rec.get("followers"), int))
            failures += not check("S1 has posts", bool(api_rec.get("recentPosts")))
            failures += not check_schema([api_rec], schema)
            print("  PROFILE:", json.dumps({k: api_rec.get(k) for k in (
                "username", "fullName", "followers", "postCount", "isBusinessAccount",
                "businessCity", "marketplaces", "primaryShopLink", "engagementRatePercent",
            )}, ensure_ascii=False)[:420])
            posts = api_rec.get("recentPosts") or []
            if posts:
                print("  POST   :", json.dumps({k: posts[0].get(k) for k in (
                    "shortcode", "likes", "comments", "mediaType")}, ensure_ascii=False)[:200])
        else:
            print("  NOTE: API returned no user this run (known intermittent) -- "
                  "HTML fallback is what covers this.")
            failures += not check_schema([enrich(html_rec)], schema) if html_rec else 0
    finally:
        await client.close()

    print(f"\n{'=' * 46}\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
