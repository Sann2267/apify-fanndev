"""Local end-to-end test: run the actor per case against local Apify storage.

    python test_local.py            # all cases
    python test_local.py summary    # cases whose name starts with 'summary'
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PY = sys.executable
NOPROXY = {"useApifyProxy": False}

CASES = {
    "summary": {"mode": "summary", "apps": ["553850", "https://store.steampowered.com/app/1988540/", "999999999"], "sampleSize": 300, "proxyConfiguration": NOPROXY},
    "summary_name": {"mode": "summary", "apps": ["Stardew Valley"], "sampleSize": 0, "languages": ["english", "schinese"], "proxyConfiguration": NOPROXY},
    "reviews": {"mode": "reviews", "apps": ["1091500"], "maxReviewsPerApp": 250, "proxyConfiguration": NOPROXY},
    "reviews_full_small": {"mode": "reviews", "apps": ["1988540"], "maxReviewsPerApp": 5000, "textSentiment": False, "proxyConfiguration": NOPROXY},
    "reviews_helpful_neg": {"mode": "reviews", "apps": ["1988540"], "sortBy": "all", "reviewType": "negative", "maxReviewsPerApp": 500, "proxyConfiguration": NOPROXY},
    "reviews_window": {"mode": "reviews", "apps": ["1091500"], "startDate": "2026-10-01", "endDate": "2026-10-05", "language": "english", "minPlaytimeHours": 50, "maxReviewsPerApp": 2000, "proxyConfiguration": NOPROXY},
    "history": {"mode": "history", "apps": ["553850"], "proxyConfiguration": NOPROXY},
    "languages": {"mode": "languages", "apps": ["553850"], "purchaseType": "steam", "proxyConfiguration": NOPROXY},
    "user": {"mode": "userReviews", "steamUsers": ["https://steamcommunity.com/profiles/76561198112703551", "gabelogannewell", "thisdoesnotexist_zz9q", "not a user!!"], "maxReviewsPerApp": 25, "proxyConfiguration": NOPROXY},
    "bad_language": {"mode": "reviews", "apps": ["10"], "language": "klingon", "proxyConfiguration": NOPROXY},
}

REQUIRED = {
    "REVIEW": ["_input", "_source", "_scrapedAt", "appId", "appName", "recommendationid", "review", "voted_up", "createdAt", "author", "reviewUrl"],
    "SUMMARY": ["_input", "appId", "appName", "steamScore", "allPurchasesScore", "trend", "languageBreakdown"],
    "HISTORY": ["_input", "appId", "period", "periodStart", "recommendations_up", "positiveRatio"],
    "LANGUAGE": ["_input", "appId", "language", "total_reviews", "positiveRatio", "shareOfAllReviews", "rank"],
    "USER_REVIEW": ["_input", "steamProfileUrl", "appId", "recommendationid", "voted_up", "postedDate", "review", "hoursOnRecord"],
    "ERROR": ["_input", "_error", "_errorDetail"],
}


def run(name: str, actor_input: dict) -> tuple[list[dict], int]:
    storage = HERE / "storage"
    shutil.rmtree(storage, ignore_errors=True)
    kvs = storage / "key_value_stores" / "default"
    kvs.mkdir(parents=True)
    (kvs / "INPUT.json").write_text(json.dumps(actor_input), encoding="utf8")
    env = dict(os.environ, APIFY_LOCAL_STORAGE_DIR=str(storage), PYTHONIOENCODING="utf8")
    p = subprocess.run([PY, "-m", "src"], cwd=HERE, env=env, capture_output=True, text=True, encoding="utf8", timeout=1800)
    log = (p.stdout + p.stderr).strip().splitlines()
    print(f"\n===== {name}  exit={p.returncode}")
    for line in [l for l in log if "WARN" in l or "ERROR" in l or "Traceback" in l][:10] + log[-4:]:
        print("   |", line[:220])
    items = []
    ds = storage / "datasets" / "default"
    for f in (sorted(x for x in ds.glob("*.json") if not x.name.startswith("__")) if ds.exists() else []):
        items.append(json.loads(f.read_text(encoding="utf8")))
    (HERE / "storage_last").mkdir(exist_ok=True)
    (HERE / "storage_last" / f"{name}.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf8")
    return items, p.returncode


def check(name: str, items: list[dict], code: int) -> bool:
    ok = code == 0 or name == "bad_language"
    by_type: dict[str, int] = {}
    for it in items:
        rt = it.get("recordType")
        by_type[rt] = by_type.get(rt, 0) + 1
        missing = [k for k in REQUIRED.get(rt, []) if k not in it or (it.get(k) in (None, "") and k not in ("appName", "review"))]
        if missing:
            ok = False
            print(f"   !! {rt} {it.get('recommendationid') or it.get('appId')} missing {missing}")
    keyed = [(i.get("_input"), i.get("recommendationid"), i.get("period"), i.get("periodStart"), i.get("language")) for i in items if not i.get("_error")]
    dup = len(keyed) - len(set(keyed))
    if dup:
        ok = False
        print(f"   !! {dup} duplicate records")
    errs = [(i["_input"], i["_error"]) for i in items if i.get("_error")]
    print(f"   records={len(items)} {by_type} dupes={dup} errors={errs}")
    return ok


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    results = {}
    for name, inp in CASES.items():
        if name.startswith(only):
            items, code = run(name, inp)
            results[name] = check(name, items, code)
    print("\nSUMMARY", results)
