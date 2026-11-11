"""Dataset envelope plus the computed fields each mode adds.

Upstream field names pass through verbatim (``strHash``, ``cSellOrders``,
``amtMaxBuyOrder``, ``listingid``...). The fields added here are additions, not
replacements, and exist because the raw payload hides the answer to the
obvious question:

* every money amount is an integer in **hundredths** of the currency
  (``unPrice: 39597800`` + ``unFee: 5939700`` = "IDR 455,375"), so a decimal
  ``...Price`` field sits next to each one;
* the order book is a flat ``[price, qty, price, qty, ...]`` array, expanded
  here into ``{price, quantity, cumulativeQuantity}`` levels;
* a listing's float / pattern seed live in ``asset.asset_properties`` keyed by
  numeric property id, flattened here to ``floatValue`` / ``paintSeed``.
"""

from __future__ import annotations

import re
import statistics
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from src.constants import ASSET_PROPERTIES, BASE_URL, CURRENCIES, ICON_CDN

SOURCE = "S1-market-rpc"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_from_unix(ts: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError):
        return None


def envelope(raw_input: str, record_type: str, payload: dict, source: str = SOURCE) -> dict:
    return {
        "_input": raw_input,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
        **payload,
    }


def error_record(raw_input: str, error: str, detail: str) -> dict:
    return {
        "_input": raw_input,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "recordType": "ERROR",
        "_error": error,
        "_errorDetail": detail,
    }


# -- money -----------------------------------------------------------------


def money(amount: Any) -> float | None:
    """Integer hundredths -> decimal. ``None`` stays ``None``."""
    if amount is None or isinstance(amount, bool):
        return None
    try:
        return round(int(amount) / 100, 2)
    except (TypeError, ValueError):
        return None


def parse_price_text(text: Any) -> float | None:
    """"$1,114.78" / "1.114,78€" / "Rp 457 896" -> float. None if unparseable."""
    if not text:
        return None
    s = re.sub(r"[^\d.,]", "", str(text))
    if not s or not any(ch.isdigit() for ch in s):
        return None
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("." if dec == "," else ",", "").replace(",", ".")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = f"{head.replace(',', '')}.{tail}" if len(tail) in (1, 2) else s.replace(",", "")
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.rpartition(".")[2]) == 3):
        s = s.replace(".", "")
    try:
        return round(float(s.strip(".")), 2)
    except ValueError:
        return None


def currency_code(e_currency: Any) -> str | None:
    try:
        return CURRENCIES.get(int(e_currency))
    except (TypeError, ValueError):
        return None


def market_url(appid: Any, hash_name: str | None) -> str | None:
    if not hash_name:
        return None
    return f"{BASE_URL}/market/listings/{appid}/{quote(hash_name, safe='')}"


def icon_url(icon: str | None) -> str | None:
    if not icon:
        return None
    return icon if icon.startswith("http") else ICON_CDN + icon


def tag_map(tags: Any) -> dict:
    """``[{category, localized_tag_name}, ...]`` -> ``{category: name}``."""
    out: dict = {}
    for tag in tags or []:
        if isinstance(tag, dict) and tag.get("category"):
            out[tag["category"]] = tag.get("localized_tag_name") or tag.get("internal_name")
    return out


# -- search ------------------------------------------------------------------


def search_extras(row: dict) -> dict:
    desc = row.get("asset_description") or {}
    appid = desc.get("appid")
    hash_name = row.get("strHash") or desc.get("market_hash_name")
    return {
        "appid": appid,
        "marketHashName": hash_name,
        "name": desc.get("market_name") or desc.get("name"),
        "type": desc.get("type"),
        "sellListings": row.get("cSellOrders"),
        # Search carries the cheapest ask only as text ("$1,114.78"); the
        # integer fields beside it are the fee components, not the price.
        "minSellPrice": parse_price_text(row.get("strMinSellSubtotal")),
        "minSellPriceText": row.get("strMinSellSubtotal"),
        "minSellFee": money((row.get("unSteamFee") or 0) + (row.get("unPublisherFee") or 0)),
        "currency": currency_code(row.get("eCurrency")),
        "commodity": desc.get("commodity"),
        "bucketGroupId": desc.get("market_bucket_group_id"),
        "bucketGroupName": desc.get("market_bucket_group_name"),
        "iconUrl": icon_url(desc.get("icon_url")),
        "marketUrl": market_url(appid, hash_name),
    }


# -- description -------------------------------------------------------------


DESCRIPTION_KEEP = (
    "appid", "classid", "instanceid", "name", "market_name", "market_hash_name",
    "market_name_inside_group", "market_bucket_group_id", "market_bucket_group_name",
    "market_bucket_id", "type", "name_color", "background_color", "commodity",
    "marketable", "tradable", "market_tradable_restriction",
    "market_marketable_restriction", "sealed", "sealed_type", "tags",
)


def description_fields(desc: dict) -> dict:
    """The identity part of a description; drops the long HTML blurbs."""
    out = {k: desc.get(k) for k in DESCRIPTION_KEEP if k in desc}
    out["tagsByCategory"] = tag_map(desc.get("tags"))
    out["iconUrl"] = icon_url(desc.get("icon_url"))
    lines = []
    for d in desc.get("descriptions") or []:
        if not isinstance(d, dict) or d.get("name") == "blank":
            continue
        text = re.sub(r"<[^>]+>", " ", str(d.get("value") or ""))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            lines.append(text)
    out["descriptionText"] = "\n".join(lines) or None
    return out


# -- price history -----------------------------------------------------------


def history_points(data: dict, days: int) -> list[dict]:
    """Normalised points, oldest first, optionally limited to the last N days."""
    prices = data.get("prices") or []
    if days and prices:
        cutoff = int(datetime.now(timezone.utc).timestamp()) - days * 86400
        prices = [p for p in prices if (p.get("time") or 0) >= cutoff]
    return [
        {
            "time": iso_from_unix(p.get("time")),
            "unixTime": p.get("time"),
            "medianPrice": round(float(p["price_median"]), 4) if p.get("price_median") is not None else None,
            "volume": p.get("purchases"),
        }
        for p in prices
    ]


def _window(prices: list[dict], now: int, seconds: int) -> tuple[float | None, int]:
    sel = [p for p in prices if (p.get("time") or 0) >= now - seconds and p.get("price_median") is not None]
    if not sel:
        return None, 0
    volume = sum(int(p.get("purchases") or 0) for p in sel)
    # Volume-weighted median price across the window's buckets.
    if volume:
        avg = sum(float(p["price_median"]) * int(p.get("purchases") or 0) for p in sel) / volume
    else:
        avg = statistics.fmean(float(p["price_median"]) for p in sel)
    return round(avg, 4), volume


def _daily_vwap(prices: list[dict]) -> list[dict]:
    days: dict[int, list[float]] = {}
    for p in prices:
        day = int(p.get("time") or 0) // 86400 * 86400
        qty = int(p.get("purchases") or 0)
        acc = days.setdefault(day, [0.0, 0, 0.0, 0])
        acc[0] += float(p["price_median"]) * qty
        acc[1] += qty
        acc[2] += float(p["price_median"])
        acc[3] += 1
    return [
        {"time": day, "price_median": (s / q) if q else (raw / n), "purchases": q}
        for day, (s, q, raw, n) in sorted(days.items())
    ]


def history_stats(data: dict) -> dict:
    prices = [p for p in (data.get("prices") or []) if p.get("price_median") is not None]
    if not prices:
        return {"historyPoints": 0}
    now = int(datetime.now(timezone.utc).timestamp())
    last = prices[-1]
    # Extremes are taken over volume-weighted *daily* prices. The most recent
    # month is hourly, and a single odd sale in a 1-sale hour (a sticker-laden
    # copy, a fat-fingered buy) otherwise becomes a 10x "all-time high".
    daily = _daily_vwap(prices)
    ath = max(daily, key=lambda p: p["price_median"])
    atl = min(daily, key=lambda p: p["price_median"])
    stats: dict = {
        "historyPoints": len(prices),
        "firstSaleDate": iso_from_unix(prices[0].get("time")),
        "lastSaleDate": iso_from_unix(last.get("time")),
        "lastMedianPrice": round(float(last["price_median"]), 4),
        "allTimeHigh": round(float(ath["price_median"]), 4),
        "allTimeHighDate": iso_from_unix(ath.get("time")),
        "allTimeLow": round(float(atl["price_median"]), 4),
        "allTimeLowDate": iso_from_unix(atl.get("time")),
        "totalVolume": sum(int(p.get("purchases") or 0) for p in prices),
    }
    for label, seconds in (("24h", 86400), ("7d", 7 * 86400), ("30d", 30 * 86400), ("90d", 90 * 86400), ("365d", 365 * 86400)):
        avg, volume = _window(prices, now, seconds)
        stats[f"avgPrice{label}"] = avg
        stats[f"volume{label}"] = volume
    p30, p7 = stats.get("avgPrice30d"), stats.get("avgPrice7d")
    stats["change7dVs30dPct"] = round((p7 - p30) / p30 * 100, 2) if p7 and p30 else None
    return stats


# -- order book --------------------------------------------------------------


def expand_levels(compact: Any, depth: int) -> list[dict]:
    """``[price, qty, price, qty, ...]`` -> levels with running depth."""
    levels: list[dict] = []
    if not isinstance(compact, list):
        return levels
    cumulative = 0
    for i in range(0, len(compact) - 1, 2):
        qty = int(compact[i + 1] or 0)
        cumulative += qty
        levels.append({"price": money(compact[i]), "quantity": qty, "cumulativeQuantity": cumulative})
        if depth and len(levels) >= depth:
            break
    return levels


def orderbook_summary(book: dict) -> dict:
    bid, ask = money(book.get("amtMaxBuyOrder")), money(book.get("amtMinSellOrder"))
    spread = round(ask - bid, 2) if bid is not None and ask is not None else None
    buy = book.get("rgCompactBuyOrders") or []
    sell = book.get("rgCompactSellOrders") or []
    return {
        "currency": currency_code(book.get("eCurrency")),
        "highestBuyOrder": bid,
        "lowestSellOrder": ask,
        "spread": spread,
        "spreadPct": round(spread / ask * 100, 2) if spread is not None and ask else None,
        "buyOrderQuantity": book.get("cBuyOrders"),
        "sellOrderQuantity": book.get("cSellOrders"),
        "buyPriceLevels": len(buy) // 2,
        "sellPriceLevels": len(sell) // 2,
    }


# -- listings ----------------------------------------------------------------


def listing_extras(listing: dict) -> dict:
    asset = listing.get("asset") or {}
    props: dict = {}
    for prop in asset.get("asset_properties") or []:
        pid = prop.get("propertyid")
        key = ASSET_PROPERTIES.get(pid, f"property{pid}")
        for vkey in ("float_value", "int_value", "string_value"):
            if vkey in prop:
                value = prop[vkey]
                props[key] = int(value) if vkey == "int_value" and str(value).lstrip("-").isdigit() else value
                break
    stickers, charms = [], []
    for acc in asset.get("asset_accessories") or []:
        d = acc.get("description") or {}
        name = d.get("market_name") or d.get("name")
        wear = next((p.get("float_value") for p in acc.get("parent_relationship_properties") or [] if p.get("propertyid") == 4), None)
        entry = {"name": name, "classid": acc.get("classid")}
        if wear is not None:
            entry["wear"] = wear
        (charms if "Charm" in (d.get("type") or "") else stickers).append(entry)
    desc = listing.get("description") or {}
    total = None
    if listing.get("unPrice") is not None:
        total = money(int(listing.get("unPrice") or 0) + int(listing.get("unFee") or 0))
    return {
        "appid": desc.get("appid"),
        "marketHashName": desc.get("market_hash_name"),
        "price": total,  # what a buyer pays
        "sellerReceives": money(listing.get("unPrice")),
        "fee": money(listing.get("unFee")),
        "currency": currency_code(listing.get("eCurrency")),
        "assetId": asset.get("assetid") or asset.get("id"),
        **props,
        "stickers": stickers,
        "charms": charms,
        "inspectImages": [a.get("url") for a in listing.get("enhanced_appearances") or [] if a.get("url")],
        "marketUrl": market_url(desc.get("appid"), desc.get("market_hash_name")),
    }


def slim_listing(listing: dict, keep_description: bool) -> dict:
    """Raw listing with the per-listing description optionally reduced."""
    out = dict(listing)
    if not keep_description and isinstance(out.get("description"), dict):
        out["description"] = {k: v for k, v in out["description"].items() if k in DESCRIPTION_KEEP}
    if not keep_description and isinstance(out.get("asset"), dict):
        asset = dict(out["asset"])
        asset["asset_accessories"] = [
            {k: v for k, v in acc.items() if k != "description"} for acc in asset.get("asset_accessories") or []
        ]
        out["asset"] = asset
    return out


# -- recent sales ------------------------------------------------------------


def sale_extras(sale: dict) -> dict:
    listing = sale.get("listing") or {}
    desc = listing.get("description") or {}
    app = sale.get("app") or {}
    return {
        "appid": desc.get("appid") or app.get("appid"),
        "appName": app.get("strName"),
        "marketHashName": desc.get("market_hash_name"),
        "name": desc.get("market_name") or desc.get("name"),
        "type": desc.get("type"),
        "soldAt": iso_from_unix(sale.get("rtSold")),
        "soldPrice": parse_price_text(sale.get("strSoldPrice")),
        "soldPriceText": sale.get("strSoldPrice"),  # in the exit IP's currency
        "listingId": listing.get("listingid"),
        "iconUrl": icon_url(desc.get("icon_url")),
        "marketUrl": market_url(desc.get("appid") or app.get("appid"), desc.get("market_hash_name")),
    }
