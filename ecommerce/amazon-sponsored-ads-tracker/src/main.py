"""Amazon Sponsored Ads Intelligence -- Apify Actor entrypoint."""

import asyncio
import logging

from apify import Actor

from src.ads import (
    InvalidInput,
    clean_keyword,
    parse_page,
    search_url,
    summary_record,
)
from src.client import AmazonClient, BlockedError, CaptchaError
from src.constants import DEFAULT_DELAY_SECONDS, DOMAINS

logger = logging.getLogger(__name__)


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        raw_keywords = actor_input.get("keywords") or []
        marketplace = actor_input.get("marketplace", "com")
        samples = max(1, min(int(actor_input.get("samplesPerKeyword") or 1), 5))
        include_organic = bool(actor_input.get("includeOrganic"))
        include_summary = actor_input.get("includeSummary", True)
        max_results = actor_input.get("maxResultsPerKeyword") or 0
        delay = actor_input.get("delaySeconds")
        delay = DEFAULT_DELAY_SECONDS if delay is None else float(delay)

        proxy_config = None
        try:
            proxy_config = await Actor.create_proxy_configuration(
                actor_proxy_input=actor_input.get("proxyConfiguration")
            )
        except Exception as exc:  # noqa: BLE001
            Actor.log.warning("Proxy configuration unavailable (%s) -- going direct.", exc)

        proxy_url = await proxy_config.new_url() if proxy_config else None
        new_proxy_url = proxy_config.new_url if proxy_config else None
        if not proxy_url:
            Actor.log.warning(
                "Running without a proxy. Amazon search blocks most TLS fingerprints and "
                "serves CAPTCHAs to traffic it dislikes -- residential proxy is strongly "
                "recommended."
            )

        client = AmazonClient(
            marketplace=marketplace, proxy_url=proxy_url, new_proxy_url=new_proxy_url
        )
        pushed = 0
        stats = {"keywords": 0, "ads": 0, "organic": 0, "failed": 0, "noAds": 0}

        try:
            if marketplace not in DOMAINS:
                raise InvalidInput(
                    f"Unknown marketplace {marketplace!r}. Expected one of {list(DOMAINS)}."
                )
            if not raw_keywords:
                raise InvalidInput(
                    '`keywords` is empty. Provide the search terms to monitor, '
                    'e.g. ["wireless earbuds", "yoga mat"].'
                )

            keywords = []
            for raw in raw_keywords:
                try:
                    keyword = clean_keyword(raw)
                except InvalidInput as exc:
                    Actor.log.error("Skipping %r: %s", raw, exc)
                    await Actor.push_data({
                        "_input": str(raw), "_source": "none",
                        "_error": "INVALID_INPUT", "_errorDetail": str(exc),
                    })
                    pushed += 1
                    stats["failed"] += 1
                else:
                    if keyword not in keywords:
                        keywords.append(keyword)
            if not keywords:
                raise InvalidInput("No usable keywords among the provided inputs.")

            Actor.log.info(
                "Monitoring %d keyword(s) on amazon.%s, %d sample(s) each",
                len(keywords), marketplace, samples,
            )

            for index, keyword in enumerate(keywords):
                collected: list = []
                failures = 0

                for sample in range(1, samples + 1):
                    context = {
                        "keyword": keyword, "marketplace": marketplace, "sample": sample,
                    }
                    try:
                        page_html = await client.get_search(search_url(marketplace, keyword))
                    except (BlockedError, CaptchaError) as exc:
                        failures += 1
                        error_kind = (
                            "CAPTCHA_ESCALATION" if isinstance(exc, CaptchaError)
                            else "BLOCKED_AFTER_RETRIES"
                        )
                        Actor.log.error("%r sample %d failed: %s", keyword, sample, exc)
                        await Actor.push_data({
                            "_input": keyword, "_source": "none", "keyword": keyword,
                            "marketplace": marketplace, "sampleIndex": sample,
                            "_error": error_kind, "_errorDetail": str(exc),
                        })
                        pushed += 1
                        continue

                    records = parse_page(page_html, context)
                    if max_results:
                        records = records[:max_results]
                    collected.extend(records)

                    ads = sum(1 for r in records if r["isSponsored"])
                    Actor.log.info(
                        "%r sample %d/%d -> %d result(s), %d sponsored",
                        keyword, sample, samples, len(records), ads,
                    )
                    if sample < samples and delay:
                        await asyncio.sleep(delay)

                if failures == samples:
                    stats["failed"] += 1
                else:
                    stats["keywords"] += 1

                for record in collected:
                    if record["isSponsored"]:
                        stats["ads"] += 1
                    else:
                        stats["organic"] += 1
                        if not include_organic:
                            continue
                    await Actor.push_data(record)
                    pushed += 1

                if include_summary and collected:
                    summary = summary_record(collected, {
                        "keyword": keyword, "marketplace": marketplace,
                    }, samples)
                    await Actor.push_data(summary)
                    pushed += 1
                    if not summary["sponsoredCount"]:
                        stats["noAds"] += 1
                        # Not an error: ad density measured 0-21.7% across
                        # keywords, so an empty auction is a real result.
                        Actor.log.info(
                            "%r had no sponsored placements in %d sample(s) -- "
                            "normal for low-competition keywords",
                            keyword, samples,
                        )
                    else:
                        Actor.log.info(
                            "%r -> %d ad(s) across %d sample(s), %.1f%% of slots, "
                            "%d unique advertiser ASIN(s)",
                            keyword, summary["sponsoredCount"], samples,
                            summary["sponsoredSharePercent"] or 0,
                            summary["uniqueAdvertisedAsins"],
                        )

                if delay and index < len(keywords) - 1:
                    await asyncio.sleep(delay)

        except (InvalidInput, BlockedError, CaptchaError) as exc:
            error_kind = {
                InvalidInput: "INVALID_INPUT",
                BlockedError: "BLOCKED_AFTER_RETRIES",
                CaptchaError: "CAPTCHA_ESCALATION",
            }[type(exc)]
            Actor.log.exception("Run failed: %s", error_kind)
            await Actor.push_data({
                "_input": "input", "_source": "none",
                "_error": error_kind, "_errorDetail": str(exc),
            })
            await Actor.set_status_message(f"Failed: {error_kind}")
            raise
        finally:
            await client.close()

        if pushed == 0:
            Actor.log.warning("Run produced no records.")
            await Actor.push_data({
                "_input": "input", "_source": "none", "_error": "EMPTY_RESULT",
                "_errorDetail": "No search result parsed. Check the keywords and marketplace.",
            })

        Actor.log.info(
            "Done -- %d pushed | %d keyword(s), %d ad(s), %d organic, "
            "%d keyword(s) with no ads, %d failed",
            pushed, stats["keywords"], stats["ads"], stats["organic"],
            stats["noAds"], stats["failed"],
        )
        await Actor.set_status_message(
            f"{stats['ads']} ad(s) across {stats['keywords']} keyword(s), "
            f"{stats['failed']} failed"
        )
