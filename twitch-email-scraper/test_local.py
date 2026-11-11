"""Standalone local runner -- exercises both modes without the Apify platform.

Usage:
    python test_local.py channel <login> [<login> ...]
    python test_local.py by-game <gameName> [limit]
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.main import discover_game_channels, run_channel_email


async def run_c(logins: list[str]):
    for login in logins:
        record = await run_channel_email(login, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:1000], "...")
        print(f"-> emailFound={record.get('emailFound')} _error={record.get('_error')}")


async def run_g(game_name: str, limit: int):
    logins = await discover_game_channels(game_name, limit, None)
    print(f"discovered {len(logins)} channels: {logins}")
    for login in logins[:5]:
        record = await run_channel_email(login, None)
        print(json.dumps(record, ensure_ascii=False, indent=2)[:500], "...")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "channel"
    if mode == "channel":
        logins = sys.argv[2:] or ["pokimane"]
        asyncio.run(run_c(logins))
    elif mode == "by-game":
        game_name = sys.argv[2] if len(sys.argv) > 2 else "Just Chatting"
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        asyncio.run(run_g(game_name, limit))
    else:
        print(__doc__)
        sys.exit(1)
