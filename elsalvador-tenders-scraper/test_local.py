"""Standalone local runner -- exercises the open/awarded/detail flow without
the Apify platform.

Usage:
    python test_local.py open [maxResults] [entidad]
    python test_local.py awarded [maxResults] [entidad]
    python test_local.py detail <processId>
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import ComprasalClient
from src.extractor import (
    UnexpectedShape,
    build_awarded_record,
    build_detail_record,
    build_open_record,
    parse_awarded_response,
    parse_detail_response,
    parse_institutions_response,
    parse_open_response,
    resolve_institution_id,
)


async def run_open(max_results: int, entidad: str | None):
    client = ComprasalClient()
    try:
        institucion_id = None
        if entidad:
            institutions = parse_institutions_response(await client.fetch_institutions())
            institucion_id = resolve_institution_id(institutions, entidad)
            print(f"resolved entidad={entidad!r} -> institucion_id={institucion_id}")

        payload = await client.fetch_open(institucion_id=institucion_id)
        rows = parse_open_response(payload)
    finally:
        await client.close()

    print(f"\n=== open entidad={entidad!r} -> {len(rows)} process(es) total ===")
    for row in rows[:5]:
        print(" -", row.get("codigo_proceso"), "|", row.get("institucion"), "|", row.get("estado_actual"))
    if len(rows) > 5:
        print(f"   ... {len(rows) - 5} more")

    for row in rows[:max_results][:2]:
        record = build_open_record(row, {"entidad": entidad, "institucionId": institucion_id})
        print(json.dumps(record, ensure_ascii=False, indent=2)[:2000])


async def run_awarded(max_results: int, entidad: str | None):
    client = ComprasalClient()
    needle = (entidad or "").strip().lower()
    matched = []
    try:
        page = 1
        while len(matched) < max_results and page <= 20:
            payload = await client.fetch_awarded_page(page, 50)
            rows = parse_awarded_response(payload)
            if not rows:
                break
            for row in rows:
                if needle and needle not in ((row.get("institucion") or {}).get("nombre") or "").lower():
                    continue
                matched.append(row)
                if len(matched) >= max_results:
                    break
            page += 1
    finally:
        await client.close()

    print(f"\n=== awarded entidad={entidad!r} -> {len(matched)} matched (scanned {page} page(s)) ===")
    for row in matched[:5]:
        inst = (row.get("institucion") or {}).get("nombre")
        proc = row.get("proceso_compra") or {}
        print(" -", proc.get("codigo_proceso"), "|", inst, "| monto:", row.get("monto"))
    if len(matched) > 5:
        print(f"   ... {len(matched) - 5} more")

    for row in matched[:2]:
        record = build_awarded_record(row, {"entidad": entidad})
        print(json.dumps(record, ensure_ascii=False, indent=2)[:2000])


async def run_detail(process_id: str):
    client = ComprasalClient()
    try:
        payload = await client.fetch_detail(process_id)
        try:
            detail = parse_detail_response(payload)
        except UnexpectedShape as e:
            print(f"UnexpectedShape: {e}")
            return
        record = build_detail_record(process_id, detail)
        print(json.dumps(record, ensure_ascii=False, indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    if args[0] == "open":
        max_results = int(args[1]) if len(args) > 1 else 10
        entidad = args[2] if len(args) > 2 else None
        asyncio.run(run_open(max_results, entidad))
    elif args[0] == "awarded":
        max_results = int(args[1]) if len(args) > 1 else 10
        entidad = args[2] if len(args) > 2 else None
        asyncio.run(run_awarded(max_results, entidad))
    elif args[0] == "detail":
        if len(args) < 2:
            print("Usage: python test_local.py detail <processId>")
            sys.exit(1)
        asyncio.run(run_detail(args[1]))
    else:
        print(__doc__)
        sys.exit(1)
