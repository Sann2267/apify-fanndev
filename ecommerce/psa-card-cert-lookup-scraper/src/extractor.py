"""Cert page HTML -> dataset records.

The page is React-streamed: the estimate, population and sales blocks arrive
inside ``<div hidden id="S:n">`` placeholders that the client script reveals.
The content is fully present in the HTML, so nothing needs a browser -- but a
parser that only looks at visible containers would find an empty page. Parsing
therefore works on the whole document.

Three labelled stat boxes ("PSA Estimate", "PSA Population", "PSA Pop Higher")
are read by locating the label text and taking the next value element, because
their class names are Tailwind soup that changes on every redeploy, while the
labels are the product's own vocabulary and change far more slowly.
"""

import re
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

from src.constants import BASE, ITEM_FIELDS


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_number(value):
    """'4,923' -> 4923 ; '$60.00' -> 60.0 ; '' -> None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "").replace("$", "")
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


def us_date_to_iso(value):
    """PSA prints sale dates as MM/DD/YY."""
    text = (value or "").strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _envelope(input_value: str, record_type: str) -> dict:
    return {
        "_input": input_value,
        "_source": "S1-cert-page",
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }


def parse_item_fields(tree) -> dict:
    """The <dt>/<dd> item-information list."""
    out = {}
    for dt in tree.css("dt"):
        label = dt.text(strip=True)
        dd = dt.next
        while dd is not None and dd.tag != "dd":
            dd = dd.next
        if dd is None:
            continue
        out[label] = re.sub(r"\s+", " ", dd.text(strip=True)).strip()
    return out


def _stat_after_label(tree, label: str):
    """Value of a labelled stat box.

    Matched on the label's own text rather than on a class name, then read from
    the next sibling that actually carries text -- PSA renders the population
    as a link (it points at the pop report) and the estimate as a paragraph.
    """
    for node in tree.css("p, span, h3, div"):
        text = node.text(strip=True)
        if text.upper() != label.upper():
            continue
        parent = node.parent
        if parent is None:
            continue
        for candidate in parent.css("p, a"):
            value = candidate.text(strip=True)
            if value and value.upper() != label.upper():
                return value, candidate.attributes.get("href")
    return None, None


def parse_sales(tree) -> list[dict]:
    """Rows of the 'Sales of Similar Items' table.

    Columns are Image | Sold Price | Seller/Type | Cert | Listing, and each
    cell packs two <p> elements (price + date, seller + type, grade + cert,
    'Lot #' + lot number). Read positionally within the row because the header
    is fixed, but guarded on cell count so a changed table is skipped rather
    than mis-mapped.
    """
    sales = []
    for table in tree.css("table"):
        header = [th.text(strip=True) for th in table.css("th")]
        if "Sold Price" not in header:
            continue
        for row in table.css("tbody tr"):
            cells = row.css("td")
            if len(cells) < 5:
                continue

            def pair(cell):
                parts = [p.text(strip=True) for p in cell.css("p")]
                return (parts + ["", ""])[:2]

            price, date = pair(cells[1])
            seller, sale_type = pair(cells[2])
            grade, _ = pair(cells[3])
            cert_link = cells[3].css_first("a")
            _, lot = pair(cells[4])
            image = cells[0].css_first("img")

            sales.append(
                {
                    "soldPrice": to_number(price),
                    "soldPriceRaw": price or None,
                    "soldDate": us_date_to_iso(date),
                    "soldDateRaw": date or None,
                    "seller": seller or None,
                    "saleType": sale_type or None,
                    "grade": grade or None,
                    "certNumber": cert_link.text(strip=True) if cert_link else None,
                    "certUrl": f"{BASE}{cert_link.attributes.get('href')}" if cert_link and cert_link.attributes.get("href") else None,
                    "lotNumber": lot or None,
                    "imageUrl": image.attributes.get("src") if image else None,
                }
            )
        if sales:
            break
    return sales


def parse_cert_page(cert: str, html: str) -> dict:
    tree = HTMLParser(html)
    fields = parse_item_fields(tree)
    estimate, _ = _stat_after_label(tree, "PSA Estimate")
    population, pop_href = _stat_after_label(tree, "PSA Population")
    pop_higher, _ = _stat_after_label(tree, "PSA Pop Higher")

    mapped = {}
    for label, key in ITEM_FIELDS.items():
        if label in fields:
            mapped[key] = fields[label]

    return {
        "fields": fields,
        "mapped": mapped,
        "estimate": estimate,
        "population": population,
        "populationReportUrl": pop_href,
        "popHigher": pop_higher,
        "sales": parse_sales(tree),
        "title": (tree.css_first("h1").text(strip=True) if tree.css_first("h1") else None),
    }


def wrap_cert(cert: str, parsed: dict, profile: str) -> dict:
    mapped = parsed["mapped"]
    sales = parsed["sales"]
    prices = [s["soldPrice"] for s in sales if isinstance(s.get("soldPrice"), (int, float))]

    record = _envelope(cert, "CERT")
    record.update(
        {
            "certNumber": mapped.get("certNumber") or cert,
            "certUrl": f"{BASE}/cert/{cert}",
            "itemGrade": mapped.get("itemGrade"),
            "gradeNumber": to_number((mapped.get("itemGrade") or "").split()[-1]) if mapped.get("itemGrade") else None,
            "year": mapped.get("year"),
            "brand": mapped.get("brand"),
            "subject": mapped.get("subject"),
            "cardNumber": mapped.get("cardNumber"),
            "category": mapped.get("category"),
            "varietyPedigree": mapped.get("varietyPedigree"),
            "labelType": mapped.get("labelType"),
            "reverseCertBarcode": mapped.get("reverseCertBarcode"),
            "psaEstimate": to_number(parsed.get("estimate")),
            "psaEstimateRaw": parsed.get("estimate"),
            "psaPopulation": to_number(parsed.get("population")),
            "psaPopHigher": to_number(parsed.get("popHigher")),
            "populationReportUrl": parsed.get("populationReportUrl"),
            "recentSalesCount": len(sales),
            # Simple, auditable summaries of the comps the page shows. Anything
            # cleverer (medians by grade, outlier rejection) belongs to the
            # consumer, who knows which comps they trust.
            "recentSaleMin": min(prices) if prices else None,
            "recentSaleMax": max(prices) if prices else None,
            "recentSaleAvg": round(sum(prices) / len(prices), 2) if prices else None,
            "latestSaleDate": next((s["soldDate"] for s in sales if s.get("soldDate")), None),
            "_tlsProfile": profile,
            "_raw": parsed["fields"],
        }
    )
    return record


def wrap_sale(cert: str, index: int, sale: dict, parent: dict) -> dict:
    record = _envelope(cert, "SALE")
    record.update(
        {
            "sourceCertNumber": cert,
            "saleIndex": index,
            "subject": parent["mapped"].get("subject"),
            "year": parent["mapped"].get("year"),
            "brand": parent["mapped"].get("brand"),
            "cardNumber": parent["mapped"].get("cardNumber"),
            "category": parent["mapped"].get("category"),
            **sale,
            "_raw": sale,
        }
    )
    return record


def wrap_reference(surface: str, url: str, ok: bool, detail: str, sample: dict | None = None) -> dict:
    record = _envelope("reference", "SURFACE")
    record.update(
        {
            "surface": surface,
            "url": url,
            "isAvailable": ok,
            "detail": detail,
            "sample": sample or {},
        }
    )
    return record


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    record = _envelope(input_value, "ERROR")
    record.update({"_error": error_kind, "_errorDetail": detail})
    return record
