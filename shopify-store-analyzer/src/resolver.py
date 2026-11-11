"""Turn a user-supplied URL into a working Shopify catalogue origin.

Four things make this harder than "append /products.json to the URL", all
measured during recon:

1. **www and apex are not interchangeable.** `www.gymshark.com/products.json`
   returns 403 while apex `gymshark.com/products.json` returns 200. Both roots
   load fine, so the difference only shows up on the JSON path.
2. **Stores geo-redirect.** `gymshark.com/` lands on `us.checkout.gymshark.com`
   depending on the exit IP, which is a different storefront from the one the
   user typed. We report both so the output is never quietly about another shop.
3. **The .myshopify.com rescue.** Headless storefronts commonly 404
   /products.json on the custom domain while the canonical Shopify domain still
   serves the whole catalogue -- `ruggable.com` 404s, `ruggable.myshopify.com`
   returns all 2,575 products. The canonical domain comes from /meta.json when
   that works, and from an HTML scan otherwise.
4. **Decoy 200s.** A JSON path can answer 200 with an HTML page, so a candidate
   only counts as working when it returns real JSON of the expected shape.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .client import HttpError, NotJson, ShopifyClient
from .constants import (
    BODY_MARKERS,
    HEADLESS_MARKERS,
    PATH_META,
    PATH_PRODUCTS,
    POWERED_BY_HEADER,
)

log = logging.getLogger(__name__)

_MYSHOPIFY_RE = re.compile(r"\b([a-z0-9][a-z0-9-]*\.myshopify\.com)\b", re.I)
_THEME_RE = re.compile(r"Shopify\.theme\s*=\s*(\{.*?\})\s*;", re.S)
_ORIGIN_RE = re.compile(r"^(https?://[^/]+)")


class InvalidStoreUrl(ValueError):
    """The input could not be read as a URL or hostname."""


class DomainUnreachable(Exception):
    """No homepage could be loaded at all -- DNS failure, dead host, hard block.

    Distinct from NotShopify on purpose: when qualifying a list of domains, a
    dead domain reported as "not Shopify" is a wrong answer, not a missing one.
    """


class NotShopify(Exception):
    """The site loads but shows no sign of being a Shopify storefront."""


class NoCatalogueApi(Exception):
    """Confirmed Shopify, but no reachable public catalogue endpoint."""


@dataclass
class StoreProfile:
    requested_url: str
    requested_domain: str
    resolved_origin: str            # origin whose homepage we actually read
    api_origin: str | None = None   # origin that serves /products.json
    is_shopify: bool = False
    confidence: str = "none"        # confirmed | likely | none
    powered_by: str = ""
    is_headless: bool = False
    marker_hits: int = 0
    myshopify_domain: str | None = None
    theme: dict | None = None
    meta: dict | None = None
    notes: list[str] = field(default_factory=list)


def normalise_input(raw: object) -> str:
    """Accept a URL, a bare hostname, or Apify's {"url": ...} start-URL object."""
    if isinstance(raw, dict):
        raw = raw.get("url") or raw.get("value") or ""
    if not isinstance(raw, str):
        raise InvalidStoreUrl(f"Expected a string or {{url}} object, got {type(raw).__name__}.")

    text = raw.strip()
    if not text:
        raise InvalidStoreUrl("Empty store URL.")
    if "://" not in text:
        text = "https://" + text

    parsed = urlparse(text)
    host = (parsed.netloc or "").strip().lower()
    if not host or "." not in host or " " in host:
        raise InvalidStoreUrl(f"{raw!r} is not a usable store URL.")
    return f"https://{host}"


def _strip_www(host: str) -> str:
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def _host_variants(origin: str) -> list[str]:
    """apex <-> www, both worth trying: they can behave differently on JSON paths."""
    host = urlparse(origin).netloc.lower()
    out = [f"https://{host}"]
    if host.startswith("www."):
        out.append(f"https://{host[4:]}")
    else:
        out.append(f"https://www.{host}")
    return out


def parse_theme(html: str) -> dict | None:
    """Extract the `Shopify.theme = {...}` object a Liquid storefront inlines.

    Absent on headless (Hydrogen) storefronts, which have no Liquid theme at all.
    """
    import json

    match = _THEME_RE.search(html)
    if not match:
        return None
    try:
        theme = json.loads(match.group(1))
    except (ValueError, TypeError):
        return None
    if not isinstance(theme, dict):
        return None

    store_id = theme.get("theme_store_id")
    # schema_name is the theme family (Dawn, Split, Horizon). Some merchants
    # blank it out on a heavily customised theme, so fall back to their label.
    name = theme.get("schema_name") or theme.get("name")
    return {
        "themeName": name,
        "themeLabel": theme.get("name"),
        "themeId": theme.get("id"),
        "themeStoreId": store_id,
        "themeSchemaName": theme.get("schema_name"),
        "themeSchemaVersion": theme.get("schema_version"),
        "themeRole": theme.get("role"),
        "isThemeStoreTheme": store_id is not None,
    }


async def _looks_like_catalogue(client: ShopifyClient, origin: str) -> bool:
    """True only when origin/products.json returns real Shopify-shaped JSON."""
    try:
        payload = await client.get_json(
            f"{origin}{PATH_PRODUCTS}?limit=1", allow_redirects=False
        )
    except (HttpError, NotJson) as exc:
        log.debug("catalogue probe %s: %s", origin, exc)
        return False
    return isinstance(payload, dict) and isinstance(payload.get("products"), list)


async def resolve_store(
    client: ShopifyClient, raw_url: str, require_catalogue: bool = True
) -> StoreProfile:
    """Identify the store and find an origin that serves its catalogue.

    `require_catalogue=False` stops after identification. The detect mode uses
    that: "is this Shopify, and which theme" is answerable without a catalogue,
    so a headless store with a private backend is a successful detection, not a
    failure -- and skipping the probe makes the mode several requests cheaper.
    """
    requested_origin = normalise_input(raw_url)
    requested_domain = urlparse(requested_origin).netloc

    profile = StoreProfile(
        requested_url=raw_url if isinstance(raw_url, str) else requested_origin,
        requested_domain=requested_domain,
        resolved_origin=requested_origin,
    )

    # -- 1. load a homepage, trying apex/www if the first variant fails --------
    html = ""
    resp = None
    for candidate in _host_variants(requested_origin):
        try:
            attempt = await client.get(candidate + "/", allow_redirects=True)
        except HttpError as exc:
            profile.notes.append(f"root {candidate} unreachable: {exc}")
            continue
        if attempt.status_code == 200:
            resp = attempt
            break
        profile.notes.append(f"root {candidate} returned {attempt.status_code}")

    if resp is None:
        raise DomainUnreachable(
            f"Could not load a homepage for {requested_domain} "
            f"({'; '.join(profile.notes) or 'no response'})."
        )

    html = resp.text or ""
    match = _ORIGIN_RE.match(str(resp.url))
    profile.resolved_origin = match.group(1) if match else requested_origin
    resolved_domain = urlparse(profile.resolved_origin).netloc
    # apex <-> www is routine normalisation and not worth a note. Only flag a
    # redirect that lands somewhere genuinely different (e.g. gymshark.com ->
    # us.checkout.gymshark.com), which can mean a region-specific storefront.
    if _strip_www(resolved_domain) != _strip_www(requested_domain):
        profile.notes.append(
            f"redirected to {profile.resolved_origin} (store may be locale-specific)"
        )

    # -- 2. platform detection ------------------------------------------------
    powered_by = resp.headers.get(POWERED_BY_HEADER) or ""
    profile.powered_by = powered_by
    lowered = powered_by.lower()
    profile.marker_hits = sum(html.count(marker) for marker in BODY_MARKERS)

    if "shopify" in lowered:
        profile.is_shopify, profile.confidence = True, "confirmed"
    elif profile.marker_hits > 0:
        profile.is_shopify, profile.confidence = True, "likely"

    profile.theme = parse_theme(html)
    # Headless = Shopify backend without a Liquid theme. The powered-by header
    # names Hydrogen/Oxygen outright; otherwise infer it from a missing theme.
    profile.is_headless = any(m in lowered for m in HEADLESS_MARKERS) or (
        profile.is_shopify and profile.theme is None
    )

    # -- 3. /meta.json: shop identity + the authoritative canonical domain -----
    for origin in dict.fromkeys([profile.resolved_origin, requested_origin]):
        try:
            meta = await client.get_json(f"{origin}{PATH_META}")
        except (HttpError, NotJson):
            continue
        if isinstance(meta, dict) and meta.get("id"):
            profile.meta = meta
            profile.myshopify_domain = meta.get("myshopify_domain")
            if not profile.is_shopify:
                profile.is_shopify, profile.confidence = True, "confirmed"
            break

    if profile.myshopify_domain is None:
        found = sorted({m.lower() for m in _MYSHOPIFY_RE.findall(html)})
        if found:
            profile.myshopify_domain = found[0]
            if len(found) > 1:
                profile.notes.append(f"multiple myshopify domains in page: {found[:4]}")

    # Headless storefronts commonly 404 /meta.json on the custom domain while the
    # canonical Shopify domain still serves it -- that is where shop name,
    # currency and country come from for those stores.
    if profile.meta is None and profile.myshopify_domain:
        try:
            meta = await client.get_json(f"https://{profile.myshopify_domain}{PATH_META}")
        except (HttpError, NotJson):
            meta = None
        if isinstance(meta, dict) and meta.get("id"):
            profile.meta = meta
            profile.confidence = "confirmed"
            profile.is_shopify = True

    if not profile.is_shopify:
        raise NotShopify(
            f"{requested_domain} shows no Shopify signals "
            f"(powered-by={powered_by!r}, body markers=0)."
        )

    if not require_catalogue:
        return profile

    # -- 4. find an origin that actually serves the catalogue -----------------
    candidates: list[str] = []
    for origin in (profile.resolved_origin, requested_origin):
        for variant in _host_variants(origin):
            if variant not in candidates:
                candidates.append(variant)
    if profile.myshopify_domain:
        canonical = f"https://{profile.myshopify_domain}"
        if canonical not in candidates:
            candidates.append(canonical)

    for candidate in candidates:
        if await _looks_like_catalogue(client, candidate):
            profile.api_origin = candidate
            break

    if profile.api_origin is None:
        raise NoCatalogueApi(
            f"{requested_domain} is Shopify ({profile.confidence}) but no public "
            f"catalogue endpoint answered. Tried: {candidates}. Headless stores "
            "with a private backend cannot be read without credentials."
        )

    if profile.api_origin != profile.resolved_origin:
        profile.notes.append(f"catalogue served from {profile.api_origin}")

    return profile
