"""Mode dispatch for the ecommerce platform market-share Actor.

Every mode reads the same report page, so a run that asks for growth, breakdown
and migration on one platform still costs one request per platform.
"""

import asyncio
import logging
import re

from apify import Actor

from src.client import BlockedUpstream, ReportNotFound, StoreLeadsClient
from src.constants import (
    BREAKDOWN_SECTIONS,
    GROWTH_SECTION,
    MIGRATION_SECTIONS,
    MODES,
    STORE_SECTIONS,
    URL_REPORT,
    URL_REPORT_INDEX,
)
from src.extractor import (
    dedupe_rows,
    extract_error,
    js_codes,
    parse_js_vars,
    parse_section_rows,
    wrap_available,
    wrap_breakdown,
    wrap_growth,
    wrap_migration,
    wrap_platform,
    wrap_store,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (BlockedUpstream, RuntimeError, ConnectionError)

_SLUG_RE = re.compile(r"[a-z0-9._-]{1,40}")


def normalize_platform(raw: str) -> str:
    """Accepts 'shopify', 'Shopify', '/reports/shopify' or a full report URL."""
    value = (raw or "").strip().lower()
    if "storeleads.app" in value:
        value = value.split("storeleads.app", 1)[1]
    value = value.replace("/reports/", "").strip("/")
    value = value.split("?")[0].split("#")[0]
    m = _SLUG_RE.fullmatch(value)
    return m.group(0) if m else ""


async def list_reports(client: StoreLeadsClient) -> list[str]:
    html = await client.get_html(URL_REPORT_INDEX)
    slugs = re.findall(r'href="/reports/([a-z0-9._-]+)"', html)
    seen: list[str] = []
    for slug in slugs:
        if slug not in seen:
            seen.append(slug)
    return seen


def build_records(mode: str, platform: str, html: str, dimensions: list[str]) -> list[dict]:
    js_vars = parse_js_vars(html)
    growth_rows = dedupe_rows(parse_section_rows(html, GROWTH_SECTION), "Quarter")

    if mode == "platform":
        found = [s for s in list(BREAKDOWN_SECTIONS) + list(STORE_SECTIONS) + list(MIGRATION_SECTIONS)
                 if parse_section_rows(html, s)]
        if growth_rows:
            found.insert(0, GROWTH_SECTION)
        return [wrap_platform(platform, html, found, growth_rows)]

    if mode == "growth":
        return [wrap_growth(platform, row) for row in growth_rows]

    if mode == "breakdown":
        wanted = {d.strip().lower() for d in dimensions if d and d.strip()}
        out = []
        for section_id, dimension in BREAKDOWN_SECTIONS.items():
            if wanted and dimension not in wanted:
                continue
            rows = parse_section_rows(html, section_id)
            codes = js_codes(js_vars, dimension)
            for row in rows:
                label = next(iter(row.values()), None)
                out.append(wrap_breakdown(platform, dimension, row, codes.get(label)))
        return out

    if mode == "migration":
        out = []
        for section_id, direction in MIGRATION_SECTIONS.items():
            for row in parse_section_rows(html, section_id):
                out.append(wrap_migration(platform, direction, row))
        return out

    # mode == "stores"
    out = []
    for section_id, list_type in STORE_SECTIONS.items():
        for row in parse_section_rows(html, section_id):
            out.append(wrap_store(platform, list_type, row))
    return out


async def run_platforms(
    mode: str,
    platforms: list[str],
    dimensions: list[str],
    max_items: int,
    max_concurrency: int,
    proxy_url_factory,
    push,
) -> int:
    sem = asyncio.Semaphore(max_concurrency)
    pushed = 0
    lock = asyncio.Lock()

    async def one(raw: str):
        nonlocal pushed
        platform = normalize_platform(raw)
        if not platform:
            await push([extract_error(raw, "invalid_platform", "could not parse a platform slug from this input")])
            return
        async with sem:
            client = StoreLeadsClient(proxy_url=await proxy_url_factory())
            try:
                html = await client.get_html(URL_REPORT.format(platform=platform))
                records = build_records(mode, platform, html, dimensions)
                if not records:
                    records = [
                        extract_error(
                            platform,
                            "empty_section",
                            f"the {platform} report exists but publishes no {mode} section",
                        )
                    ]
            except ReportNotFound:
                records = [
                    extract_error(
                        platform,
                        "not_found",
                        f"no report published for {platform!r}. Run mode 'reference' to list every available platform.",
                    )
                ]
            except TRANSIENT as e:
                records = [extract_error(platform, "blocked_or_transient", repr(e))]
            finally:
                await client.close()

            async with lock:
                room = max_items - pushed
                if room <= 0:
                    return
                records = records[:room]
                pushed += len(records)
            await push(records)

    await asyncio.gather(*(one(p) for p in platforms))
    return pushed


async def run_reference(max_items: int, proxy_url: str | None) -> list[dict]:
    client = StoreLeadsClient(proxy_url=proxy_url)
    try:
        slugs = await list_reports(client)
        if not slugs:
            return [extract_error("reference", "empty_section", "the report index listed no platforms")]
        return [wrap_available(slug) for slug in slugs][:max_items]
    except TRANSIENT as e:
        return [extract_error("reference", "blocked_or_transient", repr(e))]
    finally:
        await client.close()


def _clean_list(input_data: dict, plural: str, single: str) -> list[str]:
    values = list(input_data.get(plural) or [])
    if input_data.get(single):
        values.insert(0, input_data[single])
    out: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "platform")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 1000))
        max_concurrency = int(input_data.get("maxConcurrency", 4))
        dimensions = _clean_list(input_data, "dimensions", "dimension")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def new_proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        async def push(records: list[dict]):
            if records:
                await Actor.push_data(records)

        if mode == "reference":
            records = await run_reference(max_items, await new_proxy_url())
            Actor.log.info(f"mode=reference: {len(records)} platform report(s) available")
            await push(records)
            return

        platforms = _clean_list(input_data, "platforms", "platform")
        if input_data.get("allPlatforms"):
            client = StoreLeadsClient(proxy_url=await new_proxy_url())
            try:
                platforms = await list_reports(client)
                Actor.log.info(f"allPlatforms: expanded to {len(platforms)} platform(s)")
            finally:
                await client.close()

        if not platforms:
            raise input_error(
                "Provide 'platform' or 'platforms', or set 'allPlatforms' to true. "
                "Run mode 'reference' to see what is available."
            )

        count = await run_platforms(
            mode, platforms, dimensions, max_items, max_concurrency, new_proxy_url, push
        )
        Actor.log.info(f"mode={mode} platforms={len(platforms)} -> {count} record(s)")
