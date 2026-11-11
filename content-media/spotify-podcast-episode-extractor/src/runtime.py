"""Input coercion and proxy wiring shared by every Spotify actor here.

Proxy is opt-in and off by default. None of the three Spotify surfaces used by
these actors carries a WAF or an IP gate -- the Apify datacenter range reaches
all of them -- so a default-on proxy would bill the buyer for nothing. It stays
available because a long run from one IP can still meet Spotify's rate limiter,
and because ``market`` follows the exit IP on some endpoints.
"""

from __future__ import annotations

from typing import Any


def string_list(value: Any) -> list[str]:
    """Accept a list, a newline/comma-separated string, or a list of {url} dicts."""
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
            item = item.get("url") or item.get("value") or item.get("uri")
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def dedupe(values: list[str]) -> list[str]:
    """Order-preserving de-duplication, case-sensitive (Spotify ids are)."""
    return list(dict.fromkeys(values))


def clamp(value: Any, low: int, high: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


async def proxy_url_from(actor: Any, actor_input: dict) -> str | None:
    """Build a proxy URL if the buyer asked for one; otherwise run direct."""
    configuration_input = actor_input.get("proxyConfiguration") or {}
    if not configuration_input.get("useApifyProxy"):
        return None
    groups = configuration_input.get("apifyProxyGroups") or None
    country = configuration_input.get("apifyProxyCountry") or None
    try:
        configuration = await actor.create_proxy_configuration(
            groups=groups, country_code=country
        )
    except Exception as exc:  # a proxy misconfiguration should not end the run
        actor.log.warning(f"Proxy configuration failed ({exc}) -- continuing direct.")
        return None
    if configuration is None:
        actor.log.warning(
            "Proxy was requested but is not available on this account -- "
            "continuing direct. Spotify has no IP gate, so this is usually fine."
        )
        return None
    url = await configuration.new_url()
    actor.log.info(f"Using Apify proxy ({', '.join(groups) if groups else 'auto'}).")
    return url
