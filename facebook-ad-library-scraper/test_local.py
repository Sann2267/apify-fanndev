"""Offline + live checks for the Ad Library actor, runnable without Apify.

    python test_local.py          # live: one keyword search, one advertiser search
    python test_local.py --offline  # parser only, no network

The live path is the one that matters: it proves the 403 challenge is solved and
that pagination gets past the 30 server-rendered ads.
"""

from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, ".")

from src.fbcore import FacebookSession, harvest_preloaders, harvest_tokens  # noqa: E402
from src.main import build_url, collect, page_id_from, read_queries  # noqa: E402
from src.parser import parse_ad, parse_page, summarise  # noqa: E402


class Log:
    def info(self, message):
        print(f"  [info] {message}")

    def warning(self, message):
        print(f"  [warn] {message}")


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))
    return bool(condition)


def offline_checks() -> bool:
    ok = True
    ok &= check("page id from numeric", page_id_from("89516513179") == "89516513179")
    ok &= check(
        "page id from Ad Library URL",
        page_id_from("https://www.facebook.com/ads/library/?view_all_page_id=123456789")
        == "123456789",
    )
    ok &= check("vanity slug rejected", page_id_from("https://facebook.com/nike") is None)

    url = build_url(
        {
            "activeStatus": "active",
            "adType": "all",
            "country": "US",
            "mediaType": "all",
            "searchType": "keyword_unordered",
            "term": "running shoes",
            "pageId": None,
            "publisherPlatforms": ["FACEBOOK"],
            "contentLanguages": [],
        }
    )
    ok &= check("URL carries the query", "q=running+shoes" in url and "country=US" in url, url[:90])

    queries = read_queries({"searchTerms": ["a", "b"], "countries": ["US", "GB"]})
    ok &= check("2 terms x 2 countries = 4 searches", len(queries) == 4)

    node = {
        "ad_archive_id": "1",
        "is_active": True,
        "page_id": "9",
        "start_date": 1_785_740_400,
        "end_date": 1_789_801_200,
        "publisher_platform": ["FACEBOOK"],
        "snapshot": {
            "page_name": "Demo",
            "body": {"text": "hello world"},
            "cards": [{"title": "card", "link_url": "x", "resized_image_url": "http://i/1.jpg"}],
            "images": [],
            "videos": [],
        },
    }
    ad = parse_ad(node)
    ok &= check("running days computed", ad["runningDays"] == 47, str(ad["runningDays"]))
    ok &= check("carousel media picked up", ad["imageCount"] == 1)
    ok &= check("word count", ad["adTextWordCount"] == 2)
    ok &= check("summary shape", summarise([ad])["adsCollected"] == 1)
    return ok


async def live_checks() -> bool:
    ok = True
    log = Log()
    filters = {"onlyActive": False, "onlyWithVideo": False, "minRunningDays": None,
               "adTextContains": None}

    async with FacebookSession(log=log) as session:
        query = {
            "activeStatus": "active", "adType": "all", "country": "US", "mediaType": "all",
            "searchType": "keyword_unordered", "term": "running shoes", "pageId": None,
            "publisherPlatforms": [], "contentLanguages": [],
            "startDateMin": None, "startDateMax": None, "label": "keyword:running shoes",
        }

        print("\n-- challenge + server-rendered page --")
        html = await session.get_html(build_url(query))
        ok &= check("page fetched", len(html) > 400_000, f"{len(html)/1024:.0f} KB")
        ok &= check("LSD token present", bool(harvest_tokens(html).get("lsd")))
        ok &= check("preloader variables present", bool(harvest_preloaders(html)))
        rendered = parse_page(html)
        ok &= check("ads parsed", len(rendered["ads"]) >= 10, str(len(rendered["ads"])))
        ok &= check("total count present", isinstance(rendered["totalMatchingAds"], int),
                    str(rendered["totalMatchingAds"]))
        ok &= check("cursor present", bool(rendered["cursor"]))
        sample = rendered["ads"][0]
        ok &= check("advertiser named", bool(sample["pageName"]), str(sample["pageName"]))
        ok &= check("has a creative or copy",
                    bool(sample["adText"] or sample["imageCount"] or sample["videoCount"]))

        print("\n-- pagination past the rendered 30 --")
        ads, meta = await collect(session, query, max_ads=70, filters=filters)
        ok &= check("paginated past 30", len(ads) > 30, f"{len(ads)} ads, "
                                                        f"{meta['pagesFetched']} page(s)")

        print("\n-- advertiser search --")
        page_query = {**query, "term": None, "pageId": "89516513179",
                      "label": "page:89516513179"}
        page_ads, _ = await collect(session, page_query, max_ads=30, filters=filters)
        ok &= check("advertiser search returns ads", len(page_ads) > 0, str(len(page_ads)))
        if page_ads:
            print("   ", json.dumps({k: page_ads[0][k] for k in
                                     ("pageName", "ctaText", "displayFormat", "runningDays")},
                                    ensure_ascii=False))
    return ok


def main() -> int:
    print("== offline ==")
    ok = offline_checks()
    if "--offline" not in sys.argv:
        print("\n== live ==")
        ok = asyncio.run(live_checks()) and ok
    print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
