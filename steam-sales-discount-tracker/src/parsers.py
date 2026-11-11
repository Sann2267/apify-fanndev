"""Pure parsing: upstream payloads -> records. No I/O here."""

from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timezone
from typing import Any

from .constants import ITEM_TYPES, STORE, STORE_APP_TYPES


class UnexpectedShape(Exception):
    """Upstream changed its layout. Raised instead of emitting hollow records."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def unix_to_iso(ts: int | float | str | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(input_value: str, source: str, record_type: str, **payload: Any) -> dict[str, Any]:
    return {"_input": input_value, "_source": source, "_scrapedAt": utc_now_iso(), "recordType": record_type, **payload}


def error_record(input_value: str, kind: str, detail: str = "", **extra: Any) -> dict[str, Any]:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "recordType": "ERROR",
        "_error": kind,
        "_errorDetail": detail,
        **extra,
    }


def cents_to_amount(cents: int | None) -> float | None:
    return None if cents is None else round(cents / 100, 2)


_NUM = re.compile(r"\d[\d.,\s  ']*")


def price_text_to_cents(text: str | None) -> int | None:
    """'$24.99' -> 2499, '24,99€' -> 2499, 'Rp 119 999' -> 11999900, '¥ 1,980' -> 198000.

    Steam's own cents convention: whole-unit currencies are still x100
    (appdetails IDR initial = 11999900), so every amount is multiplied by 100.
    A separator followed by exactly two trailing digits is the decimal mark.
    """
    if not text:
        return None
    m = _NUM.search(text)
    if not m:
        return None
    raw = re.sub(r"[\s  ']", "", m.group(0)).rstrip(".,")
    dec = re.search(r"[.,](\d{2})$", raw)
    if dec:
        whole = re.sub(r"[.,]", "", raw[: dec.start()]) or "0"
        return int(whole) * 100 + int(dec.group(1))
    whole = re.sub(r"[.,]", "", raw)
    return int(whole) * 100 if whole else None


# --------------------------------------------------------------------------- input resolution

_APP_URL = re.compile(r"(?:store\.steampowered\.com|steamdb\.info|steamcommunity\.com)/app/(\d+)", re.I)


def parse_app_ref(value: Any) -> tuple[int | None, str | None]:
    """Return (appid, None) for ids/URLs, or (None, search_term) for a game name."""
    if isinstance(value, int):
        return (value, None) if value > 0 else (None, None)
    s = str(value or "").strip()
    if not s:
        return None, None
    if s.isdigit():
        return int(s), None
    m = _APP_URL.search(s)
    if m:
        return int(m.group(1)), None
    if s.lower().startswith(("http://", "https://")):
        return None, None
    return None, s


_SALE_URL = re.compile(r"store\.steampowered\.com/sale/([^/?#]+)", re.I)


def parse_sale_ref(value: Any) -> str | None:
    """'https://store.steampowered.com/sale/MachineGamesDevSale?x' or 'MachineGamesDevSale' -> slug."""
    s = str(value or "").strip()
    m = _SALE_URL.search(s)
    if m:
        return m.group(1)
    if s and re.fullmatch(r"[A-Za-z0-9_\-]+", s):
        return s
    return None


# --------------------------------------------------------------------------- search results HTML

_ROW_SPLIT = re.compile(r'<a href="https://store\.steampowered\.com/')
_ATTR = {
    "itemKey": re.compile(r'data-ds-itemkey="([^"]+)"'),
    "appid": re.compile(r'data-ds-appid="([^"]+)"'),
    "tagids": re.compile(r'data-ds-tagids="\[([^\]]*)\]"'),
    # The discount block's own data-price-final is the displayed price; the outer
    # div's value excludes a bundle-owner discount (Silver Pines DE: 2249 vs 2199).
    "priceFinal": re.compile(r'discount_block[^>]*data-price-final="(\d+)"'),
    "priceFinalOuter": re.compile(r'data-price-final="(\d+)"'),
    "packageid": re.compile(r'data-ds-packageid="(\d+)"'),
    "bundleid": re.compile(r'data-ds-bundleid="(\d+)"'),
    "discount": re.compile(r'data-discount="(\d+)"'),
    "bundleDiscount": re.compile(r'data-bundlediscount="(\d+)"'),
}
_TITLE = re.compile(r'<span class="title">(.*?)</span>', re.S)
_RELEASED = re.compile(r'<div class="search_released[^"]*">\s*(.*?)\s*</div>', re.S)
_REVIEW = re.compile(r'search_review_summary (\w+)" data-tooltip-html="([^"]+)"')
_REVIEW_NUM = re.compile(r"(\d+)% of the ([\d,.\s]+) user reviews")
_ORIG = re.compile(r'<div class="discount_original_price">(.*?)</div>')
_FINAL = re.compile(r'<div class="discount_final_price[^"]*">(.*?)</div>')
_PLATFORM = re.compile(r'platform_img (\w+)')
_IMG = re.compile(r'<div class="search_capsule"><img src="([^"]+)"')
_URL = re.compile(r'^([^"?]+)')


def parse_search_rows(results_html: str) -> list[dict[str, Any]]:
    """/search/results/?infinite=1 -> one dict per row (apps only on the specials list)."""
    rows = []
    for chunk in _ROW_SPLIT.split(results_html)[1:]:
        key = _ATTR["itemKey"].search(chunk)
        if not key:
            continue
        attrs = {k: (m.group(1) if (m := rx.search(chunk)) else None) for k, rx in _ATTR.items()}
        title = _TITLE.search(chunk)
        if not title or attrs["priceFinalOuter"] is None:
            raise UnexpectedShape(f"search row {key.group(1)}: title or data-price-final missing")
        review = _REVIEW.search(chunk)
        review_text = html.unescape(review.group(2)) if review else None
        review_num = _REVIEW_NUM.search(review_text or "")
        orig_text = (o.group(1).strip() if (o := _ORIG.search(chunk)) else None)
        final_text = (f.group(1).strip() if (f := _FINAL.search(chunk)) else None)
        # An empty discount block (no prices at all) = item listed without a
        # purchasable price (e.g. an expansion sold only as an upgrade): null, not 0.
        priced = final_text is not None
        final_cents = int(attrs["priceFinal"] or attrs["priceFinalOuter"]) if priced else None
        orig_cents = price_text_to_cents(orig_text) if priced else None
        item_key = key.group(1)
        kind, _, item_id = item_key.partition("_")
        appids = [int(a) for a in (attrs["appid"] or "").split(",") if a.strip().isdigit()]
        released = _RELEASED.search(chunk)
        rows.append({
            "itemKey": item_key,
            "itemType": {"app": "app", "sub": "package", "bundle": "bundle"}.get(kind.lower(), kind.lower()),
            "id": int(item_id) if item_id.isdigit() else None,
            "appid": appids[0] if kind == "App" and appids else None,
            "packageId": int(attrs["packageid"]) if attrs["packageid"] else None,
            "bundleId": int(attrs["bundleid"]) if attrs["bundleid"] else None,
            "includedAppids": appids,
            "name": html.unescape(title.group(1)).strip(),
            "storeUrl": f"{STORE}/{_URL.match(chunk).group(1)}",
            "discountPct": int(attrs["discount"] or 0),
            "finalPriceCents": final_cents,
            "originalPriceCents": orig_cents if orig_cents is not None else final_cents,
            "priceAvailable": priced,
            "finalPriceFormatted": html.unescape(final_text) if final_text else None,
            "originalPriceFormatted": html.unescape(orig_text) if orig_text else None,
            "isBundleDiscount": attrs["bundleDiscount"] not in (None, "0"),
            "releaseDate": (html.unescape(released.group(1)).strip() or None) if released else None,
            "reviewSummary": review_text.split("<br>")[0] if review_text else None,
            "reviewScoreClass": review.group(1) if review else None,
            "reviewPositivePct": int(review_num.group(1)) if review_num else None,
            "reviewCount": int(re.sub(r"\D", "", review_num.group(2))) if review_num else None,
            "platforms": sorted(set(_PLATFORM.findall(chunk))),
            "tagIds": [int(t) for t in (attrs["tagids"] or "").split(",") if t.strip().isdigit()],
            "capsuleImage": (i.group(1) if (i := _IMG.search(chunk)) else None),
        })
    return rows


# --------------------------------------------------------------------------- IStoreBrowseService/GetItems

_PRESET = re.compile(r"^#discount_desc_preset_(\w+)$")


def _int(v: Any) -> int | None:
    try:
        return None if v is None else int(v)
    except (TypeError, ValueError):
        return None


def discount_details(item: dict[str, Any] | None) -> dict[str, Any]:
    """Flat discount fields from a GetItems store item. Raw best_purchase_option is kept too."""
    if not item or item.get("success") != 1:
        return {"storeItemFound": False}
    best = item.get("best_purchase_option") or {}
    active = best.get("active_discounts") or []
    ends = [d.get("discount_end_date") for d in active if d.get("discount_end_date")]
    # Free-to-keep giveaways carry no active_discounts: the end is free_to_keep_ends.
    ftk = bool(best.get("is_free_to_keep", False))
    if ftk and best.get("free_to_keep_ends"):
        ends.append(best["free_to_keep_ends"])
    descs = list(dict.fromkeys(d.get("discount_description") for d in active if d.get("discount_description")))
    preset = next((m.group(1) for d in descs if (m := _PRESET.match(d))), None)
    labels = [d for d in descs if not _PRESET.match(d)]
    release = item.get("release") or {}
    basic = item.get("basic_info") or {}
    return {
        "storeItemFound": True,
        "itemName": item.get("name"),
        "appType": STORE_APP_TYPES.get(item.get("type")) if item.get("item_type") == 0 else None,
        "discountEndsAt": unix_to_iso(min(ends)) if ends else None,
        "discountEndsAtUnix": min(ends) if ends else None,
        # Steam preset (special / weekend / launch / weeklong / ...) or a named
        # publisher campaign ("Two Point Franchise - Weekend Deal").
        "discountType": "free_to_keep" if ftk else preset or ("named_campaign" if labels else None),
        "discountLabel": labels[0] if labels else None,
        "isFreeToKeep": ftk,
        "packageId": _int(best.get("packageid")),
        "bundleId": _int(best.get("bundleid")),
        "purchaseOptionName": best.get("purchase_option_name"),
        "finalPriceCentsGetItems": _int(best.get("final_price_in_cents")),
        "originalPriceCentsGetItems": _int(best.get("original_price_in_cents")),
        "discountPctGetItems": best.get("discount_pct"),
        "hideDiscountPctForCompliance": bool(best.get("hide_discount_pct_for_compliance", False)),
        "includedGameCount": best.get("included_game_count"),
        "purchaseOptionsCount": len(item.get("purchase_options") or []) or None,
        "discountedPurchaseOptions": [
            {
                "name": po.get("purchase_option_name"),
                "packageId": _int(po.get("packageid")),
                "bundleId": _int(po.get("bundleid")),
                "finalPriceCents": _int(po.get("final_price_in_cents")),
                "originalPriceCents": _int(po.get("original_price_in_cents")),
                "discountPct": po.get("discount_pct"),
                "bundleDiscountPct": po.get("bundle_discount_pct"),
            }
            for po in item.get("purchase_options") or []
            if po.get("discount_pct")
        ],
        "releaseDateGetItems": unix_to_iso(release.get("steam_release_date")),
        "isEarlyAccess": bool(release.get("is_early_access", False)),
        "developers": [d.get("name") for d in basic.get("developers") or [] if d.get("name")],
        "publishers": [p.get("name") for p in basic.get("publishers") or [] if p.get("name")],
    }


def store_item_key(item: dict[str, Any]) -> tuple[str, int] | None:
    kind = ITEM_TYPES.get(item.get("item_type", 0))
    ident = item.get("appid") if kind == "app" else item.get("id")
    if kind is None or ident is None:
        return None
    return kind, int(ident)


# --------------------------------------------------------------------------- featuredcategories

def parse_featured(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(data, dict) or data.get("status") != 1:
        raise UnexpectedShape(f"featuredcategories: status={data.get('status') if isinstance(data, dict) else type(data)}")
    out: dict[str, list[dict[str, Any]]] = {"spotlights": [], "dailyDeals": [], "specials": []}
    for key, block in data.items():
        if not isinstance(block, dict):
            continue
        cat = block.get("id")
        if cat == "cat_spotlight":
            out["spotlights"].extend(block.get("items") or [])
        elif cat == "cat_dailydeal":
            out["dailyDeals"].extend(block.get("items") or [])
        elif cat == "cat_specials" or key == "specials":
            out["specials"].extend(block.get("items") or [])
    if not out["specials"] and not out["spotlights"] and not out["dailyDeals"]:
        raise UnexpectedShape("featuredcategories: no spotlight, daily deal or specials block found")
    return out


_STORE_TARGET = re.compile(r"store\.steampowered\.com/(app|sub|bundle|sale)/([^/?#]+)", re.I)


def spotlight_target(url: str | None) -> tuple[str | None, str | None]:
    """Spotlight link -> ('app', '1808500') / ('sale', 'MachineGamesDevSale') / (None, None)."""
    m = _STORE_TARGET.search(url or "")
    return (m.group(1).lower(), m.group(2)) if m else (None, None)


# --------------------------------------------------------------------------- /sale/<name> pages

_EVENTSTORE = re.compile(r'data-partnereventstore="([^"]+)"')
_CAPSULE_KIND = {"sub": "package", "bundle": "bundle"}


def _walk_capsules(node: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "capsules" and isinstance(v, list):
                out.extend(c for c in v if isinstance(c, dict) and c.get("id"))
            else:
                _walk_capsules(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_capsules(v, out)


def parse_sale_page(page: str) -> dict[str, Any]:
    """Curated sale page -> event metadata + every capsule (game/dlc/music/sub/bundle) it lists."""
    m = _EVENTSTORE.search(page)
    if not m:
        raise UnexpectedShape("sale page: data-partnereventstore attribute not found")
    events = json.loads(html.unescape(m.group(1)))
    if not isinstance(events, list) or not events:
        raise UnexpectedShape("sale page: partnereventstore is empty")
    ev = events[0]
    jd = json.loads(ev.get("jsondata") or "{}")
    sections = jd.get("sale_sections") or []
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    dynamic = 0
    for idx, sec in enumerate(sections):
        caps: list[dict[str, Any]] = []
        _walk_capsules(sec, caps)
        if not caps and sec.get("section_type") not in ("unselected_empty", "curator", "text_section", "events"):
            dynamic += 1
        for c in caps:
            kind = _CAPSULE_KIND.get(c.get("type"), "app")
            key = (kind, int(c["id"]))
            if key in seen:
                continue
            seen.add(key)
            items.append({"itemType": kind, "id": int(c["id"]), "capsuleType": c.get("type"), "sectionIndex": idx,
                          "sectionType": sec.get("section_type")})
    return {
        "saleName": ev.get("event_name"),
        "saleGid": ev.get("gid"),
        "clanSteamId": ev.get("clan_steamid"),
        "eventType": ev.get("event_type"),
        "saleStartsAt": unix_to_iso(ev.get("rtime32_start_time")),
        "saleEndsAt": unix_to_iso(ev.get("rtime32_end_time")),
        "saleStartsAtUnix": ev.get("rtime32_start_time"),
        "saleEndsAtUnix": ev.get("rtime32_end_time"),
        "sectionCount": len(sections),
        "dynamicSectionCount": dynamic,
        "items": items,
    }


# --------------------------------------------------------------------------- partner "Upcoming Steam Events"

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_TOKENS = re.compile(r"[A-Za-z]+|\d+")


def _side(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for tok in _TOKENS.findall(text):
        if tok.isdigit():
            n = int(tok)
            if n >= 1000:
                out["y"] = n
            elif 1 <= n <= 31:
                out["d"] = n
        elif tok[:3].lower() in _MONTHS:
            out["m"] = _MONTHS[tok[:3].lower()]
    return out


def parse_date_range(text: str, default_year: int | None = None) -> tuple[str | None, str | None]:
    """'17 December, 2026 - 4 January, 2027' / 'October 19 - October 26, 2026' /
    'June 14 - 21, 2027' / 'Oct 12<br>Oct 19' (+ default_year) -> ISO dates. 'TBD' -> (None, None)."""
    parts = re.split(r"\s+-\s+|<br\s*/?>|\s+–\s+", text, maxsplit=1)
    if len(parts) != 2:
        return None, None
    a, b = _side(parts[0]), _side(parts[1])
    if "d" not in a or "d" not in b:
        return None, None
    b.setdefault("m", a.get("m"))
    a.setdefault("m", b.get("m"))
    if not a.get("m"):
        return None, None
    if "y" not in a and "y" not in b:
        # Table rows ('Dec 28<br>Jan 4' under '2026 Fests'): the year is the START year.
        if default_year is None:
            return None, None
        a["y"] = default_year
        b["y"] = default_year + 1 if b["m"] < a["m"] else default_year
    b.setdefault("y", a.get("y"))
    a.setdefault("y", b["y"] - 1 if a["m"] > b["m"] else b["y"])
    try:
        return date(a["y"], a["m"], a["d"]).isoformat(), date(b["y"], b["m"], b["d"]).isoformat()
    except ValueError:
        return None, None


_STRIP = re.compile(r"<[^>]+>")
_H2 = re.compile(r'<h2 class="bb_(section|subsection)">(.*?)</h2>', re.S)
_HREF = re.compile(r'href="([^"]+)"')


def _txt(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_STRIP.sub(" ", s))).strip()


def parse_event_calendar(page: str) -> list[dict[str, Any]]:
    i = page.find('class="documentation_bbcode"')
    if i < 0:
        raise UnexpectedShape("event calendar: documentation_bbcode block not found")
    body = page[i:]
    end = body.find('<div id="hashLocationHighlight"')
    body = body[: end if end > 0 else len(body)]
    events: list[dict[str, Any]] = []
    section = None
    year_ctx: int | None = None
    heads = list(_H2.finditer(body))
    for n, h in enumerate(heads):
        kind, inner = h.group(1), h.group(2)
        text = _txt(inner)
        tail = body[h.end(): heads[n + 1].start() if n + 1 < len(heads) else len(body)]
        if kind == "section":
            low = text.lower()
            section = "seasonal_sale" if "seasonal" in low else "themed_fest" if "fest" in low and "next" not in low else "next_fest" if "next fest" in low else "other"
            continue
        if re.fullmatch(r"\d{4}( Fests)?", text):
            year_ctx = int(text[:4])
            if section == "themed_fest" and "<table" in tail:
                for row in re.findall(r"<tr>(.*?)</tr>", tail, re.S):
                    cells = re.findall(r"<td>(.*?)</td>", row, re.S)
                    if len(cells) < 2:
                        continue
                    start, finish = parse_date_range(cells[0], year_ctx)
                    links = _HREF.findall(row)
                    events.append({
                        "eventType": "themed_fest",
                        "name": _txt(cells[1]),
                        "datesText": _txt(cells[0].replace("<br>", " - ")),
                        "startDate": start, "endDate": finish,
                        "description": re.sub(r"\s*More info\s*\.?$", "", _txt(cells[3])) if len(cells) > 3 else None,
                        "registrationUrl": next((u for u in links if "/optin/" in u), None),
                        "infoUrl": next((u for u in links if "/doc/" in u), None),
                    })
            continue
        if "|" in text:
            name, _, dates = (p.strip() for p in text.partition("|"))
            start, finish = parse_date_range(dates, year_ctx)
            links = _HREF.findall(tail)
            events.append({
                "eventType": section or "other",
                "name": name,
                "datesText": dates,
                "startDate": start, "endDate": finish,
                "description": None,
                "registrationUrl": next((u for u in links if "/optin/" in u), None),
                "infoUrl": next((u for u in links if "/doc/" in u), None),
            })
    if not events:
        raise UnexpectedShape("event calendar: no dated events parsed")
    return events


# --------------------------------------------------------------------------- ECB FX

_FX = re.compile(r"currency='(\w{3})' rate='([\d.]+)'")
_FX_TIME = re.compile(r"time='([\d-]+)'")


def parse_ecb(xml: str) -> tuple[str | None, dict[str, float]]:
    rates = {c: float(r) for c, r in _FX.findall(xml)}
    if "USD" not in rates:
        raise UnexpectedShape("ECB feed: USD rate missing")
    rates["EUR"] = 1.0
    t = _FX_TIME.search(xml)
    return (t.group(1) if t else None), rates
