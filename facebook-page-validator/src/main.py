"""Facebook Page Validator -- Apify actor entry point."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from apify import Actor

from src.client import BlockedError, FacebookClient
from src.constants import REQUEST_DELAY, TIER_HOLLOW, classify_tier
from src.exporters import BUILDERS
from src.parser import parse_page
from src.verdict import assess, matches_filters, summarise
from src.input_errors import input_error

SOURCE = "public-about-tab"

# Accepts a bare slug, a profile URL, or a pg/ style URL.
URL_SLUG = re.compile(r"^(?:https?://)?(?:[\w-]+\.)?facebook\.com/(?:pg/)?([^/?#]+)", re.I)

# Paths that look like slugs but address Facebook surfaces this actor does not
# validate; letting them through would produce confident nonsense.
RESERVED_PATHS = {"profile.php", "people", "groups", "events", "marketplace", "watch"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalise_slug(raw: str) -> str | None:
    """Reduce any accepted input form to a bare vanity slug."""
    value = (raw or "").strip()
    if not value:
        return None
    match = URL_SLUG.match(value)
    if match:
        value = match.group(1)
    value = value.strip("/").split("?")[0].split("#")[0]
    if not value or value.lower() in RESERVED_PATHS:
        return None
    return value


def read_targets(actor_input: dict) -> list[dict]:
    """Collect {slug, expectedBrand} targets from every accepted input field."""
    targets: list[dict] = []

    for item in actor_input.get("slugs") or []:
        slug = normalise_slug(str(item))
        if slug:
            targets.append({"slug": slug, "expectedBrand": None})

    for item in actor_input.get("startUrls") or []:
        value = item.get("url") if isinstance(item, dict) else item
        slug = normalise_slug(str(value or ""))
        if slug:
            targets.append({"slug": slug, "expectedBrand": None})

    # The rich form: [{"slug": "nike", "expectedBrand": "Nike"}, ...]
    for item in actor_input.get("pages") or []:
        if isinstance(item, dict):
            slug = normalise_slug(str(item.get("slug") or item.get("url") or ""))
            brand = item.get("expectedBrand") or item.get("brand")
        else:
            slug, brand = normalise_slug(str(item)), None
        if slug:
            targets.append({"slug": slug, "expectedBrand": brand or None})

    # Later entries win, so a slug supplied with an expected brand is not lost
    # to an earlier bare mention of the same slug.
    merged: dict[str, dict] = {}
    for target in targets:
        if merged.get(target["slug"]) and not target["expectedBrand"]:
            continue
        merged[target["slug"]] = target
    return list(merged.values())


def build_record(target: dict, tier: str, parsed: dict, size: int) -> dict:
    verdict = assess(target["slug"], tier, parsed, target["expectedBrand"])
    payload = {
        "_input": target["slug"],
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        "recordType": "PAGE",
        **verdict,
        "payloadBytes": size,
    }
    if tier != TIER_HOLLOW:
        payload.update(
            {
                "name": parsed.get("name"),
                "pageId": parsed.get("pageId"),
                "followers": parsed.get("followers"),
                "followersLabel": parsed.get("followersLabel"),
                "following": parsed.get("following"),
                "categories": parsed.get("categories") or [],
                "primaryCategory": (parsed.get("categories") or [None])[0],
                "phones": parsed.get("phones") or [],
                "websites": parsed.get("websites") or [],
                "emails": parsed.get("emails") or [],
                "addresses": parsed.get("addresses") or [],
                "postsInPayload": parsed.get("postsInPayload", 0),
            }
        )
    return payload


def error_record(slug: str, error: str, detail: str) -> dict:
    return {
        "_input": slug,
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        "recordType": "ERROR",
        "slug": slug,
        "_error": error,
        "_errorDetail": detail,
    }


async def check_one(client: FacebookClient, target: dict, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        try:
            html = await client.fetch_about(target["slug"])
        except BlockedError as exc:
            return error_record(target["slug"], "fetch_failed", str(exc))
        except Exception as exc:  # one bad slug must not end the run
            return error_record(
                target["slug"], "unexpected_error", f"{type(exc).__name__}: {exc}"
            )

        size = len(html)
        tier = classify_tier(size)
        # Parsing a hollow payload is pure waste -- it carries no profile data.
        parsed = parse_page(html) if tier != TIER_HOLLOW else {}
        await asyncio.sleep(REQUEST_DELAY)
        return build_record(target, tier, parsed, size)


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        targets = read_targets(actor_input)
        if not targets:
            raise input_error(
                "Nothing to check. Supply slugs (e.g. ['nike', 'starbucks']), "
                "startUrls, or pages with an expectedBrand for each slug."
            )

        concurrency = max(1, min(int(actor_input.get("concurrency", 5)), 15))
        export_formats = actor_input.get("exportFormats") or []
        emit_summary = bool(actor_input.get("emitSummary", True))
        filters = {
            "onlyExisting": bool(actor_input.get("onlyExisting")),
            "onlyNotFound": bool(actor_input.get("onlyNotFound")),
            "onlyBrandMismatch": bool(actor_input.get("onlyBrandMismatch")),
            "minFollowers": actor_input.get("minFollowers"),
        }
        if filters["onlyExisting"] and filters["onlyNotFound"]:
            raise input_error(
                "onlyExisting and onlyNotFound exclude each other -- enabling both "
                "can only ever return an empty dataset."
            )

        proxy_input = actor_input.get("proxyConfiguration") or {}
        proxy_url: str | None = None
        if proxy_input.get("useApifyProxy"):
            try:
                configuration = await Actor.create_proxy_configuration(
                    groups=proxy_input.get("apifyProxyGroups") or None,
                    country_code=proxy_input.get("apifyProxyCountry") or None,
                )
                if configuration:
                    proxy_url = await configuration.new_url()
                    Actor.log.info("Using Apify proxy.")
            except Exception as exc:
                Actor.log.warning(f"Proxy configuration unavailable ({exc}); running direct.")
        else:
            # This surface has no TLS or IP gate, so the platform IP is fine and
            # a proxy would only add latency and cost.
            Actor.log.info("No proxy configured -- using the direct connection.")

        Actor.log.info(f"Checking {len(targets)} slug(s) with concurrency {concurrency}.")

        semaphore = asyncio.Semaphore(concurrency)
        async with FacebookClient(proxy_url=proxy_url, log=Actor.log) as client:
            records = await asyncio.gather(
                *(check_one(client, target, semaphore) for target in targets)
            )

        rows: list[dict] = []
        all_records: list[dict] = []
        failures = 0
        for record in records:
            if record.get("recordType") == "ERROR":
                failures += 1
                all_records.append(record)
                await Actor.push_data(record)
                continue
            if not matches_filters(record, filters):
                continue
            rows.append(record)
            all_records.append(record)
            await Actor.push_data(record)

        if emit_summary and rows:
            summary = summarise(rows)
            summary_record = {
                "_input": f"{len(targets)} slug(s)",
                "_source": SOURCE,
                "_scrapedAt": utc_now_iso(),
                "recordType": "RUN_SUMMARY",
                **summary,
            }
            await Actor.push_data(summary_record)
            all_records.append(summary_record)
            Actor.log.info(
                f"Summary: {summary['existing']}/{summary['slugsChecked']} exist, "
                f"{summary['notFound']} not found, "
                f"{summary['brandMismatch']} brand mismatch, "
                f"{summary['brandWeakMatch']} weak match, "
                f"{summary['reducedPayloads']} reduced payload(s)"
            )

        if export_formats and all_records:
            store = await Actor.open_key_value_store()
            for fmt in export_formats:
                spec = BUILDERS.get(fmt)
                if not spec:
                    Actor.log.warning(f"Unknown export format {fmt!r} -- skipped.")
                    continue
                filename, content_type, builder = spec
                filename = filename.replace("reviews", "facebook-pages")
                payload_bytes = builder(all_records)
                if payload_bytes is None:
                    Actor.log.warning(f"{fmt}: exporter unavailable -- skipped.")
                    continue
                await store.set_value(filename, payload_bytes, content_type=content_type)
                Actor.log.info(f"Exported {filename} ({len(payload_bytes):,} bytes)")

        Actor.log.info(f"Finished: {len(rows)} record(s) kept | {failures} failure(s)")
        if failures and not rows:
            raise RuntimeError(
                "Every slug failed and nothing was collected -- see the ERROR records."
            )
