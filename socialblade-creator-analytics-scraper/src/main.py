import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import NotFound, SocialBladeClient
from src.constants import (
    MODES,
    PLATFORMS,
    TOP_MAX_CREATORS,
    TOP_PATH,
    TOP_SIZES,
)
from src.extractor import (
    absolute,
    extract_error,
    parse_target,
    parse_profile,
    parse_top,
    wrap,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (RuntimeError, ConnectionError, RequestException)


async def run_profile(raw_input: str, default_platform: str, proxy_url: str | None) -> dict:
    if not (raw_input or "").strip():
        return extract_error(raw_input, "empty_input")
    platform, path = parse_target(raw_input, default_platform)
    if platform not in PLATFORMS:
        return extract_error(
            raw_input,
            "unsupported_platform",
            f"{platform!r} is not one of {PLATFORMS} (Facebook profiles return 404 upstream)",
        )

    client = SocialBladeClient(proxy_url=proxy_url)
    try:
        html = await client.get_html(path)
        data = parse_profile(html, platform, absolute(path))
        if not data:
            return extract_error(raw_input, "not_found", f"no {platform} creator payload at {path}")
        return wrap(data, raw_input, record_type="CREATOR_PROFILE")
    except NotFound as e:
        return extract_error(raw_input, "not_found", str(e))
    except TRANSIENT as e:
        return extract_error(raw_input, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def run_top(size: int, max_items: int, proxy_url: str | None) -> list[dict]:
    label = f"top:youtube/{size}"
    client = SocialBladeClient(proxy_url=proxy_url)
    try:
        html = await client.get_html(TOP_PATH.format(size=size))
        rows = parse_top(html, "youtube")
        if not rows:
            return [extract_error(label, "empty_list", "no creators in the server-rendered payload")]
        return [wrap(r, label, record_type="TOP_CREATOR") for r in rows[:max_items]]
    except NotFound as e:
        return [
            extract_error(
                label, "not_found", f"{e} -- supported sizes are {TOP_SIZES}"
            )
        ]
    except TRANSIENT as e:
        return [extract_error(label, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "profile")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def new_proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        if mode == "top":
            size = int(input_data.get("topSize", 100))
            if size not in TOP_SIZES:
                raise input_error(f"Invalid topSize: {size}. Upstream only accepts {TOP_SIZES}.")
            max_items = min(int(input_data.get("maxItems", TOP_MAX_CREATORS)), TOP_MAX_CREATORS)
            records = await run_top(size, max_items, await new_proxy_url())
            Actor.log.info(f"mode=top size={size}: {len(records)} record(s)")
            await Actor.push_data(records)
            return

        # mode == "profile"
        platform = (input_data.get("platform") or "youtube").strip().lower()
        if platform not in PLATFORMS:
            raise input_error(f"Invalid platform: {platform!r}. Must be one of {PLATFORMS}.")

        handles = list(input_data.get("handles") or [])
        if input_data.get("handle"):
            handles.insert(0, input_data["handle"])
        if not handles:
            raise input_error("Provide 'handle' or 'handles' when mode is 'profile'.")
        seen = set()
        handles = [h for h in handles if not (h in seen or seen.add(h))]

        max_concurrency = int(input_data.get("maxConcurrency", 4))
        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(h: str):
            async with sem:
                record = await run_profile(h, platform, await new_proxy_url())
                await Actor.push_data(record)

        Actor.log.info(
            f"mode=profile platform={platform}: {len(handles)} handle(s), maxConcurrency={max_concurrency}"
        )
        await asyncio.gather(*(_bounded(h) for h in handles))
