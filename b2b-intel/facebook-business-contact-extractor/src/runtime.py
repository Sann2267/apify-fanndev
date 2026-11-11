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

    Every Facebook surface this family touches was reachable without a proxy on
    2026-09-20 -- the Ad Library's 403 is a solvable challenge, not an IP ban --
    so the default is direct and a proxy is an opt-in for rate-limit relief or
    for asking a country-specific question (Marketplace and the Ad Library both
    localise by exit IP).
    """
    proxy_input = actor_input.get("proxyConfiguration") or {}
    if not proxy_input.get("useApifyProxy"):
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
