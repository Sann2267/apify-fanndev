"""Input coercion, envelope helpers and proxy wiring."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from src.constants import CONTENT_FIELDS, RECORD_ERROR


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def string_list(value: Any) -> list[str]:
    """Accept a list, a comma/newline separated string, or a list of {url} dicts."""
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
            item = item.get("url") or item.get("value") or item.get("slug")
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


_SLUG_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def normalise_post_reference(raw: str) -> str:
    """Turn a post URL, slug or numeric id into the path segment the API wants.

    ``/posts/<x>`` resolves both slugs and numeric ids, so a single segment is
    all that is ever needed. Article URLs on this site come in two shapes --
    ``/news/<slug>`` and bare ``/<slug>`` -- and both carry the slug last.
    """
    text = (raw or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        path = urlparse(text).path
        segments = [s for s in path.split("/") if s]
        text = segments[-1] if segments else ""
    return text.strip("/")


def normalise_slug(raw: str) -> str:
    """Category / tag / company slug from a slug or a URL."""
    text = (raw or "").strip()
    if text.startswith(("http://", "https://")):
        segments = [s for s in urlparse(text).path.split("/") if s]
        text = segments[-1] if segments else ""
    return text.strip("/").lower()


def is_safe_segment(value: str) -> bool:
    """Guard against a slug that would escape its route."""
    return bool(value) and bool(_SLUG_SAFE.match(value)) and ".." not in value


def envelope(
    payload: dict,
    *,
    input_value: str,
    source: str,
    record_type: str,
    include_content: bool = False,
    extra: dict | None = None,
) -> dict:
    """Wrap an upstream object in the portfolio dataset envelope.

    Upstream fields pass through verbatim -- no renaming -- so that a field
    Tech in Asia adds tomorrow flows to the dataset without a code change.
    """
    # The _* namespace belongs to the envelope. Algolia ships _highlightResult
    # and _snippetResult on every hit -- highlight markup, not data -- and
    # letting upstream keys through here would also let them shadow _source.
    body = {k: v for k, v in payload.items() if not k.startswith("_")}
    if not include_content:
        for field in CONTENT_FIELDS:
            body.pop(field, None)
    record = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }
    if extra:
        record.update(extra)
    record.update(body)
    return record


def error_record(
    input_value: str,
    error_kind: str,
    detail: str = "",
    *,
    mode: str | None = None,
) -> dict:
    record = {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "recordType": RECORD_ERROR,
        "_error": error_kind,
    }
    if detail:
        record["_errorDetail"] = detail[:1500]
    if mode:
        record["mode"] = mode
    return record


async def proxy_url_from(actor: Any, actor_input: dict) -> str | None:
    """Build a proxy URL only if the buyer asked for one.

    Tech in Asia has no WAF and no IP gate -- every surface this actor touches
    answered an unproxied datacenter request during recon -- so proxying is off
    by default rather than billed for nothing.
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
    except Exception as exc:  # noqa: BLE001 - a proxy problem must not end the run
        actor.log.warning(f"Proxy configuration failed ({exc}) -- continuing direct.")
        return None
    if configuration is None:
        actor.log.warning(
            "Proxy requested but unavailable on this account -- continuing direct. "
            "Tech in Asia has no IP gate, so this is usually fine."
        )
        return None
    url = await configuration.new_url()
    actor.log.info(f"Using Apify proxy ({', '.join(groups) if groups else 'auto'}).")
    return url
