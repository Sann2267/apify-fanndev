"""Standalone local runner -- exercises the scraper without the Apify platform.

Usage:
    python test_local.py list [--tahun YYYY] [--kategori ID] [--instansi ID]
                               [--rekanan NAME] [--max N] [--detail]
    python test_local.py detail <kode> [<kode> ...]
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
        tahun = None
        if "--tahun" in args:
            tahun = int(args[args.index("--tahun") + 1])
        kategori_id = args[args.index("--kategori") + 1] if "--kategori" in args else ""
        instansi_id = args[args.index("--instansi") + 1] if "--instansi" in args else ""
        rekanan = args[args.index("--rekanan") + 1] if "--rekanan" in args else ""
        max_results = 10
        if "--max" in args:
            max_results = int(args[args.index("--max") + 1])
        fetch_detail = "--detail" in args
        records = await run_list(tahun, kategori_id, instansi_id, rekanan, max_results, fetch_detail, _null_proxy)
        print(
            f"=== list tahun={tahun} kategoriId={kategori_id!r} instansiId={instansi_id!r} rekanan={rekanan!r} "
            f"fetchDetail={fetch_detail} -> {len(records)} record(s) ==="
        )
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more")

    elif args[0] == "detail":
        kodes = args[1:]
        if not kodes:
            print("Usage: python test_local.py detail <kode> [<kode> ...]")
            sys.exit(1)
        records = await run_detail(kodes, 2, _null_proxy)
        print(f"=== detail -> {len(records)} record(s) ===")
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
