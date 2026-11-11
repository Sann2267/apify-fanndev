"""Turn Shopee's flash-sale payloads into flat, numeric records.

The one thing worth doing carefully is money. Shopee quotes every price as an
integer scaled by 100,000 (`45955000000` means 459,550), and the discount it
reports is a string like ``"-39%"``. Handing either of those straight to a user
means they get a spreadsheet column they cannot sum. Everything here comes out
as a plain number.
"""

from datetime import datetime, timezone

from src.constants import CURRENCIES, PRICE_DIVISOR


def _money(value) -> float | None:
    """Shopee micro-units -> a plain number. ``45955000000`` -> ``459550.0``."""
    if value in (None, "", 0):
        return None if value is None or value == "" else 0.0
    try:
        return round(int(value) / PRICE_DIVISOR, 2)
    except (TypeError, ValueError):
        return None


def _epoch(value) -> str | None:
    """Unix seconds -> UTC ISO 8601."""
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return None


def _percent(value) -> float | None:
    """``"-39%"`` or ``39`` -> ``39.0``, as a positive magnitude."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(abs(value))
    text = str(value).strip().replace("%", "").replace("-", "")
    try:
        return float(text)
    except ValueError:
        return None


def parse_sessions(payload: dict) -> list[dict]:
    sessions = ((payload or {}).get("data") or {}).get("sessions") or []
    out = []
    for raw in sessions:
        if not isinstance(raw, dict):
            continue
        out.append({
            "promotionId": raw.get("promotionid"),
            "name": raw.get("name"),
            "description": raw.get("description"),
            "status": raw.get("status"),
            "isOngoing": bool(raw.get("is_ongoing")),
            "startTime": _epoch(raw.get("start_time")),
            "endTime": _epoch(raw.get("end_time")),
            "startTimeEpoch": raw.get("start_time"),
            "endTimeEpoch": raw.get("end_time"),
            "withMegaSale": bool(raw.get("with_mega_sale_session")),
            "categoryCount": len(raw.get("categories") or []),
        })
    return out


def parse_items(payload: dict, country: str) -> list[dict]:
    items = ((payload or {}).get("data") or {}).get("items") or []
    currency = CURRENCIES.get(country)
    out = []
    for raw in items:
        if not isinstance(raw, dict):
            continue

        price = _money(raw.get("price"))
        before = _money(raw.get("price_before_discount"))
        saving = round(before - price, 2) if (price is not None and before) else None

        stock = raw.get("flash_sale_stock")
        sold = raw.get("flash_sale_sold_count")
        remaining_pct = None
        if isinstance(stock, int) and isinstance(sold, int) and (stock + sold) > 0:
            remaining_pct = round(stock / (stock + sold) * 100, 2)

        item_id, shop_id = raw.get("itemid"), raw.get("shopid")
        out.append({
            "itemId": item_id,
            "shopId": shop_id,
            "name": raw.get("name"),
            "url": (f"https://{raw.get('_domain', '')}/product-i.{shop_id}.{item_id}"
                    if raw.get("_domain") else None),
            "currency": currency,
            "price": price,
            "priceBeforeDiscount": before,
            "savingAmount": saving,
            "discountPercent": _percent(raw.get("discount") or raw.get("raw_discount")),
            "flashSaleStock": stock,
            "flashSaleSold": sold,
            "stockRemainingPercent": remaining_pct,
            "historicalSold": raw.get("historical_sold"),
            "itemRating": ((raw.get("item_rating") or {}).get("rating_star")
                           if isinstance(raw.get("item_rating"), dict) else None),
            "imageUrl": (f"https://down-id.img.susercontent.com/file/{raw.get('image')}"
                         if raw.get("image") else None),
            "isMart": bool(raw.get("is_mart")),
            "isAdult": bool(raw.get("is_adult")),
            "categoryId": raw.get("flash_catid"),
            "flashSaleType": raw.get("flash_sale_type"),
            "startTime": _epoch(raw.get("start_time")),
            "endTime": _epoch(raw.get("end_time")),
        })
    return out
