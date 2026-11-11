"""Run the validator against live Facebook pages without an Apify runtime.

Asserts against the fixtures in CRAWLING_METHOD.md, so a Facebook-side change
shows up as a failing expectation rather than as a quietly emptier dataset.

    python test_local.py
"""

from __future__ import annotations

import asyncio
import json
import sys

from src.client import FacebookClient
from src.constants import TIER_FULL, TIER_HOLLOW, TIER_REDUCED, classify_tier
from src.main import build_record, normalise_slug
from src.parser import parse_count, unwrap_link
from src.verdict import brand_match, summarise

# (slug, expectedBrand, expected tier, expected brandMatch, must have followers)
FIXTURES = [
    ("nike", "Nike", TIER_FULL, "EXACT", True),
    ("tokopedia", "Tokopedia", TIER_FULL, "STRONG", True),
    ("kopikenangan.id", "Kopi Kenangan", TIER_FULL, "STRONG", True),
    ("bukalapak", "Bukalapak", TIER_REDUCED, "MISMATCH", True),
    ("zzqq-not-a-real-page-9876543", "Ghost Brand", TIER_HOLLOW, "UNKNOWN", False),
]


def test_pure_functions() -> int:
    """Everything that needs no network."""
    failures = 0

    def check(label: str, got, want) -> None:
        nonlocal failures
        if got != want:
            print(f"  FAIL {label}: got {got!r}, want {want!r}")
            failures += 1

    check("parse_count 39M", parse_count("39M followers"), 39_000_000)
    check("parse_count 28K", parse_count("28K followers"), 28_000)
    check("parse_count exact", parse_count("124 followers"), 124)
    check("parse_count commas", parse_count("1,234 followers"), 1_234)
    check("parse_count junk", parse_count("followers"), None)
    check("parse_count none", parse_count(None), None)

    check(
        "unwrap l.php",
        unwrap_link("https://l.facebook.com/l.php?u=http%3A%2F%2Fnike.com%2F&h=AUA"),
        "http://nike.com/",
    )
    check("unwrap plain", unwrap_link("https://nike.com/"), "https://nike.com/")
    check("unwrap none", unwrap_link(None), None)

    check("slug from url", normalise_slug("https://www.facebook.com/nike/"), "nike")
    check("slug from bare", normalise_slug("nike"), "nike")
    check("slug from pg", normalise_slug("facebook.com/pg/nike"), "nike")
    check("slug query stripped", normalise_slug("facebook.com/nike?ref=x"), "nike")
    check("slug reserved", normalise_slug("facebook.com/profile.php"), None)
    check("slug empty", normalise_slug("   "), None)

    check("brand exact", brand_match("Nike", "Nike")["brandMatch"], "EXACT")
    check("brand regional", brand_match("Kopi Kenangan", "Kopi Kenangan | South Jakarta")["brandMatch"], "STRONG")
    check("brand mismatch", brand_match("Bukalapak", "Eoddata beeip.com")["brandMatch"], "MISMATCH")
    # Accents are stripped during normalisation, so these compare as identical.
    check("brand accents", brand_match("Nestle", "Nestlé")["brandMatch"], "EXACT")
    check("brand no expectation", brand_match(None, "Nike")["brandMatch"], "UNKNOWN")
    # "Official" carries no brand meaning, so its absence must not lower the score.
    check("brand noise token", brand_match("Nike Official", "Nike")["brandMatch"], "STRONG")

    print(f"pure functions: {'OK' if not failures else str(failures) + ' FAILURE(S)'}")
    return failures


async def test_live() -> int:
    """Fetch the fixtures and check the verdicts still hold."""
    failures = 0
    rows = []
    semaphore = asyncio.Semaphore(3)

    async with FacebookClient() as client:
        async def one(slug: str, brand: str):
            async with semaphore:
                html = await client.fetch_about(slug)
            tier = classify_tier(len(html))
            from src.parser import parse_page

            parsed = parse_page(html) if tier != TIER_HOLLOW else {}
            return build_record({"slug": slug, "expectedBrand": brand}, tier, parsed, len(html))

        rows = await asyncio.gather(
            *(one(slug, brand) for slug, brand, _, _, _ in FIXTURES)
        )

    print(f"\n{'slug':30}{'tier':9}{'exists':8}{'match':10}{'followers':>12}  name")
    print("-" * 100)
    for row, (slug, _, want_tier, want_match, want_followers) in zip(rows, FIXTURES):
        print(
            f"{row['slug'][:29]:30}{row['payloadTier']:9}{str(row['exists']):8}"
            f"{row['brandMatch']:10}{str(row.get('followers')):>12}  {str(row.get('name'))[:30]}"
        )
        if row["payloadTier"] != want_tier:
            print(f"  FAIL {slug}: tier {row['payloadTier']}, expected {want_tier}")
            failures += 1
        if row["brandMatch"] != want_match:
            print(f"  FAIL {slug}: brandMatch {row['brandMatch']}, expected {want_match}")
            failures += 1
        if want_followers and row.get("followers") is None:
            print(f"  FAIL {slug}: no follower count parsed")
            failures += 1
        if not want_followers and row.get("exists"):
            print(f"  FAIL {slug}: reported as existing")
            failures += 1

    print("\nRUN_SUMMARY:", json.dumps(summarise(rows)))
    return failures


async def main() -> None:
    failures = test_pure_functions()
    failures += await test_live()
    print(f"\n{'PASS' if not failures else f'{failures} FAILURE(S)'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    asyncio.run(main())
