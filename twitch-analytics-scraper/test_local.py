"""Standalone local runner -- exercises all 4 modes without the Apify platform.

Usage:
    python test_local.py top-games [limit]
    python test_local.py top-streams [limit]
    python test_local.py game-streams <gameName> [limit]
    python test_local.py channel-rank <login> [<login> ...]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import run_channel_rank, run_game_streams, run_top_games, run_top_streams


async def run_tg(limit: int):
    records = await run_top_games(limit, None)
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:500], "...")
    print(f"\n-> {len(records)} game(s)")


async def run_ts(limit: int):
    records = await run_top_streams(limit, None)
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:500], "...")
    print(f"\n-> {len(records)} stream(s)")


async def run_gs(game_name: str, limit: int):
    records = await run_game_streams(game_name, limit, None)
    for r in records:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:500], "...")
    print(f"\n-> {len(records)} stream(s)")


async def run_cr(logins: list[str]):
    for login in logins:
        record = await run_channel_rank(login, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:800], "...")
        print(f"-> _source={record.get('_source')} _error={record.get('_error')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "top-games"
    if mode == "top-games":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        asyncio.run(run_tg(limit))
    elif mode == "top-streams":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        asyncio.run(run_ts(limit))
    elif mode == "game-streams":
        game_name = sys.argv[2] if len(sys.argv) > 2 else "Just Chatting"
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        asyncio.run(run_gs(game_name, limit))
    elif mode == "channel-rank":
        logins = sys.argv[2:] or ["shroud"]
        asyncio.run(run_cr(logins))
    else:
        print(__doc__)
        sys.exit(1)
