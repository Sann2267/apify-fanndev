"""Small pieces every actor in this family repeats: envelope, proxy, output.

Kept separate from fbcore so the transport layer stays free of Apify imports and
can be exercised by the offline test without a platform context.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from apify import Actor


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def envelope(source: str, input_value: Any, record_type: str) -> dict:
    """The four fields every dataset row in this portfolio carries."""
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }


def error_record(source: str, input_value: Any, error: str, detail: str) -> dict:
    return {
        **envelope(source, input_value, "ERROR"),
        "_error": error,
        "_errorDetail": detail,
    }


async def resolve_proxy(actor_input: dict) -> str | None:
    """Turn the actor's proxy input into a URL, or None for a direct connection.

    This defaulted to a direct connection because every Facebook surface in
    this family answered a *local* address on 2026-09-20. Cloud runs on
    2026-09-22 showed that conclusion does not transfer: from an Apify
    datacentre address Facebook serves the REDUCED payload tier -- the page
    still returns HTTP 200, but with no feed, no member count and no privacy
    field, so the run reports "feed unavailable" and fails having collected
    nothing. The same group fetched from a residential address on the same day
    returned 1.16 MB with the feed present.

    So the default is now the RESIDENTIAL group, and a direct connection is the
    opt-in. A proxy also decides the country a Marketplace or Ad Library query
    is answered for, since both localise by exit IP.
    """
    proxy_input = actor_input.get("proxyConfiguration") or {}
    if not proxy_input.get("useApifyProxy"):
        if Actor.is_at_home():
            # Worth a warning rather than an info line: this is the single
            # most likely reason a platform run collects nothing at all.
            Actor.log.warning(
                "No proxy configured, and this run is on the Apify platform. "
                "Facebook serves datacentre addresses a REDUCED payload -- "
                "HTTP 200 with no feed and no counts -- so this run will very "
                "likely collect nothing. Enable the Apify proxy with the "
                "RESIDENTIAL group (this actor's default) unless you are "
                "deliberately testing the direct path."
            )
        else:
            Actor.log.info("No proxy configured -- using the direct connection.")
        return None
    try:
        configuration = await Actor.create_proxy_configuration(
            groups=proxy_input.get("apifyProxyGroups") or None,
            country_code=proxy_input.get("apifyProxyCountry") or None,
        )
        if configuration is None:
            Actor.log.warning("Proxy requested but unavailable on this account; running direct.")
            return None
        url = await configuration.new_url()
        Actor.log.info("Using Apify proxy.")
        return url
    except Exception as exc:
        Actor.log.warning(f"Proxy configuration unavailable ({exc}); running direct.")
        return None


async def write_exports(records: list[dict], formats: list[str], builders: dict) -> None:
    """Mirror the dataset into the key-value store in the requested formats."""
    if not formats or not records:
        return
    store = await Actor.open_key_value_store()
    for fmt in formats:
        spec = builders.get(fmt) or builders.get({"excel": "xlsx"}.get(fmt, ""))
        if not spec:
            Actor.log.warning(f"Unknown export format {fmt!r} -- skipped.")
            continue
        filename, content_type, builder = spec
        payload = builder(records)
        if payload is None:
            Actor.log.warning(f"{fmt}: exporter unavailable -- skipped.")
            continue
        await store.set_value(filename, payload, content_type=content_type)
        Actor.log.info(f"Exported {filename} ({len(payload):,} bytes)")
