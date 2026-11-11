"""Parsing logic for CPBN's (`www.cpbn.com.na`) "Bids" pages.

All eight listing views (see constants.LIST_CONFIGS) share the same card
layout: a `<table id="activeBidsTable"><tbody class="page-data">` containing
one `<div class="card">` per bid/notice. Two shapes are seen in the wild
(both handled generically, not treated as an error):

1. Bids that have their own detail page: the title is a link to
   `/index/bid/<id>`, and the info line reads
   `Reference number: X | Closing Date and Time: Y | More Details`.
2. Older PDF-only notices with no separate detail page: the title is plain
   text (no link) and the info line is just `Date: Y`. The reference number
   for these is usually embedded in the free-text title instead.

Rather than hardcode either shape, the info line is parsed generically:
split on `|`, then each segment on the first `:` into a label/value pair,
slugified into a camelCase key -- so a future label CPBN adds flows through
automatically (raw-passthrough) instead of being dropped, while a listing
page that loses its `table#activeBidsTable` shell entirely raises
UnexpectedShape (fail loud) instead of silently returning zero rows.

The bid-detail page (`/index/bid/<id>`) has no fixed field set either -- it's
a `<tbody class="page-data">` of `<tr><th class="title">Label</th><td
class="value">Value</td></tr>` pairs that varies per bid (works vs. goods vs.
services procurement). Parsed the same generic label-slugify way.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

RESOURCE_ID_RE = re.compile(r"/index/bid/(\d+)")
DOWNLOAD_URL_RE = re.compile(r"openModalRemoteContent\('([^']+)'\)")


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify_label(label: str) -> str:
    label = label.replace("\xa0", " ").strip()
    if label.endswith(":"):
        label = label[:-1]
    words = [w for w in re.split(r"[^A-Za-z0-9]+", label) if w]
    if not words:
        return "field"
    first, rest = words[0].lower(), words[1:]
    return first + "".join(w.capitalize() for w in rest)


def _extract_documents(container) -> list[dict]:
    """Finds every download-link `<a>` inside `container` and returns
    {"label": <filename/link text>, "downloadUrl": <ajax/download/<id> URL>}.
    Used for both listing cards and the detail page's own "Documents"
    section -- both use the same `openModalRemoteContent('<url>')` pattern."""
    docs = []
    for a in container.select("a.download-link"):
        onclick = a.get("onclick", "")
        m = DOWNLOAD_URL_RE.search(onclick)
        download_url = m.group(1) if m else a.get("href")
        label = a.get_text(" ", strip=True) or None
        docs.append({"label": label, "downloadUrl": download_url})
    return docs


def _parse_info_line(text: str) -> dict:
    """Parses e.g. 'Reference number: X | Closing Date and Time: Y | More
    Details' into {"referenceNumber": "X", "closingDateAndTime": "Y"} --
    "More Details" (a bare link label, no ':') is skipped since it duplicates
    `bidUrl`. A single-field line like 'Date: Y' parses to {"date": "Y"}."""
    fields: dict = {}
    for segment in text.split("|"):
        segment = segment.strip()
        if ":" not in segment:
            continue
        label, _, value = segment.partition(":")
        value = value.strip()
        if not value:
            continue
        fields[_slugify_label(label)] = value
    return fields


# ---------------------------------------------------------------------------
# Listing pages
# ---------------------------------------------------------------------------


def parse_list_page(html_text: str, list_type: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")
    table = soup.select_one("table#activeBidsTable")
    if table is None:
        raise UnexpectedShape(f"[{list_type}] no table#activeBidsTable found -- page shape has likely changed")

    tbody = table.select_one("tbody.page-data")
    if tbody is None:
        raise UnexpectedShape(f"[{list_type}] table#activeBidsTable has no tbody.page-data -- page shape has likely changed")

    rows = []
    for card in tbody.select("div.card"):
        h4 = card.select_one("h4.card-title")
        if h4 is None:
            raise UnexpectedShape(f"[{list_type}] a bid card is missing its h4.card-title -- page shape has likely changed")
        a = h4.find("a")
        title = (a.get_text(strip=True) if a else h4.get_text(strip=True)) or None
        bid_url = a.get("href") if a else None
        bid_id_match = RESOURCE_ID_RE.search(bid_url) if bid_url else None

        li = card.select_one("ul.list-group-flush li.list-group-item")
        info_fields = _parse_info_line(li.get_text(" ", strip=True)) if li else {}

        rows.append(
            {
                "bidId": bid_id_match.group(1) if bid_id_match else None,
                "bidUrl": bid_url,
                "title": title,
                **info_fields,
                "documents": _extract_documents(card),
            }
        )
    return {"rows": rows}


def build_list_record(list_type: str, row: dict, total_available: int) -> dict:
    return {
        "_input": f"list:{list_type}",
        "_source": f"S1-{list_type}-listing",
        "_scrapedAt": utc_now_iso(),
        "recordType": f"BID_{list_type.upper()}",
        "_totalAvailable": total_available,
        **row,
    }


# ---------------------------------------------------------------------------
# Bid detail page
# ---------------------------------------------------------------------------


def parse_detail_page(html_text: str) -> dict:
    """Returns {"kind": "details", "fields": {...}, "documents": [...]} or
    {"kind": "not_found"}.

    "not_found" covers both a genuinely invalid bidId and one CPBN doesn't
    recognize -- both cases fall through to CPBN's own generic homepage
    (title "CPBN", no `tbody.page-data` at all) instead of a 404, confirmed
    empirically against bidId=999999/0/abc. This is NOT the same as a general
    login wall on viewing (see CRAWLING_METHOD.md) -- every bidId reachable
    from the public listing pages renders with zero auth.
    """
    soup = BeautifulSoup(html_text, "lxml")

    tbody = soup.select_one("tbody.page-data")
    if tbody is None:
        return {"kind": "not_found"}

    fields: dict = {}
    for tr in tbody.select("tr"):
        th = tr.select_one("th.title")
        td = tr.select_one("td.value")
        if th is None or td is None:
            continue
        label = th.get_text(strip=True)
        key = _slugify_label(label)
        base_key = key
        n = 2
        while key in fields:
            key = f"{base_key}{n}"
            n += 1
        fields[key] = td.get_text(" ", strip=True) or None

    if not fields:
        raise UnexpectedShape("tbody.page-data had no th.title/td.value rows -- page shape has likely changed")

    documents_heading = soup.find(lambda tag: tag.name == "h3" and tag.get_text(strip=True) == "Documents")
    documents = []
    if documents_heading is not None:
        docs_container = documents_heading.find_parent("div", class_="portfolio-info")
        if docs_container is not None:
            documents = _extract_documents(docs_container)

    title_tag = soup.select_one("title")
    page_title = title_tag.get_text(strip=True) if title_tag else None

    return {"kind": "details", "fields": fields, "documents": documents, "pageTitle": page_title}


def build_detail_record(bid_id: str, parsed: dict) -> dict:
    if parsed["kind"] == "not_found":
        return build_error_record(bid_id, "not_found_or_restricted")
    return {
        "_input": bid_id,
        "_source": "S1-detail",
        "_scrapedAt": utc_now_iso(),
        "recordType": "BID_DETAIL",
        "bidId": bid_id,
        "bidUrl": f"https://www.cpbn.com.na/index/bid/{bid_id}",
        "pageTitle": parsed.get("pageTitle"),
        **parsed["fields"],
        "documents": parsed["documents"],
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
