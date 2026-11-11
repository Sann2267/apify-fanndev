import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.extractor import estimate_monthly_revenue, extract_error, wrap
from src.skool import NotFoundOrPrivate as SkoolNotFound
from src.skool import UnexpectedShape as SkoolUnexpectedShape
from src.skool import SkoolClient, extract_slug as skool_slug, parse_display_price
from src.whop import NotFound as WhopNotFound
from src.whop import UnexpectedShape as WhopUnexpectedShape
from src.whop import WhopClient, best_monthly_price_usd, extract_slug as whop_slug
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def run_skool(raw_input: str, proxy_url: str | None) -> dict:
    slug = skool_slug(raw_input)
    if not slug:
        return extract_error(raw_input, "skool", "empty_input")

    client = SkoolClient(proxy_url=proxy_url)
    try:
        group = await client.get_community(slug)
        metadata = group.get("metadata", {})
        price = parse_display_price(metadata)
        member_count = metadata.get("totalMembers")
        computed = {
            "communityName": metadata.get("displayName") or group.get("name"),
            "url": f"https://www.skool.com/{slug}",
            "memberCount": member_count,
            "isPaid": bool(metadata.get("membership")),
            "subscriptionPrice": price,
            **estimate_monthly_revenue(
                member_count, price["monthlyEquivalentUsd"] if price else None
            ),
        }
        return wrap(raw_input, "skool", "S1-nextdata", group, computed)
    except SkoolNotFound as e:
        return extract_error(raw_input, "skool", "not_found_or_private", repr(e))
    except SkoolUnexpectedShape as e:
        return extract_error(raw_input, "skool", "unexpected_shape", repr(e))
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(raw_input, "skool", "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def run_whop(raw_input: str, proxy_url: str | None) -> dict:
    slug = whop_slug(raw_input)
    if not slug:
        return extract_error(raw_input, "whop", "empty_input")

    client = WhopClient(proxy_url=proxy_url)
    try:
        company = await client.get_community(slug)
        primary_route = company.get("primaryAccessPassRoute")
        primary_plans = [p for p in company["plans"] if p["accessPassRoute"] == primary_route]
        monthly_price = best_monthly_price_usd(primary_plans)
        member_count = company.get("memberCount")
        computed = {
            "communityName": company.get("title"),
            "url": f"https://whop.com/{slug}",
            "memberCount": member_count,
            "isPaid": monthly_price is not None,
            "subscriptionPrice": (
                {"monthlyEquivalentUsd": monthly_price, "currency": "usd"}
                if monthly_price is not None
                else None
            ),
            **estimate_monthly_revenue(member_count, monthly_price),
        }
        return wrap(raw_input, "whop", "S1-html-rsc-scan", company, computed)
    except WhopNotFound as e:
        return extract_error(raw_input, "whop", "not_found", repr(e))
    except WhopUnexpectedShape as e:
        return extract_error(raw_input, "whop", "unexpected_shape", repr(e))
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(raw_input, "whop", "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "skool")
        if mode not in ("skool", "whop"):
            raise input_error(f"Invalid mode: {mode!r}. Must be 'skool' or 'whop'.")

        urls = list(input_data.get("urls") or [])
        if input_data.get("url"):
            urls.insert(0, input_data["url"])
        if not urls:
            raise input_error("Provide 'url' or 'urls'.")
        # de-dupe while preserving order
        seen = set()
        urls = [u for u in urls if not (u in seen or seen.add(u))]

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        max_concurrency = int(input_data.get("maxConcurrency", 4))
        sem = asyncio.Semaphore(max_concurrency)
        run_fn = run_skool if mode == "skool" else run_whop

        async def _bounded(u: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                record = await run_fn(u, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(f"mode={mode}: {len(urls)} url(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(u) for u in urls))
