"""Offline + live checks for the business contact extractor.

    python test_local.py            # live: two known pages, plus Ad Library discovery
    python test_local.py --offline  # parser only, no network
"""

from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, ".")

from src.fbcore import FacebookSession  # noqa: E402
from src.main import discover, extract_one, read_direct_pages  # noqa: E402
from src.parser import (  # noqa: E402
    flatten_contact,
    matches_filters,
    page_ref,
    parse_about,
    summarise,
)


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
    ok &= check("slug from URL",
                page_ref("https://www.facebook.com/BarbutoNYC/about") == "BarbutoNYC")
    ok &= check("reserved path rejected", page_ref("https://facebook.com/marketplace/x") is None)
    ok &= check("pages read from both inputs",
                [t["slug"] for t in read_direct_pages(
                    {"pages": ["a"], "startUrls": [{"url": "facebook.com/b"}]})] == ["a", "b"])

    html = (
        '<meta property="og:title" content="Barbuto | Facebook">'
        '<script type="application/json">'
        + json.dumps({
            "s": {
                "field_section_type": "about_contact_info",
                "id": "cHJvZmlsZV9maWVsZF9zZWN0aW9uOjMxMjQyNDI1OTg1OTpjYXRlZ29yeQ==",
                "profile_fields": {"nodes": [
                    {"field_type": "profile_email", "title": {"text": "info@barbutonyc.com"}},
                    {"field_type": "profile_phone", "title": {"text": "+1 212-924-9700"}},
                    {"field_type": "website", "title": {"text": "http://www.barbutonyc.com/"},
                     "link_url": "https://l.facebook.com/l.php?u=http%3A%2F%2Fwww.barbutonyc.com%2F&h=AT1"},
                    {"field_type": "address",
                     "title": {"text": "113 horatio street, New York, NY, United States, 10014"}},
                    {"field_type": "business_hours", "title": {"text": "Closed now"}},
                    {"field_type": "business_price", "title": {"text": "Price range · ££"}},
                    {"field_type": "business_services",
                     "title": {"text": "Delivery · Takeaway"}},
                    {"field_type": "category", "title": {"text": "Italian restaurant"}},
                    {"field_type": "ratings", "title": {"text": "94% recommend (1,236 reviews)"}},
                ]},
            }
        })
        + "</script>"
    )
    record = flatten_contact(parse_about(html))
    ok &= check("page name strips the Facebook suffix", record["pageName"] == "Barbuto",
                str(record["pageName"]))
    ok &= check("email", record["email"] == "info@barbutonyc.com")
    ok &= check("phone", record["phone"] == "+1 212-924-9700")
    ok &= check("website unwrapped from l.facebook.com",
                record["website"] == "http://www.barbutonyc.com/", str(record["website"]))
    ok &= check("address", record["address"].startswith("113 horatio"))
    ok &= check("services split", record["services"] == ["Delivery", "Takeaway"],
                str(record["services"]))
    ok &= check("rating parsed",
                (record["recommendPercent"], record["reviewCount"]) == (94.0, 1236),
                str((record["recommendPercent"], record["reviewCount"])))
    ok &= check("page id decoded from the section id", record["pageId"] == "312424259859",
                str(record["pageId"]))
    ok &= check("contact score counts the four channels", record["contactScore"] == 4)

    ok &= check("requireEmail drops a page without one",
                matches_filters({"hasEmail": False}, {"requireEmail": True}) is False)
    ok &= check("unknown follower count fails a minimum",
                matches_filters({"followers": None, "contactScore": 1},
                                {"minFollowers": 10}) is False)
    ok &= check("summary", summarise([record])["withEmail"] == 1)
    return ok


async def live_checks() -> bool:
    ok = True
    import asyncio as _asyncio

    async with FacebookSession(log=Log()) as session:
        semaphore = _asyncio.Semaphore(2)

        print("\n-- a local business with full contact details --")
        record = await extract_one(session, {"slug": "BarbutoNYC", "discoveredVia": "input"},
                                   True, semaphore)
        ok &= check("record returned", record.get("recordType") != "ERROR",
                    str(record.get("_errorDetail", ""))[:60])
        if record.get("recordType") != "ERROR":
            print("    ", json.dumps({k: record.get(k) for k in
                                      ("pageName", "primaryCategory", "email", "phone",
                                       "website", "hoursLabel", "priceRange", "contactScore",
                                       "pageCreationDate", "isRunningAds")},
                                     ensure_ascii=False))
            ok &= check("email found", bool(record.get("email")))
            ok &= check("phone found", bool(record.get("phone")))
            ok &= check("transparency tab read", record.get("pageCreationDate") is not None,
                        str(record.get("pageCreationDate")))

        print("\n-- a slug that does not exist --")
        missing = await extract_one(session, {"slug": "zz-not-a-real-page-98765",
                                              "discoveredVia": "input"}, False, semaphore)
        ok &= check("missing page reported as an error row",
                    missing.get("_error") == "page_not_found", str(missing.get("_error")))

        print("\n-- keyword discovery through the Ad Library --")
        found = await discover(session, ["dentist"], ["US"], {})
        ok &= check("discovery returns pages", len(found) >= 5, f"{len(found)} page(s)")
        if found:
            print("    sample:", ", ".join(
                f"{f['slug']} ({f.get('advertiserName')})" for f in found[:4]))
            ok &= check("discovery rows carry their query",
                        all(f["discoveryQuery"] for f in found))
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
