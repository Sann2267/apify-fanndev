"""List-page parsing, rank extraction and movement detection."""

import html as htmllib
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from src.constants import (
    DOMAINS,
    LIST_PATHS,
    MAX_PAGES,
    MOVE_DROPPED,
    MOVE_FALLING,
    MOVE_NEW,
    MOVE_RISING,
    MOVE_UNCHANGED,
    SIGNIFICANT_MOVE,
)

logger = logging.getLogger(__name__)

_RECS = re.compile(r'data-client-recs-list="([^"]*)"')
_ASIN = re.compile(r"^[A-Z0-9]{10}$")

# Faceout field patterns. Amazon's class names are hashed and change, so
# these deliberately anchor on the stable parts (`p13n-sc-price`,
# `zg-bdg-text`, the `out of 5 stars` phrase) rather than on a full class.
_FACEOUT_SPLIT = re.compile(r'id="gridItemRoot"')
_F_RANK = re.compile(r'class="zg-bdg-text">#([\d,]+)<')
_F_ASIN = re.compile(r'data-asin="([A-Z0-9]{10})"')
_F_TITLE = re.compile(r'_cDEzb_p13n-sc-css-line-clamp-[^"]*"[^>]*>([^<]+)<')
_F_PRICE = re.compile(r'p13n-sc-price[^"]*"[^>]*>([^\d<]{0,3})([\d,.]+)<')
_F_RATING = re.compile(r">([\d.]+) out of 5 stars<")
_F_REVIEWS = re.compile(r'<span aria-hidden="true" class="a-size-small">([\d,]+)</span>')
_F_IMAGE = re.compile(r'<img[^>]*\ssrc="(https://[^"]+)"')
_F_LINK = re.compile(r'href="(/[^"]*/dp/[A-Z0-9]{10}[^"]*)"')


class InvalidInput(ValueError):
    """The input could not be used."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_int(text):
    if not isinstance(text, str):
        return text if isinstance(text, int) else None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _to_float(text):
    if isinstance(text, (int, float)):
        return float(text)
    if not isinstance(text, str):
        return None
    cleaned = text.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def resolve_category(raw: str) -> dict:
    """Accept a category slug, a node id, or a full Amazon list URL.

    A full URL wins over the run-level defaults, so a single run can mix
    marketplaces and list types by pasting URLs.
    """
    value = str(raw or "").strip()
    if not value:
        raise InvalidInput("empty category")

    if value.startswith("http") or "amazon." in value.lower():
        parsed = urlparse(value if "//" in value else "https://" + value)
        host = (parsed.netloc or "").lower().replace("www.", "")
        if not host.startswith("amazon."):
            raise InvalidInput(f"{raw!r} is not an amazon.* URL")
        domain = host.split("amazon.", 1)[1]
        if domain not in DOMAINS:
            raise InvalidInput(f"{raw!r} uses unsupported marketplace {domain!r}")
        path = parsed.path or ""
        list_type = None
        for name, template in LIST_PATHS.items():
            head = template.split("{")[0]
            if head in path:
                list_type = name
                break
        if list_type is None:
            raise InvalidInput(
                f"{raw!r} is not a Best Sellers / New Releases / Most Wished For / "
                "Movers & Shakers URL"
            )
        head = LIST_PATHS[list_type].split("{")[0]
        tail = path.split(head, 1)[1] if head in path else ""
        segments = [s for s in tail.split("/") if s and not s.startswith("ref=")]
        if not segments:
            raise InvalidInput(f"{raw!r} has no category in its path")
        category = "/".join(segments[:2]) if len(segments) > 1 and segments[1].isdigit() \
            else segments[0]
        return {"category": category, "domain": domain, "listType": list_type, "explicit": True}

    # A bare category is either a slug ("electronics") or a slug plus a node
    # id ("electronics/172541"); anything else is not usable.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-_]*(?:/\d+)?", value):
        raise InvalidInput(
            f"{raw!r} is not a category slug. Use e.g. 'electronics', "
            "'electronics/172541', or a full Amazon list URL."
        )
    return {"category": value, "domain": None, "listType": None, "explicit": False}


def build_url(domain: str, list_type: str, category: str, page: int) -> str:
    base = DOMAINS[domain]
    path = LIST_PATHS[list_type].format(category=category)
    if page <= 1:
        return base + path
    return f"{base}{path}?pg={page}"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_recs_list(page_html: str) -> list[dict]:
    """All 50 ASINs + ranks for the page, from the embedded JSON attribute.

    This is the spine: it covers every product on the page, including the
    ones whose tiles never render. An empty `[]` here is meaningful -- it is
    exactly what Amazon's Movers & Shakers pages return.
    """
    match = _RECS.search(page_html or "")
    if not match:
        return []
    try:
        entries = json.loads(htmllib.unescape(match.group(1)))
    except json.JSONDecodeError:
        return []
    out = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        asin = entry.get("id")
        if not isinstance(asin, str) or not _ASIN.match(asin):
            continue
        meta = entry.get("metadataMap") or {}
        out.append({
            "asin": asin,
            "rank": _to_int(meta.get("render.zg.rank")),
            # Amazon's own Movers & Shakers metrics. Present in the schema,
            # empty on every page seen during recon -- read, never assumed.
            "amazonPercentageChange": _to_float(meta.get("render.zg.bsms.percentageChange")),
            "amazonCurrentSalesRank": _to_int(meta.get("render.zg.bsms.currentSalesRank")),
            "amazonPreviousSalesRank": _to_int(
                meta.get("render.zg.bsms.twentyFourHourOldSalesRank")
            ),
        })
    return out


def parse_faceouts(page_html: str, base: str) -> dict:
    """Detail fields for the server-rendered tiles, keyed by ASIN.

    Only ~30 of the 50 tiles render; the rest lazy-load and simply have no
    details to parse.
    """
    details: dict[str, dict] = {}
    for block in _FACEOUT_SPLIT.split(page_html or "")[1:]:
        asin_match = _F_ASIN.search(block)
        if not asin_match:
            continue
        asin = asin_match.group(1)
        price_match = _F_PRICE.search(block)
        link_match = _F_LINK.search(block)
        title_match = _F_TITLE.search(block)
        details[asin] = {
            "title": htmllib.unescape(title_match.group(1)).strip() if title_match else None,
            "price": _to_float(price_match.group(2)) if price_match else None,
            "currencySymbol": (price_match.group(1).strip() or None) if price_match else None,
            "rating": _to_float(_F_RATING.search(block).group(1))
            if _F_RATING.search(block) else None,
            "reviewCount": _to_int(_F_REVIEWS.search(block).group(1))
            if _F_REVIEWS.search(block) else None,
            "imageUrl": _F_IMAGE.search(block).group(1) if _F_IMAGE.search(block) else None,
            "productUrl": base + link_match.group(1).split("/ref=")[0] if link_match else None,
        }
    return details


def build_records(page_html: str, base: str, context: dict) -> list[dict]:
    """Merge the rank spine with whatever tile details exist."""
    spine = parse_recs_list(page_html)
    details = parse_faceouts(page_html, base)
    records = []
    for entry in spine:
        detail = details.get(entry["asin"], {})
        record = {
            "_input": context["label"],
            "_source": "S1-recs-list",
            "_scrapedAt": _now(),
            "asin": entry["asin"],
            "rank": entry["rank"],
            "category": context["category"],
            "listType": context["listType"],
            "marketplace": context["domain"],
            "productUrl": detail.get("productUrl") or f"{base}/dp/{entry['asin']}",
            **{k: detail.get(k) for k in
               ("title", "price", "currencySymbol", "rating", "reviewCount", "imageUrl")},
            # Only ~60% of a 100-rank run carries details; say so per row
            # rather than leaving a consumer to guess why fields are null.
            "hasDetails": bool(detail),
            "amazonPercentageChange": entry["amazonPercentageChange"],
            "amazonCurrentSalesRank": entry["amazonCurrentSalesRank"],
            "amazonPreviousSalesRank": entry["amazonPreviousSalesRank"],
        }
        if detail:
            record["_source"] = "S1-recs-list+faceout"
        records.append(record)
    return records


def pages_for(max_rank: int) -> int:
    from src.constants import RANKS_PER_PAGE
    return max(1, min(MAX_PAGES, -(-max_rank // RANKS_PER_PAGE)))


# ---------------------------------------------------------------------------
# Movement detection
# ---------------------------------------------------------------------------

def snapshot_key(context: dict) -> str:
    return f"{context['domain']}|{context['listType']}|{context['category']}"


def detect_movement(record: dict, previous_rank) -> dict:
    """Classify how a product moved since the previous run.

    A *lower* rank number is better, so an improvement is `previousRank -
    rank`. Amazon's own Movers & Shakers page was empty throughout recon, so
    this comparison is what actually produces the movers list.
    """
    rank = record.get("rank")
    if previous_rank is None:
        record["previousRank"] = None
        record["rankChange"] = None
        record["movementType"] = MOVE_NEW
        record["isNewEntry"] = True
        record["isSignificantMove"] = True
        return record

    record["previousRank"] = previous_rank
    record["isNewEntry"] = False
    if not isinstance(rank, int):
        record["rankChange"] = None
        record["movementType"] = MOVE_UNCHANGED
        record["isSignificantMove"] = False
        return record

    change = previous_rank - rank
    record["rankChange"] = change
    if change > 0:
        record["movementType"] = MOVE_RISING
    elif change < 0:
        record["movementType"] = MOVE_FALLING
    else:
        record["movementType"] = MOVE_UNCHANGED
    record["isSignificantMove"] = abs(change) >= SIGNIFICANT_MOVE
    return record


def dropped_out_records(previous: dict, seen_asins: set, context: dict, base: str) -> list[dict]:
    """Rows for products that were ranked last run and are not any more.

    A drop-out is a signal in its own right for product research, and it is
    invisible unless the previous snapshot is diffed.
    """
    out = []
    for asin, rank in (previous or {}).items():
        if asin in seen_asins or not _ASIN.match(asin):
            continue
        out.append({
            "_input": context["label"],
            "_source": "S2-snapshot-diff",
            "_scrapedAt": _now(),
            "asin": asin,
            "rank": None,
            "previousRank": rank,
            "rankChange": None,
            "movementType": MOVE_DROPPED,
            "isNewEntry": False,
            "isSignificantMove": True,
            "category": context["category"],
            "listType": context["listType"],
            "marketplace": context["domain"],
            "productUrl": f"{base}/dp/{asin}",
            "hasDetails": False,
        })
    return out
