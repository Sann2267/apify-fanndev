#!/usr/bin/env python3
"""List every actor a given Apify username has published (public Store API).

No auth required - this is the same public endpoint apify.com/@<username>
uses. Built as the "am I about to duplicate something I already built?"
check that pairs with api-search-actors.py during actor market research.

Default behavior writes JSON files to disk (no console JSON dump): one file
per category the account's actors fall under, e.g.
    output/ECOMMERCE.json
    output/NEWS.json
    output/_uncategorized.json   # only if some actor has no categories
An actor with multiple categories (the normal case) appears in each of its
category files, matching how the Store itself lists it.

CLI usage:
    python apify-my-store.py xtracto
    python apify-my-store.py xtracto --output-dir mine
    python apify-my-store.py xtracto --output mine.json   # single combined file instead of per-category split
    python apify-my-store.py xtracto --json                # raw JSON to stdout (piping/debugging), no files written
    python apify-my-store.py xtracto --table                # old human-readable table to stdout, no files written
"""
import argparse
import json
import os
import sys

import requests

STORE_URL = "https://api.apify.com/v2/store"


def fetch_all(username, page_size=100):
    """Paginate through /v2/store?username=... and return the full item list."""
    items = []
    offset = 0
    while True:
        resp = requests.get(
            STORE_URL,
            params={"username": username, "limit": page_size, "offset": offset},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        items.extend(data["items"])
        offset += page_size
        if offset >= data["total"] or not data["items"]:
            break
    return items


def group_by_category(items):
    """Return {category: [actor, ...]}. Actors with multiple categories appear
    in each. Actors with none go under "_uncategorized"."""
    grouped = {}
    for it in items:
        cats = it.get("categories") or []
        if not cats:
            grouped.setdefault("_uncategorized", []).append(it)
            continue
        for cat in cats:
            grouped.setdefault(cat, []).append(it)
    return grouped


def write_per_category(items, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    grouped = group_by_category(items)
    written = []
    for cat, actors in sorted(grouped.items()):
        path = os.path.join(output_dir, f"{cat}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(actors, f, ensure_ascii=False, indent=2)
        written.append((cat, len(actors), path))
    return written


def print_table(items):
    for it in items:
        stats = it.get("stats", {})
        cats = ",".join(it.get("categories") or [])
        print(
            f"{it['name']:<45} | {cats:<40} | "
            f"runs={stats.get('totalRuns', 0):>8} | users={stats.get('totalUsers', 0):>5} | "
            f"{it.get('title', '')}"
        )


def _fix_windows_console_encoding():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        enc = getattr(stream, "encoding", None)
        if enc and enc.lower() != "utf-8":
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def main():
    _fix_windows_console_encoding()

    parser = argparse.ArgumentParser(description="List/export all actors published by an Apify store username.")
    parser.add_argument("username", help="Apify store username, e.g. xtracto")
    parser.add_argument("--output-dir", metavar="DIR", default="output",
                         help="Folder to write one JSON file per category into (default: ./output)")
    parser.add_argument("-o", "--output", metavar="FILE",
                         help="Write a single combined JSON file instead of splitting per category")
    parser.add_argument("--json", action="store_true", help="Print raw JSON to stdout instead of writing files")
    parser.add_argument("--table", action="store_true", help="Print a human-readable table to stdout instead of writing files")
    args = parser.parse_args()

    items = fetch_all(args.username)

    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return

    if args.table:
        print(f"{args.username}: {len(items)} published actors\n")
        print_table(items)
        return

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"{args.username}: {len(items)} published actors -> wrote {args.output}")
        return

    written = write_per_category(items, args.output_dir)
    print(f"{args.username}: {len(items)} published actors -> wrote {len(written)} category files to {args.output_dir}/\n")
    for cat, count, path in written:
        print(f"{count:>4}  {path}")


if __name__ == "__main__":
    main()
