"""Facebook Business Contact Extractor -- Apify actor entry point."""

from __future__ import annotations

import asyncio
import re

from apify import Actor

from src.adlib import build_url, collect
from src.exporters import BUILDERS
from src.fbcore import BlockedError, FacebookSession, is_hollow
from src.parser import (
    flatten_contact,
    matches_filters,
    page_ref,
    parse_about,
    parse_transparency,
    summarise,
)
from src.runtime import envelope, error_record, resolve_proxy, write_exports
from src.input_errors import input_error

SOURCE = "page-about-tab"
BASE = "https://www.facebook.com/"
PROFILE_URI = re.compile(r"facebook\.com/([^/?#]+)", re.I)

# The Ad Library sample used per discovery keyword. Discovery is about breadth
# of advertisers, not depth of ads, so this stays modest: 90 ads across a keyword
# typically surfaces 30-40 distinct pages.
DISCOVERY_ADS = 90


def read_direct_pages(actor_input: dict) -> list[dict]:
    out = []
    for key in ("pages", "startUrls"):
        for item in actor_input.get(key) or []:
            value = item.get("url") if isinstance(item, dict) else item
            slug = page_ref(str(value or ""))
            if slug:
                out.append({"slug": slug, "discoveredVia": "input", "discoveryQuery": None})
    seen: set[str] = set()
    unique = []
    for entry in out:
        if entry["slug"] not in seen:
            seen.add(entry["slug"])
            unique.append(entry)
    return unique


async def discover(
    session: FacebookSession,
    keywords: list[str],
    countries: list[str],
    actor_input: dict,
) -> list[dict]:
    """Find business pages by keyword, through the Ad Library.

    Facebook's own page search is closed to logged-out clients -- every
    `/search/<vertical>/` path returns HTTP 404 -- so keyword discovery has to
    come from somewhere else. The Ad Library is keyword-addressable and every
    result names its advertiser, which has a useful side effect: the pages it
    finds are all spending money, so the list skews towards businesses that are
    actually trading.
    """
    found: dict[str, dict] = {}
    filters = {"onlyActive": False, "onlyWithVideo": False,
               "minRunningDays": None, "adTextContains": None}

    for keyword in keywords:
        for country in countries:
            query = {
                "activeStatus": "active",
                "adType": "all",
                "mediaType": "all",
                "searchType": "keyword_unordered",
                "publisherPlatforms": [],
                "contentLanguages": actor_input.get("contentLanguages") or [],
                "startDateMin": None,
                "startDateMax": None,
                "country": country,
                "term": keyword,
                "pageId": None,
                "label": f"keyword:{keyword} @ {country}",
            }
            try:
                ads, _ = await collect(session, query, DISCOVERY_ADS, filters)
            except BlockedError as exc:
                Actor.log.warning(f"Discovery for {keyword!r} in {country} failed: {exc}")
                continue

            for ad in ads:
                uri = ad.get("pageUrl") or ""
                match = PROFILE_URI.search(uri)
                if not match:
                    continue
                slug = page_ref(match.group(1))
                if not slug or slug in found:
                    continue
                found[slug] = {
                    "slug": slug,
                    "discoveredVia": "ad-library",
                    "discoveryQuery": f"{keyword} @ {country}",
                    "advertiserName": ad.get("pageName"),
                    "advertiserPageId": ad.get("pageId"),
                }
            Actor.log.info(
                f"Discovery {keyword!r} @ {country}: {len(ads)} ad(s) -> "
                f"{len(found)} distinct page(s) so far"
            )
    return list(found.values())


async def extract_one(
    session: FacebookSession,
    target: dict,
    include_transparency: bool,
    semaphore: asyncio.Semaphore,
) -> dict:
    async with semaphore:
        slug = target["slug"]
        try:
            html = await session.get_html(f"{BASE}{slug}/about")
        except BlockedError as exc:
            return error_record(SOURCE, slug, "fetch_failed", str(exc))
        except Exception as exc:
            return error_record(
                SOURCE, slug, "unexpected_error", f"{type(exc).__name__}: {exc}"
            )

        if is_hollow(html):
            return error_record(
                SOURCE, slug, "page_not_found",
                "Facebook served the empty shell (~330 KB). No page resolves to "
                "this slug. Facebook answers HTTP 200 for missing pages, so this "
                "is judged on the payload rather than the status code.",
            )

        record = flatten_contact(parse_about(html))
        record["slug"] = slug
        record["pageUrl"] = f"{BASE}{slug}"
        record["discoveredVia"] = target.get("discoveredVia")
        record["discoveryQuery"] = target.get("discoveryQuery")
        if target.get("advertiserPageId") and not record.get("pageId"):
            record["pageId"] = target["advertiserPageId"]

        if include_transparency:
            try:
                transparency_html = await session.get_html(
                    f"{BASE}{slug}/about_profile_transparency"
                )
                record.update(parse_transparency(transparency_html))
            except BlockedError:
                record["adStatusText"] = None
        return record


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        direct = read_direct_pages(actor_input)
        keywords = [str(k).strip() for k in (actor_input.get("searchKeywords") or [])
                    if str(k).strip()]
        countries = [str(c).strip().upper() for c in (actor_input.get("countries") or ["US"])
                     if str(c).strip()]
        countries = list(dict.fromkeys(countries)) or ["US"]

        if not direct and not keywords:
            raise input_error(
                "Nothing to extract. Supply pages (slugs or URLs), or "
                "searchKeywords to discover business pages through the Ad Library."
            )

        max_pages = max(1, min(int(actor_input.get("maxPages", 100)), 5000))
        concurrency = max(1, min(int(actor_input.get("concurrency", 4)), 10))
        include_transparency = bool(actor_input.get("includeTransparency"))
        filters = {
            "requireEmail": bool(actor_input.get("requireEmail")),
            "requirePhone": bool(actor_input.get("requirePhone")),
            "requireWebsite": bool(actor_input.get("requireWebsite")),
            "requireAnyContact": bool(actor_input.get("requireAnyContact")),
            "minFollowers": actor_input.get("minFollowers"),
            "categoryContains": actor_input.get("categoryContains"),
        }
        export_formats = actor_input.get("exportFormats") or []
        emit_summary = bool(actor_input.get("emitSummary", True))
        proxy_url = await resolve_proxy(actor_input)

        records: list[dict] = []
        kept: list[dict] = []
        failures = 0

        async with FacebookSession(proxy_url=proxy_url, log=Actor.log) as session:
            targets = list(direct)
            if keywords:
                Actor.log.info(
                    f"Discovering pages for {len(keywords)} keyword(s) in "
                    f"{', '.join(countries)} through the Ad Library."
                )
                discovered = await discover(session, keywords, countries, actor_input)
                known = {t["slug"] for t in targets}
                targets.extend(t for t in discovered if t["slug"] not in known)

            targets = targets[:max_pages]
            if not targets:
                raise RuntimeError(
                    "Discovery found no advertiser pages for these keywords. Try a "
                    "broader keyword or another country."
                )

            Actor.log.info(
                f"Reading the about tab of {len(targets)} page(s) with concurrency "
                f"{concurrency}. These pages are large (8-18 MB each), which is why "
                "concurrency is kept low by default."
            )

            semaphore = asyncio.Semaphore(concurrency)
            results = await asyncio.gather(
                *(extract_one(session, target, include_transparency, semaphore)
                  for target in targets)
            )

        for record in results:
            if record.get("recordType") == "ERROR":
                failures += 1
                records.append(record)
                await Actor.push_data(record)
                continue
            if not matches_filters(record, filters):
                continue
            row = {**envelope(SOURCE, record["slug"], "BUSINESS"), **record}
            records.append(row)
            kept.append(record)
            await Actor.push_data(row)

        if emit_summary and kept:
            stats = summarise(kept)
            summary = {
                **envelope(SOURCE, f"{len(targets)} page(s)", "RUN_SUMMARY"),
                **stats,
                "pagesRequested": len(targets),
                "pagesFailed": failures,
                "discoveryKeywords": keywords,
            }
            records.append(summary)
            await Actor.push_data(summary)
            Actor.log.info(
                f"Summary: {stats['pagesProcessed']} page(s) | "
                f"{stats['withEmail']} email, {stats['withPhone']} phone, "
                f"{stats['withWebsite']} website, {stats['withAddress']} address | "
                f"{stats['fullyContactable']} with all four"
            )

        await write_exports(records, export_formats, BUILDERS)

        Actor.log.info(f"Finished: {len(kept)} business(es) | {failures} failure(s)")
        if failures and not kept:
            raise RuntimeError(
                "Every page failed and nothing was collected -- see the ERROR records."
            )


__all__ = ["main", "build_url"]
