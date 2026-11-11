"""Parsing + record builders for mof.gov.ws's two Webflow CMS collection
pages: `current` (tender-adverisements) and `awards` (tender-awards) --
genuinely different card shapes, parsed separately.
"""

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Raised when a response no longer matches the structure this parser
    was written against -- must NOT be swallowed (fail loud, never silently
    emit an empty/corrupt record)."""


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.replace("\xa0", " ").strip()
    return text or None


def _strip_svgs(soup: BeautifulSoup) -> None:
    for svg in soup.find_all("svg"):
        svg.decompose()


# ---------------------------------------------------------------------------
# current -- tender-adverisements
# ---------------------------------------------------------------------------


def parse_current_cards(html: str, label: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    _strip_svgs(soup)
    cards = soup.select("div.collection-item-2.w-dyn-item[role=listitem]")
    if not cards:
        raise UnexpectedShape(f"{label}: no 'collection-item-2' cards found -- page layout may have changed")

    records = []
    for card in cards:
        title_el = card.select_one("h1.heading-16")
        if title_el is None:
            raise UnexpectedShape(f"{label}: a tender card has no 'heading-16' title -- page layout may have changed")
        title = _clean(title_el.get_text(" ", strip=True))

        # "Closing Date :" and "Agency:" are the two bare `flex-block-4`
        # divs (no `.desktop`/`.doc`/mobile-duplicate class) -- see
        # CRAWLING_METHOD.md for why this selector, not label text matching.
        bare_fields = [d for d in card.select("div.flex-block-4") if d.get("class") == ["w-layout-hflex", "flex-block-4"]]
        closing_date = _clean(bare_fields[0].get_text(" ", strip=True).removeprefix("Closing Date :")) if len(bare_fields) > 0 else None
        agency = _clean(bare_fields[1].get_text(" ", strip=True).removeprefix("Agency:")) if len(bare_fields) > 1 else None

        # Contact info -- take only the `.desktop`-flagged blocks to avoid
        # the page's own mobile-layout duplicate of the same fields.
        contact_parts = [_clean(d.get_text(" ", strip=True)) for d in card.select("div.flex-block-4.desktop")]
        contact_text = " | ".join(p for p in contact_parts if p) or None

        docs = []
        seen_hrefs = set()
        for a in card.select("a.link-4[href]"):
            href = a.get("href")
            doc_label = _clean(a.get_text(" ", strip=True))
            if not href or href == "#" or not doc_label or href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            docs.append({"label": doc_label, "url": href})

        records.append(
            {
                "title": title,
                "closingDate": closing_date,
                "agency": agency,
                "contactText": contact_text,
                "documents": docs or None,
            }
        )
    return records


def build_current_record(raw: dict) -> dict:
    return {
        "title": raw.get("title"),
        "closingDate": raw.get("closingDate"),
        "agency": raw.get("agency"),
        "contactText": raw.get("contactText"),
        "documents": raw.get("documents"),
    }


# ---------------------------------------------------------------------------
# awards -- tender-awards
# ---------------------------------------------------------------------------


def _value_after_label(card, label_text: str) -> str | None:
    for div in card.find_all("div"):
        if _clean(div.get_text(" ", strip=True)) == label_text:
            sibling = div.find_next_sibling("div")
            return _clean(sibling.get_text(" ", strip=True)) if sibling else None
    return None


def parse_award_cards(html: str, label: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    _strip_svgs(soup)
    cards = [c for c in soup.select("div.w-dyn-item[role=listitem]") if c.get("class") == ["w-dyn-item"]]
    if not cards:
        raise UnexpectedShape(f"{label}: no plain 'w-dyn-item' award cards found -- page layout may have changed")

    records = []
    for card in cards:
        contract = _value_after_label(card, "Contract:")
        if contract is None:
            raise UnexpectedShape(f"{label}: an award card has no 'Contract:' field -- page layout may have changed")
        records.append(
            {
                "contract": contract,
                "approvalDate": _value_after_label(card, "Approval Dates:"),
                "implementingAgency": _value_after_label(card, "Implementing Agency:"),
                "winningBiddersText": _value_after_label(card, "Winning Bidder(s) and Contract Amounts:"),
                "allBiddersText": _value_after_label(card, "All Bidders"),
            }
        )
    return records


def build_award_record(raw: dict) -> dict:
    return {
        "contract": raw.get("contract"),
        "approvalDate": raw.get("approvalDate"),
        "implementingAgency": raw.get("implementingAgency"),
        "winningBiddersText": raw.get("winningBiddersText"),
        "allBiddersText": raw.get("allBiddersText"),
    }


# ---------------------------------------------------------------------------
# Dataset envelope
# ---------------------------------------------------------------------------

import datetime as _dt  # noqa: E402


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


RECORD_TYPES = {"current": "CURRENT_TENDER", "awards": "TENDER_AWARD"}
SOURCE_TAGS = {
    "current": "S1-webflow-cms-tender-adverisements",
    "awards": "S1-webflow-cms-tender-awards",
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
