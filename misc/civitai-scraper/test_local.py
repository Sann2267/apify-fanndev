"""Standalone local runner -- exercises all 5 modes without the Apify platform.

Usage:
    python test_local.py models [query] [limit]
    python test_local.py model-detail <modelId> [<modelId> ...]
    python test_local.py images [modelId] [limit]
    python test_local.py creators [query] [limit]
    python test_local.py tags [query] [limit]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_creators, run_images, run_model_detail, run_models_search, run_tags


async def run_models(query: str | None, limit: int):
    input_data = {"query": query} if query else {}
    records = await run_models_search(input_data, limit, None)
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
    print(f"\n-> {len(records)} model(s)")


async def run_detail(model_ids: list[str]):
    for mid in model_ids:
        record = await run_model_detail(mid, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:1500], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


async def run_imgs(model_id: str | None, limit: int):
    input_data = {"modelId": int(model_id)} if model_id else {}
    records = await run_images(input_data, limit, None)
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
    print(f"\n-> {len(records)} image(s)")


async def run_creat(query: str | None, limit: int):
    input_data = {"query": query} if query else {}
    records = await run_creators(input_data, limit, None)
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:400], "...")
    print(f"\n-> {len(records)} creator(s)")


async def run_tgs(query: str | None, limit: int):
    input_data = {"query": query} if query else {}
    records = await run_tags(input_data, limit, None)
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:400], "...")
    print(f"\n-> {len(records)} tag(s)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "models"
    if mode == "models":
        query = sys.argv[2] if len(sys.argv) > 2 else None
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        asyncio.run(run_models(query, limit))
    elif mode == "model-detail":
        ids = sys.argv[2:] or ["4201"]
        asyncio.run(run_detail(ids))
    elif mode == "images":
        model_id = sys.argv[2] if len(sys.argv) > 2 else None
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        asyncio.run(run_imgs(model_id, limit))
    elif mode == "creators":
        query = sys.argv[2] if len(sys.argv) > 2 else None
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        asyncio.run(run_creat(query, limit))
    elif mode == "tags":
        query = sys.argv[2] if len(sys.argv) > 2 else None
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        asyncio.run(run_tgs(query, limit))
    else:
        print("Usage: python test_local.py [models [query] [limit] | model-detail <id>... | images [modelId] [limit] | creators [query] [limit] | tags [query] [limit]]")
        sys.exit(1)
