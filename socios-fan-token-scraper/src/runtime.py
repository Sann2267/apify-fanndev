"""Input coercion and proxy wiring.

Proxy is opt-in and off by default. ``api.chiliz.com`` sits behind Cloudflare
but runs no challenge on it, answers identically from an Apify datacenter IP and
from a residential one, and its only 403 is an ACL verdict that no exit IP
changes. Defaulting the proxy on would bill the buyer for nothing. It stays
available because a long run from a single IP can still meet a rate limiter, and
because residential egress is occasionally the difference on a bad Cloudflare
day.
"""

from __future__ import annotations

from typing import Any


def string_list(value: Any) -> list[str]:
    """Accept a list, a comma/newline-separated string, or a list of dicts."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(",", "\n").splitlines()]
        return [p for p in parts if p]
    if isinstance(value, dict):
        value = [value]
    out: list[str] = []
    for item in value or []:
        if isinstance(item, dict):
            item = item.get("value") or item.get("url") or item.get("id")
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def clamp(value: Any, low: int, high: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


async def proxy_url_from(actor: Any, actor_input: dict) -> str | None:
    """Build a proxy URL only if the buyer asked for one.

    Calling ``create_proxy_configuration`` unconditionally is how a no-proxy run
    ends up dying on an account without a proxy plan, so the opt-out is checked
    before the SDK is involved at all, and every failure below degrades to a
    direct run rather than ending it.
    """
    configuration_input = actor_input.get("proxyConfiguration") or {}
    if not configuration_input.get("useApifyProxy"):
        return None
    groups = configuration_input.get("apifyProxyGroups") or None
    country = configuration_input.get("apifyProxyCountry") or None
    try:
        configuration = await actor.create_proxy_configuration(
            groups=groups, country_code=country
        )
    except Exception as exc:
        actor.log.warning(f"Proxy configuration failed ({exc}) -- continuing direct.")
        return None
    if configuration is None:
        actor.log.warning(
            "Proxy requested but unavailable on this account -- continuing direct. "
            "api.chiliz.com has no IP gate, so this is usually harmless."
        )
        return None
    url = await configuration.new_url()
    actor.log.info(f"Using Apify proxy ({', '.join(groups) if groups else 'auto'}).")
    return url
