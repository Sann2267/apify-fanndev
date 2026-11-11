import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import IntegrityCheckFailed, TwitchClient
from src.constants import (
    CLIPS_PERIOD_VALUES,
    CLIPS_SORT_VALUES,
    MAX_FIRST,
    VIDEO_SORT_VALUES,
    VIDEO_TYPE_VALUES,
)
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
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def process_login(mode: str, login: str, opts: dict, proxy_url: str | None) -> list[dict]:
    client = TwitchClient(proxy_url=proxy_url)
    try:
        return await _dispatch(client, mode, login, opts)
    except IntegrityCheckFailed as e:
        return [extract_error(login, "integrity_check_failed", repr(e))]
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [extract_error(login, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def _dispatch(client: TwitchClient, mode: str, login: str, opts: dict) -> list[dict]:
    if mode == "channel":
        data = await client.graphql(CHANNEL_QUERY, {"login": login})
        return [extract_channel(data, login)]

    if mode == "videos":
        first = min(int(opts.get("limit", 20)), MAX_FIRST)
        data = await client.graphql(
            VIDEOS_QUERY,
            {
                "login": login,
                "first": first,
                "sort": opts.get("videoSort", "TIME"),
                "type": opts.get("videoType", "ARCHIVE"),
            },
        )
        return extract_videos(data, login, first)

    if mode == "clips":
        first = min(int(opts.get("limit", 20)), MAX_FIRST)
        data = await client.graphql(
            CLIPS_QUERY,
            {
                "login": login,
                "first": first,
                "period": opts.get("clipsPeriod", "ALL_TIME"),
                "sort": opts.get("clipsSort", "VIEWS_DESC"),
            },
        )
        return extract_clips(data, login, first)

    if mode == "schedule":
        data = await client.graphql(SCHEDULE_QUERY, {"login": login})
        return extract_schedule(data, login)

    raise ValueError(f"Unknown mode: {mode}")


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "channel")
        if mode not in ("channel", "videos", "clips", "schedule"):
            raise input_error(f"Invalid mode: {mode!r}. Must be one of channel/videos/clips/schedule.")

        if input_data.get("videoSort") and input_data["videoSort"] not in VIDEO_SORT_VALUES:
            raise input_error(f"Invalid videoSort: {input_data['videoSort']!r}. Must be one of {VIDEO_SORT_VALUES}.")
        if input_data.get("videoType") and input_data["videoType"] not in VIDEO_TYPE_VALUES:
            raise input_error(f"Invalid videoType: {input_data['videoType']!r}. Must be one of {VIDEO_TYPE_VALUES}.")
        if input_data.get("clipsPeriod") and input_data["clipsPeriod"] not in CLIPS_PERIOD_VALUES:
            raise input_error(f"Invalid clipsPeriod: {input_data['clipsPeriod']!r}. Must be one of {CLIPS_PERIOD_VALUES}.")
        if input_data.get("clipsSort") and input_data["clipsSort"] not in CLIPS_SORT_VALUES:
            raise input_error(f"Invalid clipsSort: {input_data['clipsSort']!r}. Must be one of {CLIPS_SORT_VALUES}.")

        logins = list(input_data.get("logins") or [])
        if input_data.get("login"):
            logins.insert(0, input_data["login"])
        if not logins:
            raise input_error("Provide 'login' or 'logins'.")
        # de-dupe while preserving order
        seen = set()
        logins = [l for l in logins if not (l in seen or seen.add(l))]

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        max_concurrency = int(input_data.get("maxConcurrency", 4))
        sem = asyncio.Semaphore(max_concurrency)

        opts = {
            "limit": input_data.get("limit", 20),
            "videoSort": input_data.get("videoSort", "TIME"),
            "videoType": input_data.get("videoType", "ARCHIVE"),
            "clipsPeriod": input_data.get("clipsPeriod", "ALL_TIME"),
            "clipsSort": input_data.get("clipsSort", "VIEWS_DESC"),
        }

        async def _bounded(login: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                records = await process_login(mode, login, opts, proxy_url)
                await Actor.push_data(records)

        Actor.log.info(f"mode={mode}: {len(logins)} channel(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(l) for l in logins))
