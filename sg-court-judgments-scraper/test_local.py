"""Standalone local runner -- exercises both modes without the Apify platform.

Usage:
    python test_local.py search [searchPhrase] [year] [maxResults] [fetchFullText(0/1)]
    python test_local.py judgment <judgmentId> [<judgmentId> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_judgment, run_search


def _preview(rec: dict, limit: int = 900) -> str:
    trimmed = dict(rec)
    if isinstance(trimmed.get("fullText"), str):
        ft = trimmed["fullText"]
        trimmed["fullText"] = ft[:200] + f"... [{len(ft)} chars total]"
    return json.dumps(trimmed, ensure_ascii=False, indent=2)[:limit]


async def run_s(search_phrase: str, year: str, max_results: int, fetch_full_text: bool):
    records = await run_search(search_phrase, year, "DateOfDecision", False, max_results, fetch_full_text, 4, None)
    for r in records[:4]:
        print(_preview(r), "...")
    sources: dict = {}
    for r in records:
        sources[r.get("_source")] = sources.get(r.get("_source"), 0) + 1
    warned = sum(1 for r in records if r.get("_warning"))
    print(f"\n-> {len(records)} record(s); by _source: {sources}; with _warning: {warned}")


async def run_j(judgment_ids: list[str]):
    for jid in judgment_ids:
        record = await run_judgment(jid, None)
        print(_preview(record, 1600), "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')} "
              f"fullTextLength={record.get('fullTextLength')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "search"
    if mode == "search":
        search_phrase = sys.argv[2] if len(sys.argv) > 2 else "negligence"
        year = sys.argv[3] if len(sys.argv) > 3 else "All"
        max_results = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        fetch_full_text = bool(int(sys.argv[5])) if len(sys.argv) > 5 else False
        asyncio.run(run_s(search_phrase, year, max_results, fetch_full_text))
    elif mode == "judgment":
        judgment_ids = sys.argv[2:] or ["2026_SGHC_175"]
        asyncio.run(run_j(judgment_ids))
    else:
        print(__doc__)
        sys.exit(1)
