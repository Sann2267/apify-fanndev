"""Local smoke test for the klikindomaret actor (no Apify platform needed).

Runs each mode directly against the WAF manager + client, printing record
counts and a sample. Usage:
    python test_local.py [mode] [--full]
Modes: token, stores, categoryTree, searchSuggestions, promoBanners, productSearch
'--full' lets paginated modes run to completion instead of capping.
"""

import asyncio
import json
import logging
import sys

from src.client import KlikClient
from src.modes import (
    resolve_store,
    run_category_tree,
    run_product_search,
    run_promo_banners,
    run_stores,
    run_suggestions,
)
from src.waf import WafManager, mint_aws_token

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def collect(stream, cap):
    rows = []
    async for r in stream:
        rows.append(r)
        if cap and len(rows) >= cap:
            break
    return rows


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "categoryTree"
    full = "--full" in sys.argv
    cap = 0 if full else 25

    if mode == "token":
        tok = await mint_aws_token()
        print("token len:", len(tok), "::", tok[:60])
        return

    waf = WafManager()
    client = KlikClient(waf)
    await waf.ensure_aws_token()
    try:
        if mode == "stores":
            rows = await collect(run_stores(client, ["141100100"]), cap)
        else:
            store = await resolve_store(client, None, None, None, None)
            print("store:", store)
            if mode == "categoryTree":
                rows = await collect(run_category_tree(client, store), cap)
            elif mode == "searchSuggestions":
                rows = await collect(run_suggestions(client, store), cap)
            elif mode == "promoBanners":
                rows = await collect(run_promo_banners(client, store, cap), cap)
            elif mode == "productSearch":
                queries = [{"type": "keyword", "value": "indomie", "label": "indomie"}]
                rows = await collect(run_product_search(client, store, queries, cap), cap)
            else:
                print("unknown mode", mode)
                return
        print(f"\n=== {mode}: {len(rows)} record(s) ===")
        if rows:
            print(json.dumps(rows[0], ensure_ascii=False, indent=2)[:1200])
            types = {}
            for r in rows:
                types[r.get("recordType", "?")] = types.get(r.get("recordType", "?"), 0) + 1
            print("recordType counts:", types)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
