"""Report HTML -> dataset records.

The reports are not built from ``<table>`` elements -- they use nested divs
(``div.table > div.row > div.cell[data-title]``), so a table parser finds
nothing. Parsing keys off ``data-title``, which is the same attribute the site
uses to label cells on mobile, and is therefore stable against layout changes
that a positional parser would not survive.

Two independent copies of most numbers exist on the page: the visible div-table
and a JavaScript array (``countryData``, ``themeData``, ...). The table is the
primary source because it is what the publisher displays; the JS array is used
as *enrichment* only, because it carries machine codes the table drops -- "US"
alongside "United States", ".com" alongside "com". Where the two disagree, the
table wins and the JS value ships as ``code`` only.
"""

import json
import re
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

from src.constants import BASE, JS_VAR_DIMENSIONS

_JS_VAR_RE = re.compile(r"(?:var|const|let)\s+(\w+Data)\s*=\s*(\[.*?\]);", re.S)
_UPDATED_RE = re.compile(r"Updated\s+([A-Z][a-z]{2}\s+\d{1,2}\s+\d{4})")
_LIVE_STORES_RE = re.compile(r"there are\s+([\d,]+)\s+live stores", re.I)
_QOQ_RE = re.compile(r"increased\s+([\d.]+)%\s+quarter-over-quarter in\s+(\d{4}\s+Q\d)", re.I)
_YOY_RE = re.compile(r"increased\s+([\d.]+)%\s+year-over-year in\s+(\d{4}\s+Q\d)", re.I)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_number(value):
    """'3,077,514' -> 3077514 ; '7.3' -> 7.3 ; '' -> None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return None


def _envelope(input_value: str, record_type: str) -> dict:
    return {
        "_input": input_value,
        "_source": "S1-report-html",
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }


def parse_js_vars(html: str) -> dict:
    """Return {varName: [rows]} for every embedded data array that parses.

    A single malformed array must not cost the whole page, so failures are
    skipped silently here -- the div-tables are the primary source and they are
    parsed separately.
    """
    out = {}
    for m in _JS_VAR_RE.finditer(html):
        try:
            out[m.group(1)] = json.loads(m.group(2))
        except (json.JSONDecodeError, ValueError):
            continue
    return out


def parse_section_rows(html: str, section_id: str) -> list[dict]:
    """Rows of the div-table that follows a section anchor.

    The anchor and its table are siblings inside the same block, so the search
    runs over the slice of HTML between this anchor and the next one -- taking
    the whole document would let one section swallow the next section's rows.
    """
    start = html.find(f'id="{section_id}"')
    if start < 0:
        return []
    next_anchor = re.search(r'id="[a-z0-9_-]+"', html[start + 10:])
    end = start + 10 + next_anchor.start() if next_anchor else len(html)
    # Sections are short; scanning a bounded slice keeps unrelated tables out.
    chunk = html[start:end]
    tree = HTMLParser(chunk)
    rows = []
    for row in tree.css("div.row"):
        cells = row.css("div.cell[data-title]")
        if not cells:
            continue
        record = {}
        for cell in cells:
            key = cell.attributes.get("data-title") or ""
            # Cells are pretty-printed across several lines ("2026 Q3\n\n
            # (to date)"), so text() alone leaks layout whitespace into the
            # dataset. Collapsing it here keeps every consumer from having to.
            record[key.strip()] = re.sub(r"\s+", " ", cell.text(strip=True)).strip()
        if record:
            rows.append(record)
    return rows


def dedupe_rows(rows: list[dict], key: str) -> list[dict]:
    """Keep the last occurrence of each key, preserving order.

    The growth section repeats its newest quarter: once in the callout above
    the table and once as the table's final row. Keeping the last occurrence
    keeps the series in chronological order instead of starting with a stray
    partial quarter.
    """
    last_index = {}
    for i, row in enumerate(rows):
        last_index[row.get(key)] = i
    return [row for i, row in enumerate(rows) if last_index.get(row.get(key)) == i]


def parse_headline(html: str) -> dict:
    tree = HTMLParser(html)
    h1 = tree.css_first("h1")
    title = h1.text(strip=True) if h1 else None

    text = tree.text(separator=" ")
    text = re.sub(r"\s+", " ", text)

    updated = _UPDATED_RE.search(text)
    live = _LIVE_STORES_RE.search(text)
    qoq = _QOQ_RE.search(text)
    yoy = _YOY_RE.search(text)

    updated_iso = None
    if updated:
        try:
            updated_iso = datetime.strptime(updated.group(1), "%b %d %Y").strftime("%Y-%m-%d")
        except ValueError:
            updated_iso = updated.group(1)

    return {
        "reportTitle": title,
        "reportUpdated": updated_iso,
        "liveStores": to_number(live.group(1)) if live else None,
        "quarterOverQuarterGrowthPct": to_number(qoq.group(1)) if qoq else None,
        "quarterOverQuarterQuarter": qoq.group(2) if qoq else None,
        "yearOverYearGrowthPct": to_number(yoy.group(1)) if yoy else None,
        "yearOverYearQuarter": yoy.group(2) if yoy else None,
    }


def wrap_platform(platform: str, html: str, sections_found: list[str], growth_rows: list[dict]) -> dict:
    head = parse_headline(html)
    latest = growth_rows[-1] if growth_rows else {}
    record = _envelope(platform, "PLATFORM")
    record.update(
        {
            "platform": platform,
            "platformName": (head.get("reportTitle") or "").replace("The State of ", "").replace(" in 2026", "") or platform,
            "reportUrl": f"{BASE}/reports/{platform}",
            **head,
            "latestQuarter": (latest.get("Quarter") or "").replace("(to date)", "").strip() or None,
            "latestQuarterIsPartial": "(to date)" in (latest.get("Quarter") or ""),
            "latestQuarterStores": to_number(latest.get("Active Stores")),
            "quartersOfHistory": len(growth_rows),
            "sectionsFound": sections_found,
        }
    )
    return record


def wrap_growth(platform: str, row: dict) -> dict:
    record = _envelope(platform, "GROWTH")
    quarter = row.get("Quarter") or ""
    record.update(
        {
            "platform": platform,
            "quarter": quarter.replace(" (to date)", "").strip() or None,
            # The newest quarter is partial; labelling it keeps a consumer from
            # reading an in-progress quarter as a decline.
            "isPartialQuarter": "(to date)" in quarter,
            "activeStores": to_number(row.get("Active Stores")),
            "_raw": row,
        }
    )
    return record


def wrap_breakdown(platform: str, dimension: str, row: dict, code: str | None = None) -> dict:
    keys = list(row.keys())
    label_key = keys[0] if keys else None
    value_key = next((k for k in keys if k.lower() in ("stores", "count")), keys[-1] if len(keys) > 1 else None)
    record = _envelope(platform, "BREAKDOWN")
    record.update(
        {
            "platform": platform,
            "dimension": dimension,
            "label": row.get(label_key) if label_key else None,
            "code": code,
            "stores": to_number(row.get(value_key)) if value_key else None,
            "_raw": row,
        }
    )
    return record


def wrap_migration(platform: str, direction: str, row: dict) -> dict:
    record = _envelope(platform, "MIGRATION")
    record.update(
        {
            "platform": platform,
            "direction": direction,
            "otherPlatform": row.get("Platform"),
            "stores": to_number(row.get("Stores")),
            "_raw": row,
        }
    )
    return record


def wrap_store(platform: str, list_type: str, row: dict) -> dict:
    domain = row.get("Domain")
    record = _envelope(platform, "STORE")
    record.update(
        {
            "platform": platform,
            "listType": list_type,
            "name": row.get("Name"),
            "domain": domain,
            "url": f"https://{domain}" if domain else None,
            "rank": to_number(row.get("Rank")),
            "created": row.get("Created"),
            "_raw": row,
        }
    )
    return record


def wrap_available(platform: str, name: str | None = None) -> dict:
    record = _envelope("reference", "AVAILABLE_REPORT")
    record.update(
        {
            "platform": platform,
            "platformName": name or platform,
            "reportUrl": f"{BASE}/reports/{platform}",
        }
    )
    return record


def js_codes(js_vars: dict, dimension: str) -> dict:
    """label -> machine code, from whichever JS array covers that dimension."""
    for var_name, dim in JS_VAR_DIMENSIONS.items():
        if dim != dimension:
            continue
        mapping = {}
        for row in js_vars.get(var_name) or []:
            label = (row.get("label") or "").replace("&", "&").strip()
            code = row.get("term") or row.get("value")
            if label and code and label != code:
                mapping[label] = code
        if mapping:
            return mapping
    return {}


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    record = _envelope(input_value, "ERROR")
    record.update({"_error": error_kind, "_errorDetail": detail})
    return record
