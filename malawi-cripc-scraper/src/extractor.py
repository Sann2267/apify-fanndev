"""Parse CRIPC/MBRS's server-rendered search HTML into dataset-ready records.

Transport (client.py) and parsing (this file) are kept separate per this
portfolio's convention. The page is server-rendered but a thin Vue overlay
never executes in this actor, so a couple of fields (dates) arrive as
literal unrendered `{{formatDate(...)}}` mustache expressions -- pulled out
with a small regex instead of a JS engine. See `constants.py` for the full
recon summary and card markup samples this parser is built against.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

SOURCE = "S1-html-search"
SOURCE_DETAIL = "S1-html-search+owner-detail"

# Pulls the raw ISO date string out of e.g. formatDate('MMM D, YYYY',"2024-11-25" )
DATE_RE = re.compile(r"""formatDate\(\s*'[^']*'\s*,\s*"([^"]+)"\s*\)""")
OWNER_UUID_RE = re.compile(r"/search/([0-9a-fA-F-]{36})")


class UnexpectedShape(Exception):
    """Raised when the search page doesn't look like anything this parser
    recognizes (neither result cards nor a "no results" empty state) --
    propagates and fails the run loudly rather than silently emitting an
    empty record, per .ai/CLAUDE.md principle #6 (a redesign of the page
    would trip this rather than silently returning nothing)."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _first_date(card) -> str | None:
    m = DATE_RE.search(str(card))
    return m.group(1) if m else None


def _parse_business_card(card) -> dict:
    """Shared shape for both the top-level `type=entity` search results and
    the per-owner business list on the owner-detail page -- same markup in
    both places (`.ai` cross-reference: constants.py "Response shape")."""
    reg_p = card.find("p", class_="uppercase")
    registration_number = reg_p.get_text(strip=True) if reg_p else None

    name = None
    for p in card.find_all("p"):
        classes = p.get("class") or []
        if (
            "text-sm" in classes
            and "font-semibold" in classes
            and "text-black" in classes
            and "uppercase" not in classes
        ):
            name = p.get_text(strip=True)
            break

    status_p = card.find("p", class_="leading-none")
    status = status_p.get_text(strip=True) if status_p else None

    owner_type = None
    for p in card.find_all("p"):
        if p.get_text(strip=True) == "Owner Type":
            sib = p.find_next_sibling("p")
            if sib and sib.get_text(strip=True):
                owner_type = sib.get_text(strip=True)
            break

    record = {
        "registrationNumber": registration_number,
        "name": name,
        "registeredDate": _first_date(card),
        "status": status,
    }
    if owner_type:
        record["ownerType"] = owner_type
    return record


def _parse_owner_card(card) -> dict:
    name_p = card.find("p", class_="uppercase")
    name = name_p.get_text(strip=True) if name_p else None

    status_p = None
    for p in card.find_all("p"):
        classes = p.get("class") or []
        if "capitalize" in classes and "font-semibold" in classes:
            status_p = p
            break
    status = status_p.get_text(strip=True) if status_p else None

    owner_id = None
    detail_url = None
    link = card.find("a", href=True)
    if link:
        href = link["href"]
        m = OWNER_UUID_RE.search(href)
        if m:
            owner_id = m.group(1)
            detail_url = f"https://mbrs.gov.mw{href}" if href.startswith("/") else href

    return {
        "name": name,
        "status": status,
        "ownerId": owner_id,
        "ownerDetailUrl": detail_url,
    }


def parse_entity_page(html: str) -> list[dict]:
    """Returns one dict per matched company/business-name entity on this
    page of `type=entity` search results. Empty list means this page (and,
    if page==1, the whole query) had zero matches -- a valid, successful
    "no matches" outcome, not a parse failure."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.mb-3.mt-2.p-4.bg-white.rounded-lg")
    if not cards and "No results found" not in html and "Not found" not in html:
        raise UnexpectedShape("Entity search page has neither result cards nor a recognized empty state")
    return [_parse_business_card(c) for c in cards]


def parse_individual_page(html: str) -> list[dict]:
    """Returns one dict per matched owner/individual on this page of
    `type=individual` search results."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.cursor-pointer.p-4.bg-white.border.border-gray-100.rounded-lg")
    if not cards and "No results found" not in html and "Not found" not in html:
        raise UnexpectedShape("Individual search page has neither result cards nor a recognized empty state")
    return [_parse_owner_card(c) for c in cards]


def parse_owner_detail(html: str) -> dict:
    """Parses `/search/<uuid>?type=owner` -- the owner's name/ID type plus
    every business they're a registered proprietor/owner of. This is the
    only public detail page CRIPC exposes without login (see constants.py
    "Gotcha: entities have NO public detail page")."""
    soup = BeautifulSoup(html, "html.parser")

    def _value_after_label(label: str) -> str | None:
        node = soup.find(string=label)
        if not node:
            return None
        label_p = node.find_parent("p")
        if not label_p:
            return None
        sib = label_p.find_next_sibling("p")
        return sib.get_text(strip=True) if sib else None

    owner_name = _value_after_label("Owner Name")
    owner_id_type = _value_after_label("Owner ID Type")
    business_cards = soup.select("div.mb-3.mt-2.p-4.bg-white.rounded-lg")
    businesses = [_parse_business_card(c) for c in business_cards]

    return {
        "ownerName": owner_name,
        "ownerIdType": owner_id_type,
        "businesses": businesses,
    }


def build_record(query: str, search_type: str, item: dict, source: str = SOURCE, warning: str | None = None) -> dict:
    record = {
        "_input": query,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "searchType": search_type,
        **item,
    }
    if warning:
        record["_warning"] = warning
    return record


def extract_error(query: str, search_type: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "searchType": search_type,
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
