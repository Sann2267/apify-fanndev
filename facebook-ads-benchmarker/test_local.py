"""Offline + live checks for the ads benchmarker.

    python test_local.py            # live: sample one niche and benchmark it
    python test_local.py --offline  # analytics only, no network
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter

sys.path.insert(0, ".")

from src.analytics import _length_band, _words, benchmark, compare  # noqa: E402
from src.fbcore import FacebookSession  # noqa: E402
from src.main import build_queries, read_niches  # noqa: E402
from src.search import collect  # noqa: E402


class Log:
    def info(self, message):
        print(f"  [info] {message}")

    def warning(self, message):
        print(f"  [warn] {message}")


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))
    return bool(condition)


def fake_ads(count: int) -> list[dict]:
    ctas = ["Shop now", "Shop now", "Learn more"]
    formats = ["VIDEO", "IMAGE", "VIDEO"]
    out = []
    for i in range(count):
        out.append(
            {
                "adArchiveId": str(i),
                "isActive": i % 4 != 0,
                "pageName": f"Brand {i % 3}",
                "ctaText": ctas[i % 3],
                "displayFormat": formats[i % 3],
                "publisherPlatforms": ["FACEBOOK", "INSTAGRAM"],
                "title": "Free shipping today",
                "linkUrl": "https://www.example.com/offer?utm=1",
                "adText": "Free shipping today on every order {{product.name}}",
                "adTextWordCount": 6,
                "hasVideo": formats[i % 3] == "VIDEO",
                "runningDays": 10 + (i % 30),
            }
        )
    return out


def offline_checks() -> bool:
    ok = True

    ok &= check("simple niches accepted",
                [n["name"] for n in read_niches({"niches": ["a", "b"]})] == ["a", "b"])
    grouped = read_niches({"niches": [{"name": "skincare", "keywords": ["serum", "cream"]}]})
    ok &= check("grouped niche keeps both keywords",
                grouped and grouped[0]["keywords"] == ["serum", "cream"])
    queries = build_queries(grouped[0], {}, ["US", "GB"])
    ok &= check("2 keywords x 2 countries = 4 searches", len(queries) == 4)

    ok &= check("template tokens stripped", "product" not in _words("buy {{product.name}} now"))
    ok &= check("stopwords dropped", _words("the best serum") == ["best", "serum"])
    ok &= check("length bands", _length_band(6) == "1-10 words" and _length_band(400) == "100+ words")

    rows = benchmark("demo", fake_ads(30), {"topN": 5, "minGroupSample": 3})
    by_metric = Counter(r["metric"] for r in rows)
    ok &= check("overview row emitted", by_metric["OVERVIEW"] == 1)
    overview = next(r for r in rows if r["metric"] == "OVERVIEW")
    ok &= check("sample size reported", overview["sampleSize"] == 30)
    ok &= check("active share computed", overview["activeShare"] is not None,
                str(overview["activeShare"]))
    ok &= check("CTA ranking present", by_metric["TOP_CTA"] >= 2)
    ok &= check("longevity by CTA present", by_metric["LONGEVITY_BY_CTA"] >= 1)
    ok &= check("phrases counted once per ad",
                all(r["count"] <= 30 for r in rows if r["metric"] == "TOP_PHRASE_2"))

    word_rows = [r for r in rows if r["metric"] == "TOP_WORD"]
    ok &= check("no template token in words",
                all(r["value"] != "product" for r in word_rows))

    rows_b = benchmark("other", fake_ads(20), {"topN": 5, "minGroupSample": 3})
    comparison = compare(rows + rows_b, "TOP_CTA", 5)
    ok &= check("comparison spans both niches",
                comparison and set(comparison[0]["sharePerNiche"]) == {"demo", "other"})
    return ok


async def live_checks() -> bool:
    ok = True
    niche = {"name": "protein powder", "keywords": ["protein powder"], "advertisers": []}
    queries = build_queries(niche, {"activeStatus": "active"}, ["US"])
    filters = {"onlyActive": False, "onlyWithVideo": False,
               "minRunningDays": None, "adTextContains": None}

    async with FacebookSession(log=Log()) as session:
        ads, meta = await collect(session, queries[0], 60, filters)

    ok &= check("sample collected", len(ads) >= 30, f"{len(ads)} ads")
    if not ads:
        return ok

    rows = benchmark(niche["name"], ads, {"topN": 10, "minGroupSample": 3})
    overview = next(r for r in rows if r["metric"] == "OVERVIEW")
    ok &= check("overview computed from the live sample",
                overview["sampleSize"] == len(ads))
    ok &= check("median days on air present", overview["medianRunningDays"] is not None,
                str(overview["medianRunningDays"]))

    ctas = [r for r in rows if r["metric"] == "TOP_CTA"]
    ok &= check("real CTAs ranked", len(ctas) >= 1,
                ", ".join(f"{r['value']} ({r['share']}%)" for r in ctas[:3]))
    words = [r for r in rows if r["metric"] == "TOP_WORD"]
    ok &= check("real vocabulary ranked", len(words) >= 3,
                ", ".join(r["value"] for r in words[:6]))
    longevity = [r for r in rows if r["metric"] == "LONGEVITY_BY_FORMAT"]
    print("   longevity by format:",
          json.dumps([{k: r[k] for k in ("value", "count", "medianRunningDays")}
                      for r in longevity], ensure_ascii=False))
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
