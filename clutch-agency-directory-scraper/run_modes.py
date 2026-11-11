"""Run every mode against local storage, one after another, and report what
each produced. This is the Phase-3 loop: it is meant to be re-run after any
change to the extractor, not kept as a one-off.

    python run_modes.py            # all modes
    python run_modes.py reviews    # one mode
"""

import collections
import glob
import json
import os
import shutil
import subprocess
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

CASES = {
    "directory": {"mode": "directory", "categories": ["web-developers"], "maxPages": 2, "maxItems": 40},
    "directory-pinned": {
        "mode": "directory",
        "categories": ["seo-firms"],
        "maxPages": 2,
        "includePinnedRows": True,
        "includePaidPlacements": False,
        "maxItems": 40,
    },
    "profile": {"mode": "profile", "profileUrls": ["imaginovation", "cleveroad"]},
    "reviews": {"mode": "reviews", "profileUrls": ["imaginovation"], "maxReviewPages": 3},
    "categories": {"mode": "categories", "categoryFilter": "/id/", "maxItems": 25},
    "reference": {"mode": "reference", "categories": ["web-developers"]},
}

DATASET = "storage/datasets/default"
INPUT = "storage/key_value_stores/default/INPUT.json"


def reset() -> None:
    shutil.rmtree("storage/datasets", ignore_errors=True)
    os.makedirs(os.path.dirname(INPUT), exist_ok=True)


def records() -> list[dict]:
    out = []
    for path in sorted(glob.glob(f"{DATASET}/*.json")):
        with open(path, encoding="utf-8") as fh:
            item = json.load(fh)
        if "recordType" in item:
            out.append(item)
    return out


def main() -> int:
    wanted = sys.argv[1:] or list(CASES)
    failures = []
    for name in wanted:
        case = CASES[name]
        print("=" * 74)
        print(f"MODE {name}: {json.dumps(case)}")
        reset()
        with open(INPUT, "w", encoding="utf-8") as fh:
            json.dump(case, fh)
        proc = subprocess.run(
            [sys.executable, "-m", "src"], capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        tail = [ln for ln in (proc.stdout + proc.stderr).splitlines() if ln.strip()][-6:]
        for line in tail:
            print("   |", line[:190])
        data = records()
        kinds = collections.Counter(r.get("recordType") for r in data)
        print(f"   exit={proc.returncode} records={len(data)} {dict(kinds)}")
        if proc.returncode != 0 or not data:
            failures.append(name)
            continue
        sample = data[0]
        keys = [k for k, v in sample.items() if v not in (None, [], {})]
        print(f"   populated fields on first record ({len(keys)}): {', '.join(keys[:14])}")
        if name.startswith("directory"):
            print(f"     rowTypes: {dict(collections.Counter(r.get('rowType') for r in data))}")
            print(f"     pages:    {dict(collections.Counter(r.get('pageNumber') for r in data))}")
            ids = [r.get("providerId") for r in data]
            print(f"     duplicate providerIds: {len(ids) - len(set(ids))}")
        if name == "reviews":
            ids = [r.get("reviewId") for r in data]
            print(f"     reviews={len(data)} distinct={len(set(ids))} "
                  f"withSubRatings={sum(1 for r in data if r.get('ratingQuality') is not None)}")
        if name == "reference":
            for r in data:
                print(f"     check={r.get('check')}: "
                      f"{json.dumps({k: v for k, v in r.items() if k not in ('_input', '_source', '_scrapedAt', 'recordType', 'note', 'expected')}, ensure_ascii=False)[:230]}")
    print("=" * 74)
    if failures:
        print(f"FAILED modes: {failures}")
        return 1
    print("every mode produced records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
