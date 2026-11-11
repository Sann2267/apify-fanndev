#!/usr/bin/env python3
"""Search the public Apify Store (Algolia `prod_PUBLIC_STORE` index).

This hits the same endpoint apify.com/store uses in the browser, so it needs
no Apify API token - the Algolia key embedded below is a public search-only
key (safe to keep in source control).

CLI usage:
    python api-search-actors.py --category ECOMMERCE --length 30 --sort users
    python api-search-actors.py --query "hotel reviews"

    # "underrated" scan: real demand, but not dominated by a giant.
    # --length doubles as "how many actors do I want to research" - Algolia
    # applies --min-users/--max-users server-side BEFORE truncating to length,
    # so a low --length here still returns the top N *within the band*, not
    # just the first N of the whole category.
    python api-search-actors.py --category TRAVEL --min-users 20 --max-users 3000 --length 15 --sort runs_per_user

Default behavior WRITES a JSON file, it does not print. Given --category, the
file is output/search-<CATEGORY>.json (e.g. output/search-TRAVEL.json), and
each run overwrites it with the fresh result set. Use --output to pick an
exact path, or --json/--table to print to stdout instead of writing anything.

Importable:
    from importlib import import_module
    m = import_module("api-search-actors")  # or rename to a valid module name
    m.search_store(category="TRAVEL", length=40, min_users=20, max_users=3000)

See .ai/skills/apify-store-research/SKILL.md for the full research workflow
(pairs with apify-my-store.py to cross-check against an existing account so
you don't propose an actor that's already built).
"""
import argparse
import json
import os
import re
import sys

import requests

ALGOLIA_APP_ID = "OW0O5I3QO7"
ALGOLIA_API_KEY = "0ecccd09f50396a4dbbe5dbfb17f4525"
ALGOLIA_URL = (
    f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/prod_PUBLIC_STORE/query"
    "?x-algolia-agent=Algolia%20for%20JavaScript%20(4.22.1)%3B%20Browser"
)

HEADERS = {
    "Accept": "*/*",
    "Origin": "https://apify.com",
    "Referer": "https://apify.com/",
    "content-type": "application/x-www-form-urlencoded",
    "x-algolia-api-key": ALGOLIA_API_KEY,
    "x-algolia-application-id": ALGOLIA_APP_ID,
}

DEFAULT_ATTRS = [
    "objectID", "title", "name", "username", "userFullName", "stats",
    "description", "categories", "actorReviewRating", "actorReviewCount",
    "bookmarkCount", "currentPricingInfo",
]

# Probed from the `categories` facet on prod_PUBLIC_STORE, 2026-08-08.
# Re-probe with --list-categories if this list ever looks stale.
CATEGORIES = [
    "AUTOMATION", "LEAD_GENERATION", "DEVELOPER_TOOLS", "ECOMMERCE", "SOCIAL_MEDIA",
    "AI", "OTHER", "JOBS", "BUSINESS", "REAL_ESTATE", "SEO_TOOLS", "NEWS", "AGENTS",
    "VIDEOS", "INTEGRATIONS", "TRAVEL", "MCP_SERVERS", "MARKETING", "OPEN_SOURCE",
    "EDUCATION", "SPORTS", "FOR_CREATORS", "GAMES", "COVID_19", "DEVELOPER_EXAMPLES",
]


def search_store(query="", category=None, length=24, offset=0, extra_filters=None,
                  attrs=None, min_users=None, max_users=None, min_runs=None):
    """POST a query to the Algolia store index. Returns the parsed JSON response.

    With query="" the index falls back to its default (roughly popularity-led)
    ranking, which is what makes this useful for a "what's doing well" scan
    instead of a literal keyword search.

    min_users/max_users/min_runs apply as server-side numeric filters on
    stats.totalUsers / stats.totalRuns - this is what makes the "underrated
    niche" scan cheap: Algolia excludes the giants (or the no-traction noise)
    before `length`/`offset` ever truncates the page, so a small --length
    still returns the top actors *within the band*, not just the first N
    of the unfiltered category.
    """
    filters = []
    if category:
        filters.append(f"categories:{category}")
    if extra_filters:
        filters.append(extra_filters)

    numeric_filters = []
    if min_users is not None:
        numeric_filters.append(f"stats.totalUsers>={min_users}")
    if max_users is not None:
        numeric_filters.append(f"stats.totalUsers<={max_users}")
    if min_runs is not None:
        numeric_filters.append(f"stats.totalRuns>={min_runs}")

    payload = {
        "query": query,
        "length": length,
        "offset": offset,
        "filters": " AND ".join(filters),
        "restrictSearchableAttributes": [],
        "attributesToHighlight": [],
        "attributesToRetrieve": attrs or DEFAULT_ATTRS,
        "analyticsTags": ["web", "store-search"],
        "clickAnalytics": True,
    }
    if numeric_filters:
        payload["numericFilters"] = numeric_filters

    resp = requests.post(ALGOLIA_URL, headers=HEADERS, data=json.dumps(payload), timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_category_facets():
    """Probe the `categories` facet to get the live category list + counts."""
    payload = {
        "query": "",
        "length": 1,
        "offset": 0,
        "filters": "",
        "facets": ["categories"],
        "attributesToRetrieve": ["objectID"],
    }
    resp = requests.post(ALGOLIA_URL, headers=HEADERS, data=json.dumps(payload), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("facets", {}).get("categories", {}), data.get("nbHits", 0)


def runs_per_user(hit):
    stats = hit.get("stats", {})
    users = stats.get("totalUsers", 0)
    runs = stats.get("totalRuns", 0)
    return (runs / users) if users else 0.0


def format_row(hit):
    stats = hit.get("stats", {})
    pricing = (hit.get("currentPricingInfo") or {}).get("pricingModel", "")
    return (
        f"{stats.get('totalUsers', 0):>7} users | "
        f"{stats.get('totalRuns', 0):>10} runs | "
        f"{runs_per_user(hit):>8.0f} runs/user | "
        f"{stats.get('actorReviewRating', 0):>4.2f}*({stats.get('actorReviewCount', 0)}) | "
        f"{pricing:<22} | "
        f"{hit.get('name', ''):<40} | "
        f"{hit.get('username', ''):<18} | "
        f"{hit.get('title', '')}"
    )


def _fix_windows_console_encoding():
    # Default Windows console codepage (cp1252) can't print titles containing
    # emoji, which are common in Store listings - crashes print() otherwise.
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

    parser = argparse.ArgumentParser(description="Search the public Apify Store (Algolia index).")
    parser.add_argument("--query", default="", help="Free-text search query (default: empty = browse/popularity order)")
    parser.add_argument("--category", default=None, choices=CATEGORIES, help="Apify store category filter")
    parser.add_argument("--length", type=int, default=24,
                         help="How many actors to return (also your research budget knob - combine with "
                              "--min-users/--max-users to get the top N *within a demand band* instead of overall)")
    parser.add_argument("--offset", type=int, default=0, help="Pagination offset")
    parser.add_argument("--min-users", type=int, default=None,
                         help="Skip actors with fewer total users than this (filters out no-traction noise)")
    parser.add_argument("--max-users", type=int, default=None,
                         help="Skip actors with more total users than this (filters out actors dominated by an "
                              "entrenched giant - hard to compete against a 50k+ user incumbent)")
    parser.add_argument("--min-runs", type=int, default=None, help="Skip actors with fewer total runs than this")
    parser.add_argument("--sort", choices=["default", "users", "runs", "rating", "runs_per_user"], default="default",
                         help="Client-side re-sort of the fetched page (the API itself returns relevance order, not "
                              "a numeric sort). 'runs_per_user' surfaces the 'few users but each runs it constantly' "
                              "pattern - a signal for underrated/high-value niches (e.g. an actor with 50 users and "
                              "200k runs is a much stronger signal than 50 users and 200 runs).")
    parser.add_argument("--output-dir", metavar="DIR", default="output",
                         help="Folder to write the result file into (default: ./output)")
    parser.add_argument("-o", "--output", metavar="FILE",
                         help="Write to this exact file instead of the default "
                              "output-dir/search-<CATEGORY>.json path")
    parser.add_argument("--json", action="store_true", help="Print raw JSON hits to stdout instead of writing a file")
    parser.add_argument("--table", action="store_true", help="Print a human-readable table to stdout instead of writing a file")
    parser.add_argument("--list-categories", action="store_true", help="Print the live category facet (name + actor count) and exit")
    args = parser.parse_args()

    if args.list_categories:
        facets, total = get_category_facets()
        print(f"prod_PUBLIC_STORE total actors: {total}\n")
        for cat, count in sorted(facets.items(), key=lambda x: -x[1]):
            print(f"{cat:<22} {count}")
        return

    data = search_store(query=args.query, category=args.category, length=args.length, offset=args.offset,
                         min_users=args.min_users, max_users=args.max_users, min_runs=args.min_runs)
    hits = data.get("hits", [])

    if args.sort == "users":
        hits.sort(key=lambda h: h.get("stats", {}).get("totalUsers", 0), reverse=True)
    elif args.sort == "runs":
        hits.sort(key=lambda h: h.get("stats", {}).get("totalRuns", 0), reverse=True)
    elif args.sort == "rating":
        hits.sort(key=lambda h: h.get("stats", {}).get("actorReviewRating", 0), reverse=True)
    elif args.sort == "runs_per_user":
        hits.sort(key=runs_per_user, reverse=True)

    band = ""
    if args.min_users is not None or args.max_users is not None:
        band = f" | band: {args.min_users or 0}-{args.max_users if args.max_users is not None else '∞'} users"
    summary = f"nbHits for this filter: {data.get('nbHits')} | showing {len(hits)} (offset {args.offset}){band}"

    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return

    if args.table:
        print(summary + "\n")
        for h in hits:
            print(format_row(h))
        return

    # Default: write a JSON file (overwriting any previous result for this
    # category/query) instead of printing.
    if args.output:
        path = args.output
    else:
        os.makedirs(args.output_dir, exist_ok=True)
        if args.category:
            fname = f"search-{args.category}.json"
        elif args.query:
            slug = re.sub(r"[^a-z0-9]+", "-", args.query.strip().lower()).strip("-") or "query"
            fname = f"search-query-{slug}.json"
        else:
            fname = "search-default.json"
        path = os.path.join(args.output_dir, fname)

    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hits, f, ensure_ascii=False, indent=2)
    print(f"{summary} -> wrote {len(hits)} hits to {path}")


if __name__ == "__main__":
    main()
