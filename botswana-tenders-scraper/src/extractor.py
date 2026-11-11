"""Parsing + raw-passthrough record builders for the Botswana ministry
tender sources.

Two very different upstream shapes feed this actor:

1. **Ministry of Finance** -- a genuine RSS feed (Joomla's built-in category
   feed). Clean `title`/`link`/`pubDate`/`category` fields, plus a
   `description` CDATA blob that embeds the actual tender-document PDF
   link as an `<a href>` -- this actor extracts that href rather than
   leaving raw HTML in the dataset.
2. **Ministry of Health** -- one plain HTML `<table>` with a header row
   (Tender / Closing date) and one data row per open tender. No API, no
   feed -- parsed directly from server-rendered HTML.

Both are normalized into the same dataset envelope (`_ministry`/`_source`/
`_scrapedAt`) with upstream's own field names/values passed through
unchanged wherever upstream already returns clean data.
"""

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.constants import FINANCE_BASE_URL, HEALTH_BASE_URL

PDF_HREF_RE = re.compile(r'href="([^"]+)"')


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(node) -> str | None:
    if node is None:
        return None
    t = node.get_text(strip=True)
    return t or None


# ---------------------------------------------------------------------------
# Ministry of Finance (RSS feed)
# ---------------------------------------------------------------------------


def parse_finance_rss(xml_text: str) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    items = soup.find_all("item")
    if not items:
        raise RuntimeError("No <item> elements found in Ministry of Finance RSS feed -- feed shape may have changed")

    records = []
    for item in items:
        title = _text(item.find("title"))
        link = _text(item.find("link"))
        category = _text(item.find("category"))
        pub_date_raw = _text(item.find("pubDate"))
        published_date_iso = None
        if pub_date_raw:
            try:
                published_date_iso = parsedate_to_datetime(pub_date_raw).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except (TypeError, ValueError):
                pass  # keep pub_date_raw as-is; published_date_iso stays None rather than a guess

        description_html = item.find("description")
        pdf_url = None
        attachment_title = None
        if description_html is not None and description_html.string:
            desc_soup = BeautifulSoup(str(description_html.string), "html.parser")
            a = desc_soup.find("a", href=True)
            if a is not None:
                pdf_url = urljoin(FINANCE_BASE_URL, a["href"])
                attachment_title = _text(a)

        records.append(
            {
                "title": title,
                "article_url": link,
                "category": category,
                "pub_date": pub_date_raw,
                "published_date": published_date_iso,
                "pdf_url": pdf_url,
                "attachment_title": attachment_title,
            }
        )
    return records


# ---------------------------------------------------------------------------
# Ministry of Health (HTML table)
# ---------------------------------------------------------------------------

TENDER_REF_RE = re.compile(r"Tender Ref No[:\s]*(.+)", re.IGNORECASE)


def parse_health_tenders(html_text: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")

    adjudication_url = None
    for a in soup.find_all("a", href=True):
        if "adjudication" in a.get_text(strip=True).lower():
            adjudication_url = a["href"]
            break

    table = soup.find("table")
    if table is None:
        raise RuntimeError("No <table> found on Ministry of Health tenders page -- page shape may have changed")

    rows = table.find_all("tr")
    if not rows:
        raise RuntimeError("Ministry of Health tenders table has no rows -- page shape may have changed")

    records = []
    for row in rows[1:]:  # rows[0] is the "Tender / Closing date" header
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        tender_cell, closing_cell = cells[0], cells[1]

        full_text = tender_cell.get_text(" ", strip=True)
        if not full_text:
            continue  # skip genuinely blank spacer rows, if any

        ref_node = tender_cell.find("u") or tender_cell.find("span")
        ref_text = _text(ref_node) or ""
        ref_match = TENDER_REF_RE.search(ref_text)
        tender_ref = ref_match.group(1).strip() if ref_match else None

        link = tender_cell.find("a", href=True)
        title = _text(link) if link is not None else full_text
        pdf_url = urljoin(HEALTH_BASE_URL + "/", link["href"]) if link is not None else None

        records.append(
            {
                "tender_ref": tender_ref,
                "title": title,
                "pdf_url": pdf_url,
                "closing_date": _text(closing_cell),
                "adjudication_decisions_url": adjudication_url,
            }
        )
    return records


# ---------------------------------------------------------------------------
# Dataset envelope
# ---------------------------------------------------------------------------


def build_record(ministry: str, source: str, fields: dict) -> dict:
    return {
        "_ministry": ministry,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        **fields,
    }


def extract_error(ministry: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_ministry": ministry,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
