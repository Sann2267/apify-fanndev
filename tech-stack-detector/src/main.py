"""Tech Stack Detector -- Apify actor entry point."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from apify import Actor

from src.client import FetchFailure, WebClient
from src.constants import MAX_HTML_BYTES, REQUEST_DELAY, ROBOTS_MARKERS, ROBOTS_PATH
from src.detector import detect, summarise_stack
from src.exporters import BUILDERS
from src.fingerprints import CATEGORIES, FINGERPRINTS
from src.input_errors import input_error

SOURCE = "homepage-fingerprint"

# A hostname: letters, digits, hyphens and dots, ending in a TLD of 2+ letters.
HOSTNAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9-]+)*\.[a-z]{2,}$", re.I)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalise_target(raw: str) -> str | None:
    """Turn 'allbirds.com', 'www.allbirds.com' or a full URL into an https URL."""
    value = (raw or "").strip()
    if not value:
        return None
    if "://" not in value:
        value = "https://" + value.lstrip("/")
    parsed = urlparse(value)
    host = (parsed.hostname or "").strip().lower()
    if not host or not HOSTNAME.match(host):
        return None
    port = f":{parsed.port}" if parsed.port else ""
    # The homepage is what gets fingerprinted, so any path is dropped on
    # purpose -- two URLs on the same site must not become two billed records.
    return f"https://{host}{port}/"


def read_targets(actor_input: dict) -> list[str]:
    raw: list[str] = []
    for item in actor_input.get("domains") or []:
        raw.append(str(item))
    for item in actor_input.get("startUrls") or []:
        value = item.get("url") if isinstance(item, dict) else item
        if value:
            raw.append(str(value))
    normalised = [normalise_target(value) for value in raw]
    return list(dict.fromkeys(url for url in normalised if url))


def robots_detections(robots_text: str, already: set[str]) -> list[dict]:
    """Technologies implied by robots.txt that the homepage did not reveal."""
    lowered = robots_text.lower()
    found: list[dict] = []
    for technology, marker, confidence in ROBOTS_MARKERS:
        if technology in already or marker.lower() not in lowered:
            continue
        category = next(
            (f["category"] for f in FINGERPRINTS if f["name"] == technology), "CMS"
        )
        found.append({
            "technology": technology,
            "category": category,
            "categoryLabel": CATEGORIES.get(category, category),
            "confidence": confidence,
            "signalCount": 1,
            "evidence": [f'robots.txt disallows "{marker}"'],
            "signalTypes": ["robots"],
        })
        already.add(technology)
    return found


def error_record(url: str, kind: str, detail: str) -> dict:
    return {
        "_input": url,
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        "recordType": "ERROR",
        "url": url,
        "domain": urlparse(url).hostname,
        "reachable": False,
        "_error": kind,
        "_errorDetail": detail,
    }


async def analyse(
    client: WebClient, url: str, semaphore: asyncio.Semaphore, check_robots: bool
) -> dict:
    async with semaphore:
        try:
            page = await client.fetch(url)
        except FetchFailure as exc:
            # Every input is normalised to https, but plenty of older business
            # sites still answer only on port 80 with a broken or absent
            # certificate. Falling back keeps them in the dataset as analysable
            # prospects instead of writing them off as unreachable.
            page = None
            if exc.kind in ("tls_failure", "connection_failed", "unreachable"):
                try:
                    page = await client.fetch("http://" + url.split("://", 1)[1])
                except Exception:
                    page = None
            if page is None:
                return error_record(url, exc.kind, exc.detail)
        except Exception as exc:
            return error_record(url, "unexpected_error", f"{type(exc).__name__}: {exc}")

        html = page["html"][:MAX_HTML_BYTES]
        detections = detect(html, page["headers"], page["cookies"], page["finalUrl"])

        if check_robots:
            robots = await client.fetch_text(url.rstrip("/") + ROBOTS_PATH)
            if robots:
                detections.extend(
                    robots_detections(robots, {d["technology"] for d in detections})
                )

        await asyncio.sleep(REQUEST_DELAY)

        final_host = urlparse(page["finalUrl"]).hostname
        requested_host = urlparse(url).hostname
        return {
            "_input": url,
            "_source": SOURCE,
            "_scrapedAt": utc_now_iso(),
            "recordType": "SITE",
            "url": url,
            "domain": requested_host,
            "finalUrl": page["finalUrl"],
            "finalDomain": final_host,
            # A redirect to a different host means the stack described here is
            # that host's, not the one the buyer typed. Say so rather than
            # quietly reporting somebody else's technology.
            "redirected": final_host != requested_host,
            "reachable": True,
            "statusCode": page["statusCode"],
            "pageBytes": len(page["html"]),
            **summarise_stack(detections),
            "detections": detections,
        }


def run_summary(rows: list[dict]) -> dict:
    """Which technologies showed up across the whole list, most common first."""
    counts: dict[str, int] = {}
    for row in rows:
        for technology in row.get("technologies") or []:
            counts[technology] = counts.get(technology, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    reachable = [r for r in rows if r.get("reachable")]
    return {
        "sitesChecked": len(rows),
        "sitesReachable": len(reachable),
        "sitesWithNoDetections": sum(1 for r in reachable if not r.get("technologies")),
        "technologyRanking": [
            {"technology": name, "sites": count, "share": round(count / len(reachable), 3)}
            for name, count in ranked[:40]
        ] if reachable else [],
    }


def matches_filters(row: dict, filters: dict) -> bool:
    if filters.get("onlyReachable") and not row.get("reachable"):
        return False
    required = filters.get("requireTechnology") or []
    if required:
        found = {t.lower() for t in (row.get("technologies") or [])}
        if not any(t.lower() in found for t in required):
            return False
    excluded = filters.get("excludeTechnology") or []
    if excluded:
        found = {t.lower() for t in (row.get("technologies") or [])}
        if any(t.lower() in found for t in excluded):
            return False
    minimum = filters.get("minTechnologies")
    if minimum is not None and row.get("technologyCount", 0) < minimum:
        return False
    return True


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        targets = read_targets(actor_input)
        if not targets:
            raise input_error(
                "Nothing to analyse. Supply domains (e.g. ['allbirds.com', "
                "'notion.com']) or startUrls."
            )

        concurrency = max(1, min(int(actor_input.get("concurrency", 8)), 30))
        check_robots = bool(actor_input.get("checkRobotsTxt", True))
        include_evidence = bool(actor_input.get("includeEvidence", True))
        export_formats = actor_input.get("exportFormats") or []
        emit_summary = bool(actor_input.get("emitSummary", True))
        filters = {
            "onlyReachable": bool(actor_input.get("onlyReachable")),
            "requireTechnology": actor_input.get("requireTechnology") or [],
            "excludeTechnology": actor_input.get("excludeTechnology") or [],
            "minTechnologies": actor_input.get("minTechnologies"),
        }

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
            Actor.log.info("No proxy configured -- using the direct connection.")

        Actor.log.info(
            f"Analysing {len(targets)} site(s) against {len(FINGERPRINTS)} "
            f"technologies, concurrency {concurrency}."
        )

        semaphore = asyncio.Semaphore(concurrency)
        async with WebClient(proxy_url=proxy_url, log=Actor.log) as client:
            records = await asyncio.gather(
                *(analyse(client, url, semaphore, check_robots) for url in targets)
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
            if not include_evidence:
                record.pop("detections", None)
            rows.append(record)
            all_records.append(record)
            await Actor.push_data(record)

        if emit_summary and rows:
            summary = run_summary(rows)
            summary_record = {
                "_input": f"{len(targets)} site(s)",
                "_source": SOURCE,
                "_scrapedAt": utc_now_iso(),
                "recordType": "RUN_SUMMARY",
                **summary,
            }
            await Actor.push_data(summary_record)
            all_records.append(summary_record)
            top = ", ".join(
                f"{item['technology']} ({item['sites']})"
                for item in summary["technologyRanking"][:5]
            )
            Actor.log.info(f"Most common: {top or 'nothing detected'}")

        if export_formats and all_records:
            store = await Actor.open_key_value_store()
            for fmt in export_formats:
                spec = BUILDERS.get(fmt)
                if not spec:
                    Actor.log.warning(f"Unknown export format {fmt!r} -- skipped.")
                    continue
                filename, content_type, builder = spec
                filename = filename.replace("reviews", "tech-stack")
                payload_bytes = builder(all_records)
                if payload_bytes is None:
                    Actor.log.warning(f"{fmt}: exporter unavailable -- skipped.")
                    continue
                await store.set_value(filename, payload_bytes, content_type=content_type)
                Actor.log.info(f"Exported {filename} ({len(payload_bytes):,} bytes)")

        Actor.log.info(f"Finished: {len(rows)} site(s) kept | {failures} failure(s)")
        if failures and not rows:
            raise RuntimeError(
                "Every site failed and nothing was collected -- see the ERROR records."
            )
