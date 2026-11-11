#!/usr/bin/env python3
"""Show NEW failed runs per public actor since the previous check.

The Apify API has no per-day breakdown of other users' runs, only the rolling
`stats.publicActorRunStats30Days` counter on each public actor (anonymous GET,
includes Apify's daily test runs). This script snapshots that counter for every
public actor of a username and diffs it against the previous snapshot. A rise in
FAILED / TIMED-OUT between two snapshots is a failure that happened in between.
Counts can also DROP as old runs fall out of the 30-day window, so a delta of
0 or less means "no new failures large enough to outweigh the expiring ones".

CLI usage:
    python apify-failed-runs-delta.py              # fanndev, snapshots in ./run-stats/
    python apify-failed-runs-delta.py fanndev --dir run-stats
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import glob
import json
import os

import requests

BAD = ("FAILED", "TIMED-OUT")


def public_actors(username):
    items, offset = [], 0
    while True:
        data = requests.get("https://api.apify.com/v2/store", timeout=30, params={
            "username": username, "limit": 100, "offset": offset}).json()["data"]
        items += data["items"]
        offset += 100
        if offset >= data["total"] or not data["items"]:
            return items


def actor_stats(item):
    d = requests.get(f"https://api.apify.com/v2/acts/{item['id']}", timeout=30).json()["data"]
    return item["name"], {
        "stats": d["stats"].get("publicActorRunStats30Days") or {},
        "notice": d.get("notice"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("username", nargs="?", default="fanndev")
    ap.add_argument("--dir", default="run-stats")
    args = ap.parse_args()
    os.makedirs(args.dir, exist_ok=True)

    previous = sorted(glob.glob(os.path.join(args.dir, "*.json")))
    with cf.ThreadPoolExecutor(16) as ex:
        now = dict(ex.map(actor_stats, public_actors(args.username)))
    stamp = dt.datetime.now().strftime("%Y-%m-%dT%H%M")
    with open(os.path.join(args.dir, f"{stamp}.json"), "w", encoding="utf-8") as f:
        json.dump(now, f, indent=1)

    maint = sorted(n for n, v in now.items() if v["notice"] == "UNDER_MAINTENANCE")
    print(f"{len(now)} public actors | UNDER_MAINTENANCE: {', '.join(maint) or '-'}")
    if not previous:
        print("First snapshot saved; run again later to see new failures.")
        return
    with open(previous[-1], encoding="utf-8") as f:
        before = json.load(f)
    print(f"Delta vs {os.path.basename(previous[-1])}:")
    rows = []
    for name, v in now.items():
        old = before.get(name, {}).get("stats", {})
        delta = {k: v["stats"].get(k, 0) - old.get(k, 0) for k in BAD + ("TOTAL",)}
        if any(delta[k] > 0 for k in BAD):
            rows.append((delta["FAILED"] + delta["TIMED-OUT"], name, delta))
    for bad, name, delta in sorted(rows, reverse=True):
        print(f"  +{bad:<3} {name}  (FAILED {delta['FAILED']:+}, "
              f"TIMED-OUT {delta['TIMED-OUT']:+}, runs {delta['TOTAL']:+})")
    if not rows:
        print("  no new failed runs")


if __name__ == "__main__":
    main()
