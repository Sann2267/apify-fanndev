"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py list [--estado X] [--modalidad Y] [--unidad-compra N]
                               [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
                               [--proceso CODE] [--max N] [--detail]
    python test_local.py detail <codigo_proceso> [<codigo_proceso> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_detail, run_list


async def _null_proxy():
    return None


async def run(args: list[str]):
    if not args:
        print(__doc__)
        sys.exit(1)

    if args[0] == "list":
        estado = ""
        if "--estado" in args:
            estado = args[args.index("--estado") + 1]
        modalidad = ""
        if "--modalidad" in args:
            modalidad = args[args.index("--modalidad") + 1]
        unidad_compra = None
        if "--unidad-compra" in args:
            unidad_compra = int(args[args.index("--unidad-compra") + 1])
        start_date = ""
        if "--start-date" in args:
            start_date = args[args.index("--start-date") + 1]
        end_date = ""
        if "--end-date" in args:
            end_date = args[args.index("--end-date") + 1]
        proceso_code = ""
        if "--proceso" in args:
            proceso_code = args[args.index("--proceso") + 1]
        max_results = 10
        if "--max" in args:
            max_results = int(args[args.index("--max") + 1])
        fetch_detail = "--detail" in args

        records = await run_list(
            estado, modalidad, unidad_compra, None, None,
            start_date, end_date, proceso_code, max_results, fetch_detail, _null_proxy,
        )
        print(
            f"=== list estado={estado!r} modalidad={modalidad!r} startDate={start_date!r} "
            f"endDate={end_date!r} fetchDetail={fetch_detail} -> {len(records)} record(s) ==="
        )
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")

    elif args[0] == "detail":
        codigos = args[1:]
        if not codigos:
            print("Usage: python test_local.py detail <codigo_proceso> [<codigo_proceso> ...]")
            sys.exit(1)
        records = await run_detail(codigos, 2, _null_proxy)
        print(f"=== detail -> {len(records)} record(s) ===")
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
