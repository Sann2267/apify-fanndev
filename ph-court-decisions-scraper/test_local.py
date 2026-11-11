"""Standalone local runner -- exercises all three modes without the Apify platform.

Usage:
    python test_local.py search <query> [corpus] [maxResults] [fetchFullText(0/1)] [searchType]
    python test_local.py browse <fromYear> <toYear> [maxResults] [fetchFullText(0/1)]
    python test_local.py decision <docId> [<docId> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_browse, run_decision, run_search


def _preview(rec: dict, limit: int = 1000) -> str:
    trimmed = dict(rec)
    for key in ("fullText", "snippet"):
        value = trimmed.get(key)
        if isinstance(value, str) and len(value) > 200:
            trimmed[key] = value[:200] + f"... [{len(value)} chars total]"
    return json.dumps(trimmed, ensure_ascii=False, indent=2)[:limit]


def _summarise(records: list[dict]):
    for r in records[:3]:
        print(_preview(r), "...")
    sources: dict = {}
    for r in records:
        sources[r.get("_source")] = sources.get(r.get("_source"), 0) + 1
    warned = sum(1 for r in records if r.get("_warning"))
    errored = sum(1 for r in records if r.get("_error"))
    print(f"\n-> {len(records)} record(s); by _source: {sources}; _warning: {warned}; _error: {errored}")
    return records


async def run_s(query, corpus, max_results, full_text, search_type):
    records = await run_search(query, corpus, search_type, max_results, full_text, 4, None)
    return _summarise(records)


async def run_b(from_year, to_year, max_results, full_text):
    records = await run_browse(from_year, to_year, max_results, full_text, 4, None)
    return _summarise(records)


async def run_d(doc_ids):
    for doc_id in doc_ids:
        record = await run_decision(doc_id, None)
        print(_preview(record, 1800), "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')} "
              f"fullTextLength={record.get('fullTextLength')}\n")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "search"
    if mode == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else "negligence"
        corpus = sys.argv[3] if len(sys.argv) > 3 else "sc_decision"
        max_results = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        full_text = bool(int(sys.argv[5])) if len(sys.argv) > 5 else False
        search_type = sys.argv[6] if len(sys.argv) > 6 else "anywords"
        asyncio.run(run_s(query, corpus, max_results, full_text, search_type))
    elif mode == "browse":
        from_year = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
        to_year = int(sys.argv[3]) if len(sys.argv) > 3 else from_year
        max_results = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        full_text = bool(int(sys.argv[5])) if len(sys.argv) > 5 else False
        asyncio.run(run_b(from_year, to_year, max_results, full_text))
    elif mode == "decision":
        asyncio.run(run_d(sys.argv[2:] or ["70008"]))
    else:
        print(__doc__)
        sys.exit(1)
