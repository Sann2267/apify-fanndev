import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import InvalidRequest, LumaClient, NotFound, NotSignedIn
from src.constants import PERIOD_VALUES
from src.extractor import extract_error, extract_slug, wrap
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def run_event(raw_input: str, proxy_url: str | None) -> dict:
    slug = extract_slug(raw_input)
    if not slug:
        return extract_error(raw_input, "empty_input")

    client = LumaClient(proxy_url=proxy_url)
    try:
        resolved = await client.resolve_url(slug)
        kind = resolved.get("kind")
        if kind != "event":
            return extract_error(raw_input, "kind_mismatch", f"'{slug}' resolved to kind={kind!r}, not 'event'")
        return wrap(resolved["data"], raw_input)
    except NotFound as e:
        return extract_error(raw_input, "not_found", repr(e))
    except NotSignedIn as e:
        return extract_error(raw_input, "auth_required", repr(e))
    except InvalidRequest as e:
        return extract_error(raw_input, "invalid_request", repr(e))
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(raw_input, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def run_calendar(raw_input: str, period: str, max_items: int, proxy_url: str | None) -> list[dict]:
    slug = extract_slug(raw_input)
    if not slug:
        return [extract_error(raw_input, "empty_input")]

    client = LumaClient(proxy_url=proxy_url)
    try:
        resolved = await client.resolve_url(slug)
        kind = resolved.get("kind")
        if kind != "calendar":
            return [extract_error(raw_input, "kind_mismatch", f"'{slug}' resolved to kind={kind!r}, not 'calendar'")]

        data = resolved["data"]
        records = [wrap(data, raw_input, record_type="CALENDAR_PROFILE")]

        calendar_api_id = (data.get("calendar") or {}).get("api_id")
        if calendar_api_id:
            entries = await client.paginate_calendar(calendar_api_id, period, max_items)
            records.extend(wrap(entry, raw_input, record_type="CALENDAR_EVENT") for entry in entries)
        return records
    except NotFound as e:
        return [extract_error(raw_input, "not_found", repr(e))]
    except NotSignedIn as e:
        return [extract_error(raw_input, "auth_required", repr(e))]
    except InvalidRequest as e:
        return [extract_error(raw_input, "invalid_request", repr(e))]
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [extract_error(raw_input, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_discover(
    latitude: str | None, longitude: str | None, max_items: int, proxy_url: str | None
) -> list[dict]:
    input_desc = f"geo:{latitude},{longitude}" if latitude and longitude else "discover"
    client = LumaClient(proxy_url=proxy_url)
    try:
        entries = await client.paginate_discover(latitude, longitude, max_items)
        return [wrap(entry, input_desc) for entry in entries]
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [extract_error(input_desc, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "event")
        if mode not in ("event", "calendar", "discover"):
            raise input_error(f"Invalid mode: {mode!r}. Must be one of event/calendar/discover.")

        period = input_data.get("period", "future")
        if period not in PERIOD_VALUES:
            raise input_error(f"Invalid period: {period!r}. Must be one of {PERIOD_VALUES}.")

        max_items = int(input_data.get("maxItems", 100))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        if mode == "discover":
            proxy_url = await proxy_config.new_url() if proxy_config else None
            records = await run_discover(
                input_data.get("latitude"), input_data.get("longitude"), max_items, proxy_url
            )
            Actor.log.info(f"mode=discover: {len(records)} record(s), maxItems={max_items}")
            await Actor.push_data(records)
            return

        urls = list(input_data.get("urls") or [])
        if input_data.get("url"):
            urls.insert(0, input_data["url"])
        if not urls:
            raise input_error("Provide 'url' or 'urls' when mode is 'event' or 'calendar'.")
        # de-dupe while preserving order
        seen = set()
        urls = [u for u in urls if not (u in seen or seen.add(u))]

        max_concurrency = int(input_data.get("maxConcurrency", 4))
        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(u: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                if mode == "event":
                    record = await run_event(u, proxy_url)
                    await Actor.push_data(record)
                else:  # calendar
                    records = await run_calendar(u, period, max_items, proxy_url)
                    await Actor.push_data(records)

        Actor.log.info(f"mode={mode}: {len(urls)} url(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(u) for u in urls))
