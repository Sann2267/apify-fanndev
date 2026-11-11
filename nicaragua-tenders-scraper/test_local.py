"""Standalone local runner -- exercises the search flow without the Apify
platform.

Usage:
    python test_local.py search [maxResults] [estado]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import SiscaeClient
from src.constants import ESTADO_VALUES
from src.extractor import build_list_record


async def run_search(max_results: int, estado_key: str):
    estado = ESTADO_VALUES.get(estado_key, "VIGENTE")
    client = SiscaeClient()
    try:
        rows, filters_used = await client.search(estados=[estado], resultados_items="CINCUENTA")
    finally:
        await client.close()

    print(f"\n=== search estados=[{estado}] -> {len(rows)} procedure(s) ===")
    for row in rows[:5]:
        print(" -", row["tipoProcedimiento"], row["numeroProcedimiento"], "|", row["institucion"], "|", row["estado"])
    if len(rows) > 5:
        print(f"   ... {len(rows) - 5} more")

    for row in rows[: min(2, max_results)]:
        record = build_list_record(row, filters_used)
        print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] != "search":
        print(__doc__)
        sys.exit(1)

    max_results = int(args[1]) if len(args) > 1 else 10
    estado_key = args[2] if len(args) > 2 else "vigente"
    asyncio.run(run_search(max_results, estado_key))
