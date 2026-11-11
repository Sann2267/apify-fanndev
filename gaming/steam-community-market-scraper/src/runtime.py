"""Input coercion, item parsing and proxy wiring."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse

from src.constants import APP_ALIASES

GROUP_ID_RE = re.compile(r"^G[0-9A-F]{6,}$")

# The market prices in the exit IP's currency, so "currency" is really a
# proxy-country choice. One representative country per currency.
CURRENCY_COUNTRY = {
    "USD": "US", "EUR": "DE", "GBP": "GB", "CAD": "CA", "AUD": "AU", "NZD": "NZ",
    "JPY": "JP", "KRW": "KR", "CNY": "CN", "HKD": "HK", "TWD": "TW", "SGD": "SG",
    "MYR": "MY", "IDR": "ID", "PHP": "PH", "THB": "TH", "VND": "VN", "INR": "IN",
    "BRL": "BR", "MXN": "MX", "CLP": "CL", "PEN": "PE", "COP": "CO", "ARS": "AR",
    "UYU": "UY", "CRC": "CR", "PLN": "PL", "CHF": "CH", "NOK": "NO", "UAH": "UA",
    "TRY": "TR", "ZAR": "ZA", "SAR": "SA", "AED": "AE", "ILS": "IL", "KZT": "KZ",
    "KWD": "KW", "QAR": "QA", "RUB": "RU",
}


@dataclass(frozen=True)
class ItemRef:
    raw: str
    appid: int
    name: str  # market_hash_name, or a bucket-group id like "G1807209A023004"

    @property
    def is_group(self) -> bool:
        return bool(GROUP_ID_RE.match(self.name))


def string_list(value: Any) -> list[str]:
    """Accept a list, a newline-separated string, or Apify requestListSources dicts.

    Commas are NOT separators: market hash names contain them
    ("Sticker | Team Liquid, Holo | Katowice 2015" does not, but many TF2 and
    Dota names do), so splitting on them would corrupt real inputs.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [p.strip() for p in value.splitlines() if p.strip()]
    if isinstance(value, dict):
        value = [value]
    out: list[str] = []
    for item in value or []:
        if isinstance(item, dict):
            item = item.get("url") or item.get("value") or item.get("name")
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def dedupe(values: list) -> list:
    return list(dict.fromkeys(values))


def clamp(value: Any, low: int, high: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def optional_float(value: Any, field: str) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        raise ValueError(f"{field} must be a number like 0.15, got {value!r}")


def resolve_app(value: Any, default: int = 730) -> int:
    if value is None or value == "":
        return default
    text = str(value).strip().casefold()
    if text.isdigit():
        return int(text)
    if text in APP_ALIASES:
        return APP_ALIASES[text]
    raise ValueError(f"Unknown app {value!r}. Use a numeric Steam appid or one of: {', '.join(sorted(APP_ALIASES))}")


def parse_item(raw: str, default_app: int) -> ItemRef:
    """Market listing URL, bucket-group URL, or a bare market_hash_name."""
    text = raw.strip()
    if text.startswith(("http://", "https://", "steamcommunity.com", "www.steamcommunity.com")):
        url = text if text.startswith("http") else "https://" + text
        parts = [p for p in urlparse(url).path.split("/") if p]
        # /market/listings/<appid>/<name>[/<bucket>]
        if len(parts) >= 4 and parts[0] == "market" and parts[1] == "listings" and parts[2].isdigit():
            name = unquote(parts[3])
            if len(parts) >= 5:  # /G.../<variant hash name> -> the variant
                name = unquote(parts[4])
            return ItemRef(raw, int(parts[2]), name)
        raise ValueError("not a /market/listings/<appid>/<name> URL")
    return ItemRef(raw, default_app, text)


async def proxy_factory_from(actor: Any, actor_input: dict):
    """Return an async callable producing a fresh proxy URL, or None for direct.

    A new session id on every call means every rotation in the client is a new
    exit IP. Any failure degrades to a direct run instead of ending it:
    steamcommunity.com has no WAF, so direct is a working (if single-IP) mode.
    """
    cfg = dict(actor_input.get("proxyConfiguration") or {})
    currency = (actor_input.get("currency") or "").strip().upper()
    if not cfg.get("useApifyProxy"):
        if currency:
            actor.log.warning(
                f"currency={currency} needs Apify Proxy (Steam prices in the exit IP's "
                "currency). Proxy is off, so prices will be in this machine's local currency."
            )
        return None
    groups = cfg.get("apifyProxyGroups") or None
    country = cfg.get("apifyProxyCountry") or None
    if currency:
        if currency not in CURRENCY_COUNTRY:
            raise ValueError(f"Unsupported currency {currency!r}. Choose one of: {', '.join(sorted(CURRENCY_COUNTRY))}")
        country = CURRENCY_COUNTRY[currency]
    fallback_note = (
        f" Prices will be in this machine's local currency, not {currency}." if currency else ""
    )
    try:
        configuration = await actor.create_proxy_configuration(groups=groups, country_code=country)
    except Exception as exc:
        actor.log.warning(f"Proxy configuration failed ({exc}) -- continuing direct.{fallback_note}")
        return None
    if configuration is None:
        actor.log.warning(f"Proxy requested but unavailable on this account -- continuing direct.{fallback_note}")
        return None
    actor.log.info(f"Using Apify proxy groups={groups or 'auto'} country={country or 'any'}.")

    async def factory() -> str | None:
        try:
            return await configuration.new_url(session_id="s" + secrets.token_hex(6))
        except Exception as exc:
            actor.log.warning(f"Could not get a proxy URL ({exc}) -- this attempt goes direct.")
            return None

    return factory
