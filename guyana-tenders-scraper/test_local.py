"""Standalone local runner -- exercises the list (+ optional detail) flow and
the standalone detail flow without the Apify platform.

Usage:
    python test_local.py list [maxItems] [--detail]
    python test_local.py detail <projectId>
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import GuyanaEprocureClient
from src.extractor import (
    FrappeApiError,
    UnexpectedShape,
    build_error,
    build_record,
    normalize_detail,
    normalize_list_row,
)


async def run_list(max_items: int, fetch_detail: bool):
    client = GuyanaEprocureClient()
    try:
        raw_rows = await client.fetch_bid_opportunities()
        rows = [normalize_list_row(r) for r in raw_rows][:max_items]
        print(f"{len(rows)} currently advertised bid opportunities (upstream is unpaginated -- this is the complete list)")

        if fetch_detail:
            for row in rows:
                pid = row.get("project_id")
                try:
                    row["_detail"] = normalize_detail(await client.fetch_project_advertisement(pid)) if pid else None
                except (FrappeApiError, UnexpectedShape) as e:
                    row["_detail"] = None
                    row["_detailError"] = repr(e)

        source = "S1-json-api-detail" if fetch_detail else "S1-json-api"
        for row in rows[:5]:
            print(" -", json.dumps(row, ensure_ascii=False)[:200])
        if len(rows) > 5:
            print(f"   ... {len(rows) - 5} more")
        print("\n=== full record sample ===")
        for row in rows[:2]:
            print(json.dumps(build_record(source, row), ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps(build_error("blocked_or_transient", repr(e)), ensure_ascii=False))
    finally:
        await client.close()


async def run_detail(project_id: str):
    client = GuyanaEprocureClient()
    try:
        raw_detail = await client.fetch_project_advertisement(project_id)
        record = build_record("S1-json-api-detail", normalize_detail(raw_detail))
        print(json.dumps(record, ensure_ascii=False, indent=2))
    except FrappeApiError as e:
        print(json.dumps(build_error("not_found", repr(e)), ensure_ascii=False))
    except Exception as e:
        print(json.dumps(build_error("blocked_or_transient", repr(e)), ensure_ascii=False))
    finally:
        await client.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    detail_flag = "--detail" in sys.argv[1:]
    if not args or args[0] not in ("list", "detail"):
        print(__doc__)
        sys.exit(1)

    if args[0] == "list":
        max_items = int(args[1]) if len(args) > 1 else 50
        asyncio.run(run_list(max_items, detail_flag))
    else:
        if len(args) < 2:
            print("usage: python test_local.py detail <projectId>")
            sys.exit(1)
        asyncio.run(run_detail(args[1]))
