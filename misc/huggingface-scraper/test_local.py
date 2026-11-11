"""Standalone local runner -- exercises all 7 modes without the Apify platform.

Usage:
    python test_local.py models [search] [limit]
    python test_local.py model-detail <id> [<id> ...]
    python test_local.py datasets [search] [limit]
    python test_local.py dataset-detail <id> [<id> ...]
    python test_local.py spaces [search] [limit]
    python test_local.py space-detail <id> [<id> ...]
    python test_local.py creator <username> [accountType]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_creator, run_detail, run_list


async def run_l(entity: str, search: str | None, limit: int):
    input_data = {"search": search} if search else {}
    records = await run_list(entity, input_data, limit, None)
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
    print(f"\n-> {len(records)} {entity} record(s)")


async def run_d(entity: str, ids: list[str]):
    for rid in ids:
        record = await run_detail(entity, rid, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:1500], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


async def run_c(username: str, account_type: str):
    record = await run_creator(username, account_type, None)
    print(json.dumps(record, ensure_ascii=False, indent=2)[:1200], "...")
    print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "models"
    if mode in ("models", "datasets", "spaces"):
        search = sys.argv[2] if len(sys.argv) > 2 else None
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        asyncio.run(run_l(mode, search, limit))
    elif mode == "model-detail":
        asyncio.run(run_d("models", sys.argv[2:] or ["google-bert/bert-base-uncased"]))
    elif mode == "dataset-detail":
        asyncio.run(run_d("datasets", sys.argv[2:] or ["rajpurkar/squad"]))
    elif mode == "space-detail":
        asyncio.run(run_d("spaces", sys.argv[2:] or ["enzostvs/deepsite"]))
    elif mode == "creator":
        username = sys.argv[2] if len(sys.argv) > 2 else "huggingface"
        account_type = sys.argv[3] if len(sys.argv) > 3 else "auto"
        asyncio.run(run_c(username, account_type))
    else:
        print(__doc__)
        sys.exit(1)
