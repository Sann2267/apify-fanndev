"""Standalone local runner -- exercises all 4 modes without the Apify platform.

Usage:
    python test_local.py channel <login> [<login> ...]
    python test_local.py videos <login> [limit]
    python test_local.py clips <login> [limit]
    python test_local.py schedule <login>
"""

import asyncio
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.client import IntegrityCheckFailed, TwitchClient
from src.extractor import (
    CHANNEL_QUERY,
    CLIPS_QUERY,
    SCHEDULE_QUERY,
    VIDEOS_QUERY,
    extract_channel,
    extract_clips,
    extract_error,
    extract_schedule,
    extract_videos,
)

DEFAULT_OPTS = {
    "videoSort": "TIME",
    "videoType": "ARCHIVE",
    "clipsPeriod": "ALL_TIME",
    "clipsSort": "VIEWS_DESC",
}


async def run_channel(logins: list[str]):
    for login in logins:
        client = TwitchClient()
        try:
            try:
                data = await client.graphql(CHANNEL_QUERY, {"login": login})
                record = extract_channel(data, login)
            except IntegrityCheckFailed as e:
                record = extract_error(login, "integrity_check_failed", repr(e))
            print(json.dumps(record, ensure_ascii=False, indent=2)[:1500], "...")
            print(f"-> _source={record.get('_source')} _error={record.get('_error')}")
        finally:
            await client.close()


async def run_videos(login: str, limit: int):
    client = TwitchClient()
    try:
        data = await client.graphql(
            VIDEOS_QUERY,
            {"login": login, "first": limit, "sort": DEFAULT_OPTS["videoSort"], "type": DEFAULT_OPTS["videoType"]},
        )
        records = extract_videos(data, login, limit)
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
        print(f"\n-> {len(records)} video(s)")
    finally:
        await client.close()


async def run_clips(login: str, limit: int):
    client = TwitchClient()
    try:
        data = await client.graphql(
            CLIPS_QUERY,
            {"login": login, "first": limit, "period": DEFAULT_OPTS["clipsPeriod"], "sort": DEFAULT_OPTS["clipsSort"]},
        )
        records = extract_clips(data, login, limit)
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
        print(f"\n-> {len(records)} clip(s)")
    finally:
        await client.close()


async def run_schedule(login: str):
    client = TwitchClient()
    try:
        data = await client.graphql(SCHEDULE_QUERY, {"login": login})
        records = extract_schedule(data, login)
        for r in records:
            print(json.dumps(r, ensure_ascii=False, indent=2)[:800], "...")
        print(f"\n-> {len(records)} segment(s)")
    finally:
        await client.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "channel"
    if mode == "channel":
        logins = sys.argv[2:] or ["shroud"]
        asyncio.run(run_channel(logins))
    elif mode == "videos":
        login = sys.argv[2] if len(sys.argv) > 2 else "shroud"
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        asyncio.run(run_videos(login, limit))
    elif mode == "clips":
        login = sys.argv[2] if len(sys.argv) > 2 else "shroud"
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        asyncio.run(run_clips(login, limit))
    elif mode == "schedule":
        login = sys.argv[2] if len(sys.argv) > 2 else "shroud"
        asyncio.run(run_schedule(login))
    else:
        print("Usage: python test_local.py [channel <login>... | videos <login> [limit] | clips <login> [limit] | schedule <login>]")
        sys.exit(1)
