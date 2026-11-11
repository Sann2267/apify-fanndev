import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import NotFound, PartifulClient
from src.extractor import extract_error, extract_id, strip_noise, wrap
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def run_event(raw_input: str, proxy_url: str | None) -> dict:
    event_id = extract_id(raw_input, "e")
    if not event_id:
        return extract_error(raw_input, "empty_input")

    client = PartifulClient(proxy_url=proxy_url)
    try:
        page_props = await client.get_event(event_id)
        if not page_props.get("event"):
            return extract_error(raw_input, "not_found", f"'{event_id}' has no event object in pageProps")
        return wrap(strip_noise(page_props), raw_input)
    except NotFound as e:
        return extract_error(raw_input, "not_found", repr(e))
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(raw_input, "blocked_or_transient", repr(e))
    finally:
        await client.close()
    # UnexpectedShape (site markup changed) is intentionally NOT caught
    # here -- it must propagate and crash the run per
    # .ai/conventions/error-handling.md Category 3.


async def run_host(raw_input: str, max_items: int, proxy_url: str | None) -> list[dict]:
    user_id = extract_id(raw_input, "u")
    if not user_id:
        return [extract_error(raw_input, "empty_input")]

    client = PartifulClient(proxy_url=proxy_url)
    try:
        page_props = await client.get_host(user_id)
        if not page_props.get("user"):
            return [extract_error(raw_input, "not_found", f"'{user_id}' has no user object in pageProps")]

        published = page_props.get("initialPublishedEvents")
        profile = {k: v for k, v in strip_noise(page_props).items() if k != "initialPublishedEvents"}
        if not isinstance(published, list):
            # Real, legitimate platform limit -- most hosts haven't opted
            # into a public event list, not a bug on our end. See
            # CRAWLING_METHOD.md.
            profile["_warning"] = "host_has_no_public_event_list"
        records = [wrap(profile, raw_input, record_type="HOST_PROFILE")]

        if isinstance(published, list):
            records.extend(
                wrap(item, raw_input, record_type="HOST_EVENT") for item in published[:max_items]
            )
        return records
    except NotFound as e:
        return [extract_error(raw_input, "not_found", repr(e))]
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [extract_error(raw_input, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_discover(regions: list[str], max_items: int, proxy_url: str | None) -> list[dict]:
    input_desc = f"discover:{','.join(regions)}" if regions else "discover"
    client = PartifulClient(proxy_url=proxy_url)
    try:
        page_props = await client.get_discover()
        sections = page_props.get("trendingSections") or {}
        records = []
        for region_key, section in sections.items():
            if regions and region_key not in regions:
                continue
            for item in section.get("items") or []:
                event = item.get("event")
                if not event:
                    continue
                enriched = {**event, "region": region_key, "regionTitle": section.get("title")}
                records.append(wrap(enriched, input_desc, record_type="DISCOVER_EVENT"))
        return records[:max_items]
    except (RuntimeError, ConnectionError, RequestException) as e:
        return [extract_error(input_desc, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "event")
        if mode not in ("event", "host", "discover"):
            raise input_error(f"Invalid mode: {mode!r}. Must be one of event/host/discover.")

        max_items = int(input_data.get("maxItems", 100))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        if mode == "discover":
            regions = list(input_data.get("regions") or [])
            proxy_url = await proxy_config.new_url() if proxy_config else None
            records = await run_discover(regions, max_items, proxy_url)
            Actor.log.info(f"mode=discover: {len(records)} record(s), regions={regions or 'all'}, maxItems={max_items}")
            await Actor.push_data(records)
            return

        urls = list(input_data.get("urls") or [])
        if input_data.get("url"):
            urls.insert(0, input_data["url"])
        if not urls:
            raise input_error("Provide 'url' or 'urls' when mode is 'event' or 'host'.")
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
                else:  # host
                    records = await run_host(u, max_items, proxy_url)
                    await Actor.push_data(records)

        Actor.log.info(f"mode={mode}: {len(urls)} url(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(u) for u in urls))
