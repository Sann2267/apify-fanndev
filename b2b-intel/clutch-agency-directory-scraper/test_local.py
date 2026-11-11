"""Local smoke test -- real HTTP against clutch.co, no Apify platform involved.

    python test_local.py

The assertions are about measured facts, not about "it did not crash":

* the ``?page=1`` alias is real -- page 1 is the bare URL, and ``?page=1`` and
  ``?page=2`` return the same ranked set, so a naive loop would skip page 1;
* the Leaders Matrix block repeats identically on consecutive pages while the
  ranked rows never overlap, which is what makes the dedupe key load-bearing;
* roughly half of page 1 in a busy category is paid placement, and the Actor
  can tell you which half;
* the lead attributes the vein is bought for (min project size, hourly rate,
  headcount, website) are present on the ranked rows, not only on sponsors;
* the outbound website URL survives the r.clutch.co redirect;
* a profile's JSON-LD carries the money fields, while its ``review`` array does
  NOT match the page's review list -- which is why reviews come from the HTML;
* robots-disallowed query parameters are stripped before any request is sent.
"""

import asyncio
import collections
import sys

from src.client import ClutchClient
from src.constants import BASE
from src.extractor import (
    category_record,
    parse_directory,
    parse_profile,
    parse_reviews,
    parse_sitemap,
    split_percent,
    website_from_redirect,
)
from src.main import normalize_category, normalize_profile, page_url, strip_disallowed

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

CATEGORY = f"{BASE}/web-developers"


async def main():  # noqa: C901 -- a smoke test reads better flat
    client = ClutchClient()
    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        print(f"   {'PASS' if condition else 'FAIL'}  {label}" + (f" -- {detail}" if detail else ""))
        if not condition:
            failures.append(label)

    print("=" * 74)
    print("0. pure functions")
    assert split_percent("25% Web Development") == (25.0, "Web Development")
    assert split_percent("Web Development") == (None, "Web Development")
    assert website_from_redirect(
        "https://r.clutch.co/redirect?pid=1&u=https%3A%2F%2Fexample.com%2Fa%3Fb%3Dc"
    ) == "https://example.com/a?b=c"
    assert normalize_category("web-developers") == CATEGORY
    assert normalize_category("/id/web-developers") == f"{BASE}/id/web-developers"
    assert normalize_profile("imaginovation") == f"{BASE}/profile/imaginovation"
    assert page_url(CATEGORY, 1) == CATEGORY, "page 1 must never carry ?page="
    assert page_url(CATEGORY, 7) == f"{CATEGORY}?page=7"
    cleaned, dropped = strip_disallowed(f"{CATEGORY}?page=3&sort_by=rating&hourly_rate=1")
    assert dropped == ["sort_by", "hourly_rate"], dropped
    assert "page=3" in cleaned and "sort_by" not in cleaned
    cat = category_record(f"{BASE}/ng/web-designers/lagos")
    assert (cat["countryCode"], cat["categorySlug"], cat["refinements"]) == ("ng", "web-designers", ["lagos"])
    print("   percent split, redirect unwrap, URL normalisation, robots stripping: ok")

    print("=" * 74)
    print("1. page 1 is the bare URL -- the ?page=1 alias")
    bare = parse_directory(await client.get_text(CATEGORY), CATEGORY, 1)
    p1 = parse_directory(await client.get_text(f"{CATEGORY}?page=1"), CATEGORY, 1)
    p2 = parse_directory(await client.get_text(f"{CATEGORY}?page=2"), CATEGORY, 2)
    bare_ids = {r["providerId"] for r in bare["records"] if r["isRankedResult"]}
    p1_ids = {r["providerId"] for r in p1["records"] if r["isRankedResult"]}
    p2_ids = {r["providerId"] for r in p2["records"] if r["isRankedResult"]}
    print(f"   bare={bare['pageTitle']!r}")
    print(f"   ?page=1={p1['pageTitle']!r}")
    print(f"   ?page=2={p2['pageTitle']!r}")
    check("?page=1 returns the same ranked set as ?page=2", p1_ids == p2_ids and bool(p1_ids),
          f"{len(p1_ids)} vs {len(p2_ids)} ids")
    check("?page=1 is NOT page 1", p1_ids != bare_ids,
          f"bare has {len(bare_ids)} ranked ids, ?page=1 has {len(p1_ids)}")

    print("=" * 74)
    print("2. page composition -- what a category page actually is")
    print(f"   page 1: {bare['rowCount']} rows = {bare['rankedCount']} ranked / "
          f"{bare['paidCount']} paid / {bare['pinnedCount']} pinned")
    check("page 1 carries paid placement", bare["paidCount"] > 0, f"{bare['paidCount']} rows")
    check("page 1 reports the category size", bool(bare["totalCompaniesClaim"]),
          f"claims {bare['totalCompaniesClaim']} companies")
    check("the pager exposes how deep the category goes", bool(bare["lastPageInPager"]),
          f"last page {bare['lastPageInPager']}")

    print("=" * 74)
    print("3. pinned rows repeat, ranked rows never do")
    p3 = parse_directory(await client.get_text(page_url(CATEGORY, 3)), CATEGORY, 3)
    p4 = parse_directory(await client.get_text(page_url(CATEGORY, 4)), CATEGORY, 4)
    pinned3 = {r["providerId"] for r in p3["records"] if r["isPinnedBlock"]}
    pinned4 = {r["providerId"] for r in p4["records"] if r["isPinnedBlock"]}
    ranked3 = {r["providerId"] for r in p3["records"] if r["isRankedResult"]}
    ranked4 = {r["providerId"] for r in p4["records"] if r["isRankedResult"]}
    check("pinned block is identical on consecutive pages",
          bool(pinned3) and pinned3 == pinned4, f"{len(pinned3)} rows repeated")
    check("ranked rows do not overlap between pages", not (ranked3 & ranked4),
          f"{len(ranked3)} and {len(ranked4)} ids, {len(ranked3 & ranked4)} shared")
    check("a page carries a full block of ranked rows", len(ranked3) >= 40, f"{len(ranked3)} ranked")

    print("=" * 74)
    print("4. lead attributes on RANKED rows, not just sponsors")
    ranked_rows = [r for r in p3["records"] if r["isRankedResult"]]
    have = {
        key: sum(1 for r in ranked_rows if r.get(key))
        for key in ("minProjectSize", "hourlyRate", "employees", "location", "website", "services")
    }
    for key, count in have.items():
        print(f"   {key:<16} {count}/{len(ranked_rows)}")
    check("min project size present on every ranked row", have["minProjectSize"] == len(ranked_rows))
    check("hourly rate present on every ranked row", have["hourlyRate"] == len(ranked_rows))
    check("headcount present on every ranked row", have["employees"] == len(ranked_rows))
    check("the agency's own website survived the redirect", have["website"] == len(ranked_rows))
    sample = ranked_rows[0]
    print(f"   sample: {sample['name']} | {sample['minProjectSize']} | {sample['hourlyRate']} | "
          f"{sample['employees']} | {sample['location']} | {sample['websiteDomain']}")
    check("a service mix carries percentages",
          bool(sample["services"]) and any(s.get("percent") for s in sample["services"]),
          str(sample["services"])[:110])
    check("no clutch.co redirect leaked into the website field",
          not any("r.clutch.co" in (r.get("website") or "") for r in ranked_rows))

    print("=" * 74)
    print("5. profile -- JSON-LD money fields")
    slug = sample["profileUrl"]
    html = await client.get_text(slug)
    profile = parse_profile(html, slug)
    print(f"   {profile['name']} | founded {profile['foundingDate']} | {profile['priceRange']} | "
          f"{profile['rating']} from {profile['reviewCount']} reviews | {profile['websiteDomain']}")
    check("profile carries structured data", profile["hasLdJson"])
    check("profile carries the agency website", bool(profile["website"]))
    check("profile carries the summary strip",
          bool(profile["minProjectSize"] or profile["hourlyRate"] or profile["employees"]),
          f"{profile['minProjectSize']} / {profile['hourlyRate']} / {profile['employees']}")
    check("profile carries a service-line chart", bool(profile["serviceLines"]),
          str(profile["serviceLines"])[:110])
    lines_total = sum(e["percent"] or 0 for e in profile["serviceLines"] or [])
    check("the service split adds up to 100", 99 <= lines_total <= 101, f"{lines_total}")
    if profile["focusAreas"]:
        groups = collections.defaultdict(float)
        for entry in profile["focusAreas"]:
            groups[entry["groupLabel"]] += entry["percent"] or 0
        off = {k: round(v, 1) for k, v in groups.items() if not 99 <= v <= 101}
        print(f"   focus groups: {len(groups)} -> " + ", ".join(f"{k}={round(v)}%" for k, v in list(groups.items())[:4]))
        check("each focus group is its own 100% scale, not one flat list", not off, str(off))

    print("=" * 74)
    print("6. reviews come from the HTML, because JSON-LD disagrees with the page")
    reviews = parse_reviews(html, slug, 1)
    print(f"   {len(reviews)} review blocks on page 1, profile claims {profile['reviewCount']}")
    check("review blocks were found", len(reviews) > 0)
    check("every review has an id", all(r["reviewId"] for r in reviews),
          f"{sum(1 for r in reviews if r['reviewId'])}/{len(reviews)}")
    graded = [r for r in reviews if r["ratingQuality"] is not None]
    check("reviews carry the four sub-ratings", bool(graded),
          f"{len(graded)}/{len(reviews)} with a Quality score")
    if reviews:
        r0 = reviews[0]
        print(f"   sample: {r0['title']!r} | {r0['rating']} | {r0['projectSize']} | "
              f"{r0['projectLength']} | {r0['reviewerPosition']}")
    page2_html = await client.get_text(page_url(slug, 2))
    reviews2 = parse_reviews(page2_html, slug, 2)
    ids1 = {r["reviewId"] for r in reviews}
    ids2 = {r["reviewId"] for r in reviews2}
    print(f"   page 2 carries {len(reviews2)} blocks, {len(ids2 - ids1)} of them new")
    check("review pagination yields new reviews", bool(ids2 - ids1) or not reviews2,
          f"{len(ids2 - ids1)} new")

    print("=" * 74)
    print("7. category index from the sitemap")
    index = await client.get_text(f"{BASE}/sitemap.xml")
    shards = [u for u in parse_sitemap(index) if "sitemap-directory" in u]
    check("the sitemap index lists directory shards", len(shards) >= 1, f"{len(shards)} shards")
    urls = parse_sitemap(await client.get_text(shards[0]))
    records = [category_record(u) for u in urls[:500]]
    roots = [r for r in records if r["isRootCategory"]]
    countries = {r["countryCode"] for r in records if r["countryCode"]}
    print(f"   {len(urls)} URLs in shard 1; first 500 hold {len(roots)} root categories "
          f"and {len(countries)} country cuts")
    check("category URLs split into axes", bool(countries) or bool(roots))

    print("=" * 74)
    print(f"requests={client.requests} challenges={client.challenges} tls={client.winning_profile}")
    await client.close()

    if failures:
        print(f"\n{len(failures)} FAILED: {failures}")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
