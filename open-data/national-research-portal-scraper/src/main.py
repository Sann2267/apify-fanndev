"""Mode and portal dispatch for the national research portal Actor."""

import asyncio
import logging

from apify import Actor

from src.client import (
    BlockedUpstream,
    NotFoundUpstream,
    PortalClient,
    ServiceUnavailable,
)
from src.constants import (
    CINII_ARTICLES,
    CINII_PAGE_SIZE,
    CINII_SEARCH,
    GARUDA_AUTHORS,
    GARUDA_DOCUMENTS,
    GARUDA_JOURNALS,
    KCI_PAGE_SIZE,
    KCI_SEARCH,
    MODES,
    PORTAL_MODES,
    PORTALS,
)
from src.extractor import (
    extract_error,
    garuda_total,
    parse_cinii,
    parse_garuda_authors,
    parse_garuda_documents,
    parse_garuda_journals,
    parse_kci,
    wrap_source,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (BlockedUpstream, ServiceUnavailable, RuntimeError, ConnectionError)


async def run_garuda(client: PortalClient, mode: str, query: str, max_items: int, max_pages: int) -> list[dict]:
    url_template = {
        "documents": GARUDA_DOCUMENTS,
        "journals": GARUDA_JOURNALS,
        "authors": GARUDA_AUTHORS,
    }[mode]
    parser = {
        "documents": parse_garuda_documents,
        "journals": parse_garuda_journals,
        "authors": parse_garuda_authors,
    }[mode]

    records: list[dict] = []
    total = None
    for page in range(1, max_pages + 1):
        url = url_template.format(query=query.replace(" ", "+"), page=page)
        html = await client.get_html(url)
        if total is None:
            total = garuda_total(html, mode)
        page_records = parser(query, html)
        if not page_records:
            # An empty page is the end of the result set, not an error -- Garuda
            # serves the same shell with no rows past the last page.
            break
        for record in page_records:
            record["page"] = page
            record["totalResults"] = total
            records.append(record)
            if len(records) >= max_items:
                return records[:max_items]
    return records


async def run_cinii(client: PortalClient, query: str, max_items: int, max_pages: int, articles_only: bool) -> list[dict]:
    endpoint = CINII_ARTICLES if articles_only else CINII_SEARCH
    records: list[dict] = []
    total = None
    for page in range(max_pages):
        start = page * CINII_PAGE_SIZE + 1  # OpenSearch `start` is 1-based
        payload = await client.get_json(
            endpoint,
            params={"q": query, "format": "json", "count": str(CINII_PAGE_SIZE), "start": str(start)},
        )
        page_records, page_total = parse_cinii(query, payload)
        total = total if total is not None else page_total
        if not page_records:
            break
        for record in page_records:
            record["page"] = page + 1
            record["totalResults"] = total
            records.append(record)
            if len(records) >= max_items:
                return records[:max_items]
    return records


async def run_kci(client: PortalClient, query: str, max_items: int, max_pages: int) -> list[dict]:
    records: list[dict] = []
    total = None
    for page in range(1, max_pages + 1):
        html = await client.get_html(
            KCI_SEARCH,
            params={
                "poSearchBean.searchQuery": query,
                "poSearchBean.currentPageNo": str(page),
                "poSearchBean.docsCount": str(KCI_PAGE_SIZE),
            },
        )
        page_records, page_total = parse_kci(query, html)
        total = total if total is not None else page_total
        if not page_records:
            break
        for record in page_records:
            record["page"] = page
            record["totalResults"] = total
            records.append(record)
            if len(records) >= max_items:
                return records[:max_items]
    return records


async def run_portal(
    portal: str, mode: str, query: str, max_items: int, max_pages: int, articles_only: bool, proxy_url: str | None
) -> list[dict]:
    supported = PORTAL_MODES.get(portal, ())
    if mode not in supported:
        others = sorted(p for p, modes in PORTAL_MODES.items() if mode in modes)
        return [
            extract_error(
                query,
                portal,
                "unsupported_mode",
                f"{portal} publishes no {mode} index. Portals that do: {', '.join(others) or 'none'}. "
                f"{portal} supports: {', '.join(supported)}.",
            )
        ]

    client = PortalClient(proxy_url=proxy_url)
    try:
        if portal == "garuda":
            records = await run_garuda(client, mode, query, max_items, max_pages)
        elif portal == "cinii":
            records = await run_cinii(client, query, max_items, max_pages, articles_only)
        else:
            records = await run_kci(client, query, max_items, max_pages)

        if not records:
            return [
                extract_error(query, portal, "no_results", f"{portal} returned no results for {query!r}")
            ]
        return records
    except NotFoundUpstream as e:
        return [extract_error(query, portal, "not_found", repr(e))]
    except ServiceUnavailable as e:
        return [extract_error(query, portal, "service_unavailable", repr(e))]
    except TRANSIENT as e:
        return [extract_error(query, portal, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_reference(proxy_url: str | None) -> list[dict]:
    """Probe each portal live. Government portals move hosts and go down for
    maintenance, so what worked last month is not evidence about today."""
    client = PortalClient(proxy_url=proxy_url)
    records: list[dict] = []
    try:
        try:
            html = await client.get_html(GARUDA_DOCUMENTS.format(query="machine+learning", page=1))
            rows = parse_garuda_documents("probe", html)
            records.append(
                wrap_source("garuda", GARUDA_DOCUMENTS.format(query="machine+learning", page=1), bool(rows),
                            "payload parsed" if rows else "no rows",
                            {"rows": len(rows), "totalResults": garuda_total(html, "documents"),
                             "sampleTitle": rows[0]["title"][:70] if rows else None,
                             "supportedModes": list(PORTAL_MODES["garuda"])})
            )
        except Exception as e:  # noqa: BLE001 -- a probe reports, never raises
            records.append(wrap_source("garuda", GARUDA_DOCUMENTS, False, repr(e)))

        try:
            payload = await client.get_json(CINII_SEARCH, params={"q": "machine learning", "format": "json", "count": "3"})
            rows, total = parse_cinii("probe", payload)
            records.append(
                wrap_source("cinii", CINII_SEARCH, bool(rows), "payload parsed" if rows else "no rows",
                            {"rows": len(rows), "totalResults": total,
                             "sampleTitle": rows[0]["title"][:70] if rows else None,
                             "supportedModes": list(PORTAL_MODES["cinii"])})
            )
        except Exception as e:  # noqa: BLE001
            records.append(wrap_source("cinii", CINII_SEARCH, False, repr(e)))

        try:
            html = await client.get_html(KCI_SEARCH, params={"poSearchBean.searchQuery": "machine learning"})
            rows, total = parse_kci("probe", html)
            records.append(
                wrap_source("kci", KCI_SEARCH, bool(rows), "payload parsed" if rows else "no rows",
                            {"rows": len(rows), "totalResults": total,
                             "sampleTitle": rows[0]["title"][:70] if rows else None,
                             "supportedModes": list(PORTAL_MODES["kci"])})
            )
        except Exception as e:  # noqa: BLE001
            records.append(wrap_source("kci", KCI_SEARCH, False, repr(e)))

        return records
    finally:
        await client.close()


def _clean_portals(input_data: dict) -> list[str]:
    values = list(input_data.get("portals") or [])
    if input_data.get("portal"):
        values.insert(0, input_data["portal"])
    out: list[str] = []
    for value in values:
        name = str(value).strip().lower()
        if name == "all":
            return list(PORTALS)
        if name in PORTALS and name not in out:
            out.append(name)
    return out


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "documents")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 200))
        max_pages = max(1, int(input_data.get("maxPages", 5)))
        articles_only = bool(input_data.get("ciniiArticlesOnly", False))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        proxy_url = await proxy_config.new_url() if proxy_config else None

        if mode == "reference":
            records = await run_reference(proxy_url)
            Actor.log.info(f"mode=reference: {sum(1 for r in records if r.get('isAvailable'))}/{len(records)} portal(s) live")
            await Actor.push_data(records)
            return

        portals = _clean_portals(input_data)
        if not portals:
            raise input_error(f"Provide 'portal' or 'portals' -- one of {PORTALS}, or 'all'.")

        query = (input_data.get("query") or "").strip()
        if not query and mode != "journals":
            raise input_error(f"Provide 'query' for mode '{mode}'.")

        # Budget per portal so the first portal cannot eat the whole run.
        per_portal = max(1, max_items // len(portals))
        total = 0
        for portal in portals:
            records = await run_portal(portal, mode, query, per_portal, max_pages, articles_only, proxy_url)
            await Actor.push_data(records)
            total += len(records)
            Actor.log.info(f"{portal}: {len(records)} record(s)")

        Actor.log.info(f"mode={mode} portals={portals} query={query!r} -> {total} record(s)")
