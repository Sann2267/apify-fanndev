"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py list [--tipo convNacional|convInternacional] [--entidad X]
                               [--objeto Y] [--all] [--max N]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_list


async def _null_proxy():
    return None


async def run(args: list[str]):
    if not args or args[0] != "list":
        print(__doc__)
        sys.exit(1)

    tipo = "convNacional"
    if "--tipo" in args:
        tipo = args[args.index("--tipo") + 1]
    entidad = ""
    if "--entidad" in args:
        entidad = args[args.index("--entidad") + 1]
    objeto = ""
    if "--objeto" in args:
        objeto = args[args.index("--objeto") + 1]
    solo_vigentes = "--all" not in args
    max_results = 10
    if "--max" in args:
        max_results = int(args[args.index("--max") + 1])

    records = await run_list(
        tipo, max_results, entidad, objeto, solo_vigentes, ("B", "O", "S", "C"), _null_proxy
    )
    print(
        f"=== list tipo={tipo} entidad={entidad!r} objeto={objeto!r} soloVigentes={solo_vigentes} "
        f"-> {len(records)} record(s) ==="
    )
    for r in records[:5]:
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    if len(records) > 5:
        print(f"... and {len(records) - 5} more")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
