"""Run the detector against live sites without an Apify runtime.

    python test_local.py

Asserts that known sites still resolve to their known stacks, so a vendor
changing its CDN hostname shows up as a failing expectation rather than as a
quietly emptier dataset.
"""

from __future__ import annotations

import asyncio
import sys

from src.client import WebClient
from src.detector import Evidence, detect, summarise_stack
from src.fingerprints import CATEGORIES, FINGERPRINTS
from src.main import normalise_target, run_summary

# site -> technologies that must be detected
EXPECTED = {
    "allbirds.com": ["Shopify", "Cloudflare"],
    "notion.com": ["Next.js", "Vercel", "Contentful"],
    "wordpress.org": ["WordPress"],
    "squarespace.com": ["Squarespace"],
    "hubspot.com": ["HubSpot", "HubSpot CMS"],
}


def test_table() -> int:
    failures = 0
    names = [f["name"] for f in FINGERPRINTS]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        print(f"  FAIL duplicate technology names: {duplicates}")
        failures += 1
    for entry in FINGERPRINTS:
        if entry["category"] not in CATEGORIES:
            print(f"  FAIL {entry['name']}: unknown category {entry['category']}")
            failures += 1
        if not entry["signals"]:
            print(f"  FAIL {entry['name']}: no signals")
            failures += 1
        for signal_type, value, confidence in entry["signals"]:
            if signal_type not in ("header", "cookie", "generator", "host", "html"):
                print(f"  FAIL {entry['name']}: bad signal type {signal_type}")
                failures += 1
            if confidence not in ("confirmed", "likely"):
                print(f"  FAIL {entry['name']}: bad confidence {confidence}")
                failures += 1
            if not value:
                print(f"  FAIL {entry['name']}: empty signal value")
                failures += 1
    print(f"fingerprint table ({len(FINGERPRINTS)} technologies): "
          f"{'OK' if not failures else str(failures) + ' FAILURE(S)'}")
    return failures


def test_matching() -> int:
    """Signal matching, especially the cases that should NOT match."""
    failures = 0

    def check(label: str, got, want) -> None:
        nonlocal failures
        if bool(got) != bool(want):
            print(f"  FAIL {label}: got {got!r}, want {'a match' if want else 'no match'}")
            failures += 1

    html = (
        '<html><head><meta name="generator" content="WordPress 6.5">'
        '<script src="https://cdn.shopify.com/s/files/x.js"></script>'
        '<script src="https://sub.cdn.shopify.com/y.js"></script>'
        '<script src="https://myshop.apple.com/z.js"></script>'
        '<script src="/local/app.js"></script>'
        "</head><body>__NEXT_DATA__</body></html>"
    )
    evidence = Evidence(
        html,
        {"Server": "nginx/1.2", "X-Powered-By": "Next.js"},
        ["_shopify_y"],
        "https://example.com/",
    )

    check("host exact", evidence.match("host", "cdn.shopify.com"), True)
    check("host subdomain", evidence.match("host", "shopify.com"), True)
    # "shop.app" must not be satisfied by "myshop.apple.com".
    check("host not substring", evidence.match("host", "shop.app"), False)
    check("own host ignored", evidence.match("host", "example.com"), False)
    check("relative asset ignored", evidence.match("host", "local"), False)
    check("cookie", evidence.match("cookie", "_shopify_y"), True)
    check("cookie absent", evidence.match("cookie", "laravel_session"), False)
    check("header name only", evidence.match("header", "x-powered-by"), True)
    check("header with value", evidence.match("header", "x-powered-by:Next.js"), True)
    check("header wrong value", evidence.match("header", "server:Apache"), False)
    check("generator", evidence.match("generator", "WordPress"), True)
    check("generator absent", evidence.match("generator", "Drupal"), False)
    check("html", evidence.match("html", "__NEXT_DATA__"), True)
    check("html absent", evidence.match("html", "__NUXT__"), False)

    found = {d["technology"] for d in detect(html, {"X-Powered-By": "Next.js"}, ["_shopify_y"], "https://example.com/")}
    for expected in ("Shopify", "WordPress", "Next.js"):
        if expected not in found:
            print(f"  FAIL synthetic page: {expected} not detected")
            failures += 1

    check("normalise bare", normalise_target("allbirds.com"), True)
    check("normalise junk", normalise_target("not a domain"), False)
    check("normalise localhost", normalise_target("localhost"), False)

    print(f"matching: {'OK' if not failures else str(failures) + ' FAILURE(S)'}")
    return failures


async def test_live() -> int:
    failures = 0
    rows = []
    semaphore = asyncio.Semaphore(5)

    async with WebClient() as client:
        async def one(site: str):
            async with semaphore:
                page = await client.fetch(f"https://{site}/")
            detections = detect(
                page["html"], page["headers"], page["cookies"], page["finalUrl"]
            )
            return site, detections, summarise_stack(detections)

        results = await asyncio.gather(
            *(one(site) for site in EXPECTED), return_exceptions=True
        )

    print()
    for result in results:
        if isinstance(result, Exception):
            print(f"  FAIL live fetch raised {type(result).__name__}: {result}")
            failures += 1
            continue
        site, detections, stack = result
        rows.append({"reachable": True, **stack})
        found = set(stack["technologies"])
        missing = [t for t in EXPECTED[site] if t not in found]
        status = "OK  " if not missing else "FAIL"
        print(f"  {status} {site:20} {stack['technologyCount']:>2} tech: "
              f"{', '.join(stack['technologies'][:6])}")
        if missing:
            print(f"       missing: {missing}")
            failures += 1

    if rows:
        ranking = run_summary(rows)["technologyRanking"][:5]
        print("\n  ranking:", ", ".join(f"{r['technology']} ({r['sites']})" for r in ranking))
    return failures


async def main() -> None:
    failures = test_table() + test_matching() + await test_live()
    print(f"\n{'PASS' if not failures else f'{failures} FAILURE(S)'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    asyncio.run(main())
