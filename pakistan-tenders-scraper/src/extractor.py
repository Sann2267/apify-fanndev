"""Parsing logic for epms.ppra.gov.pk's listing tables and tender-detail
pages.

The listing table (shared, identical shape, by `/public/tenders/active-tenders`
and `/public/tenders/tenders-history`) has a fixed 8-column header; columns
are matched by exact visible header text rather than positional index, so a
future column reorder raises `UnexpectedShape` instead of silently
mislabeling data.

The tender-detail page has no JSON field names at all -- it's a series of
`div.detail-card` sections, each a `list-group` of label/value pairs (some
optional fields render conditionally per-tender, e.g. Contact Person/Email/
Phone, Estimated Cost). This parser slugifies each visible label into a
camelCase key generically rather than hardcoding a fixed field list, the
same convention established by this vertical's `ghana-tenders-scraper` (for
its `<dl class="Grid">` pairs) and `nepal-tenders-scraper` (for its
`cellpadding="10"` tables), so upstream additions/renames flow through
automatically (raw-passthrough) instead of being dropped.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import LISTING_HEADERS

TENDER_NO_IN_URL_RE = re.compile(r"/tender-details/([A-Za-z0-9]+)")


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _slugify_label(label: str) -> str:
    label = label.replace("\xa0", " ").replace("&", " and ").strip()
    if label.endswith(":"):
        label = label[:-1]
    words = [w for w in re.split(r"[^A-Za-z0-9]+", label) if w]
    if not words:
        return "field"
    first, rest = words[0].lower(), words[1:]
    return first + "".join(w.capitalize() for w in rest)


# ---------------------------------------------------------------------------
# Listing pages (/public/tenders/active-tenders, /public/tenders/tenders-history)
# ---------------------------------------------------------------------------


def parse_listing(html_text: str) -> dict:
    """Returns {"rows": [...], "hasNextPage": bool}. Raises UnexpectedShape
    if the result table or its expected header columns are missing -- must
    NOT be silently swallowed (fail loud, per project convention)."""
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table")
    if table is None:
        raise UnexpectedShape("no <table> found on listing page -- page shape has likely changed")

    thead = table.find("thead")
    if thead is None:
        raise UnexpectedShape("listing table has no <thead> -- page shape has likely changed")
    header_labels = [_norm(th.get_text(" ", strip=True)) for th in thead.find_all("th")]
    if header_labels != LISTING_HEADERS:
        raise UnexpectedShape(f"expected header {LISTING_HEADERS}, got {header_labels} -- page shape has likely changed")

    tbody = table.find("tbody")
    rows = []
    for tr in (tbody.find_all("tr") if tbody else []):
        tds = tr.find_all("td", recursive=False)
        if len(tds) != len(LISTING_HEADERS):
            continue

        sr_td, tenderno_td, details_td, org_td, status_td, advertised_td, closing_td, actions_td = tds

        tender_no_el = tenderno_td.find("strong")
        tender_no = _norm(tender_no_el.get_text(" ", strip=True)) if tender_no_el else None

        title_el = details_td.find("strong")
        title = _norm(title_el.get_text(" ", strip=True)) if title_el else None
        description_parts = [
            _norm(s.get_text(" ", strip=True))
            for s in details_td.select("small.text-muted.d-block")
            if _norm(s.get_text(" ", strip=True))
        ]
        tag_texts = [
            _norm(s.get_text(" ", strip=True))
            for s in details_td.select("div.d-flex.flex-wrap > small")
            if "organization-chart" not in s.decode_contents()
        ]

        org_small = org_td.find("small")
        organization_name = _norm(org_small.get_text(" ", strip=True)) if org_small else None
        office_span = org_td.find("span", class_="tender-org")
        office_name = _norm(office_span.get_text(" ", strip=True)) if office_span else None
        location_smalls = org_td.find_all("small")
        location = _norm(location_smalls[-1].get_text(" ", strip=True)) if len(location_smalls) > 1 else None

        status_list = [_norm(b.get_text(" ", strip=True)) for b in status_td.select(".tender-badge")]

        advertised_date = _norm(advertised_td.get_text(" ", strip=True)) or None

        closing_strong = closing_td.find("strong")
        closing_date = _norm(closing_strong.get_text(" ", strip=True)) if closing_strong else None
        closing_small = closing_td.find("small")
        closing_time = _norm(closing_small.get_text(" ", strip=True)) if closing_small else None

        detail_href = None
        invoice_href = None
        for a in actions_td.find_all("a", href=True):
            if "/tender-details/" in a["href"]:
                detail_href = a["href"]
            elif "/invoice/" in a["href"]:
                invoice_href = a["href"]
        if not tender_no and detail_href:
            m = TENDER_NO_IN_URL_RE.search(detail_href)
            tender_no = m.group(1) if m else None

        rows.append(
            {
                "tenderNo": tender_no,
                "title": title,
                "description": " ".join(description_parts) or None,
                "tags": tag_texts,
                "organizationName": organization_name,
                "officeName": office_name,
                "location": location,
                "status": status_list,
                "advertisedDate": advertised_date,
                "closingDate": closing_date,
                "closingTime": closing_time,
                "detailUrl": f"https://epms.ppra.gov.pk{detail_href}" if detail_href else None,
                "invoiceUrl": f"https://epms.ppra.gov.pk{invoice_href}" if invoice_href else None,
            }
        )

    pagination = soup.select_one(".pagination-custom")
    has_next_page = bool(pagination) and "Next" in pagination.get_text()

    return {"rows": rows, "hasNextPage": has_next_page}


def build_list_record(row: dict, listing_type: str, page: int, query_label: str) -> dict:
    return {
        "_input": query_label,
        "_source": "S1-listing",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_LIST",
        "listingType": listing_type,
        "page": page,
        **row,
    }


# ---------------------------------------------------------------------------
# Tender detail page (/public/tenders/tender-details/<tenderNo>)
# ---------------------------------------------------------------------------


def parse_detail(html_text: str) -> dict:
    """Returns {"kind": "details", "fields": {...}} or {"kind": "not_found"}.
    An unknown/invalid tenderNo 302-redirects to the active-tenders listing
    (confirmed on a deliberately made-up tenderNo) -- this parser treats an
    `<h1>` reading exactly "Active Tenders" (the listing page's own title,
    followed after redirect) as the not-found signal, since curl_cffi
    follows redirects by default."""
    soup = BeautifulSoup(html_text, "html.parser")
    h1 = soup.find("h1")
    if h1 is None:
        raise UnexpectedShape("no <h1> found on tender detail page -- page shape has likely changed")
    title = _norm(h1.get_text(" ", strip=True))
    if title == "Active Tenders":
        return {"kind": "not_found"}

    cards = soup.select(".detail-card")
    if not cards:
        raise UnexpectedShape("no .detail-card sections found on tender detail page -- page shape has likely changed")

    fields: dict = {"title": title}
    for card in cards:
        for item in card.select(".list-group-item"):
            label_el = item.select_one(".detail-label")
            if label_el is None:
                continue
            value_el = label_el.find_next_sibling("span")
            if value_el is None:
                continue
            label = _norm(label_el.get_text(" ", strip=True))
            if not label:
                continue
            value = _norm(value_el.get_text(" ", strip=True)) or None
            key = _slugify_label(label)
            base_key, n = key, 2
            while key in fields:
                key = f"{base_key}{n}"
                n += 1
            fields[key] = value

    if len(fields) <= 1:
        raise UnexpectedShape("no label/value pairs found on tender detail page -- page shape has likely changed")
    return {"kind": "details", "fields": fields}


def build_detail_record(tender_no: str, parsed: dict) -> dict:
    if parsed["kind"] == "not_found":
        return build_error_record(tender_no, "not_found")
    return {
        "_input": tender_no,
        "_source": "S1-detail",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_DETAIL",
        "tenderNo": tender_no,
        "detailUrl": f"https://epms.ppra.gov.pk/public/tenders/tender-details/{tender_no}",
        "invoiceUrl": f"https://epms.ppra.gov.pk/public/tenders/invoice/{tender_no}",
        **parsed["fields"],
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    record = {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
