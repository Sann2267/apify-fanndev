"""Parsing + record builders for ctb.gov.vu's two Joomla `com_finder` card
listings: `current` (Actual Tenders) and `results` (Tenders Results) --
identical card shape, different URL/archive.
"""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.constants import BASE


class UnexpectedShape(Exception):
    """Raised when a response no longer matches the structure this parser
    was written against -- must NOT be swallowed (fail loud, never silently
    emit an empty/corrupt record)."""


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.replace("\xa0", " ").strip()
    return text or None


def _labeled_field(card, css_class: str) -> str | None:
    """Each field div looks like `<div class="...submissiondate">
    <span class='lbld'>Submission Date : </span>05 Dec 2024 08:00</div>` --
    strip the label span's own text off the front of the div's full text."""
    div = card.select_one(f".{css_class}")
    if div is None:
        return None
    label = div.find("span")
    full_text = _clean(div.get_text(" ", strip=True))
    if full_text is None:
        return None
    if label is not None:
        label_text = _clean(label.get_text(" ", strip=True))
        if label_text and full_text.startswith(label_text):
            return _clean(full_text[len(label_text) :])
    return full_text


def _split_tender_type(result_text: str | None) -> tuple[str | None, str | None]:
    """`p.result-text` looks like "Request For Tender : No.RFT MFEM MALAMPA
    01/25" or "Request For Proposal : No. 01/23/VEAP/LV-DSC/VPMU" -- the
    label before " : " is the solicitation type (varies -- Tender vs
    Proposal observed at recon time), the rest is the reference number."""
    if not result_text:
        return None, None
    if " : " in result_text:
        label, _, ref = result_text.partition(" : ")
        return _clean(label), _clean(ref)
    return None, result_text


def parse_tender_cards(html: str, label: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("li.tendersList")
    if not cards:
        return []  # legitimately the last page -- caller decides how to treat this

    records = []
    for card in cards:
        link = card.find("a", href=True)
        if link is None:
            raise UnexpectedShape(f"{label}: a 'tendersList' card has no detail link -- page layout may have changed")
        result_text = _clean(card.select_one("p.result-text").get_text(" ", strip=True)) if card.select_one("p.result-text") else None
        tender_type, ref = _split_tender_type(result_text)
        title = _clean(card.select_one("h4").get_text(" ", strip=True)) if card.select_one("h4") else None
        if title is None:
            raise UnexpectedShape(f"{label}: a 'tendersList' card has no <h4> title -- page layout may have changed")
        records.append(
            {
                "tenderType": tender_type,
                "referenceNumber": ref,
                "title": title,
                "purchaser": _labeled_field(card, "purchaser"),
                "category": _labeled_field(card, "category"),
                "submissionDate": _labeled_field(card, "submissiondate"),
                "expiryDate": _labeled_field(card, "expirydate"),
                "description": _clean(card.select_one(".tenderdescription").get_text(" ", strip=True))
                if card.select_one(".tenderdescription")
                else None,
                "detailUrl": urljoin(BASE, link["href"]),
            }
        )
    return records


def build_tender_record(raw: dict) -> dict:
    return {
        "tenderType": raw.get("tenderType"),
        "referenceNumber": raw.get("referenceNumber"),
        "title": raw.get("title"),
        "purchaser": raw.get("purchaser"),
        "category": raw.get("category"),
        "submissionDate": raw.get("submissionDate"),
        "expiryDate": raw.get("expiryDate"),
        "description": raw.get("description"),
        "detailUrl": raw.get("detailUrl"),
    }


# ---------------------------------------------------------------------------
# Dataset envelope
# ---------------------------------------------------------------------------

import datetime as _dt  # noqa: E402


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


RECORD_TYPES = {"current": "CURRENT_TENDER", "results": "TENDER_RESULT"}
SOURCE_TAGS = {
    "current": "S1-joomla-finder-actual-tenders",
    "results": "S1-joomla-finder-tenders-results",
}


def build_record(list_type: str, fields: dict) -> dict:
    return {
        "_input": f"list:{list_type}",
        "_source": SOURCE_TAGS.get(list_type, list_type),
        "_scrapedAt": utc_now_iso(),
        "recordType": RECORD_TYPES.get(list_type, list_type),
        **fields,
    }


def build_error_record(list_type: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": f"list:{list_type}",
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
