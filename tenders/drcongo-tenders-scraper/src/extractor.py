"""Parsing logic for marchepublic.cd's PrimeFaces `DataView` publication grid
(rendered on `publication.xhtml` after a mega-menu category click, see
client.py / CRAWLING_METHOD.md).

Each publication is one `div.product-grid-item` card with:
- `.product-category` -- ARMP's own short type code (e.g. "MF", "MT").
- `.product-badge` -- the human label for that code ("Marche de fournitures").
- two `.product-name` divs -- the contracting authority, then the
  publication's own reference number (rendered in italics).
- `.product-description` -- a short repeat of the authority + reference
  (upstream always suffixes it with " ..." -- stripped here since it never
  carries additional information beyond the two fields above).
- a `label` with "Date de publication : dd/mm/yyyy".
- a "Telecharger" (download) button wired to `redirectPage('<relative pdf
  url>')` -- the only genuinely public per-publication artifact available at
  recon time (every live record's own "Details" button was disabled/inert;
  see CRAWLING_METHOD.md for why no detail-page parser was built).
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

PDF_RE = re.compile(r"redirectPage\('([^']+)'\)")
PUBLISHED_RE = re.compile(r"Date de publication\s*:\s*(\S+)")


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_text(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def parse_publication_grid(html_text: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "lxml")
    dataview = soup.select_one("div.ui-dataview-content")
    if dataview is None:
        raise UnexpectedShape("no div.ui-dataview-content found -- page shape has likely changed")

    # A genuinely empty category renders this exact message inside the same
    # container instead of any product-grid-item cards -- not an error.
    if "Aucun enregistrement" in (dataview.get_text() or ""):
        return []

    cards = dataview.select("div.product-grid-item")
    rows = []
    for card in cards:
        cat_code_tag = card.select_one(".product-category")
        category_code = _clean_text(cat_code_tag.get_text()) if cat_code_tag else None

        badge_tag = card.select_one(".product-badge")
        category_label = _clean_text(badge_tag.get_text()) if badge_tag else None

        name_tags = card.select(".product-name")
        authority = _clean_text(name_tags[0].get_text()) if len(name_tags) > 0 else None
        reference = _clean_text(name_tags[1].get_text()) if len(name_tags) > 1 else None

        desc_tag = card.select_one(".product-description")
        description = _clean_text(desc_tag.get_text()) if desc_tag else None
        if description and description.endswith("..."):
            description = description[:-3].strip()

        published_at = None
        content_tag = card.select_one(".product-grid-item-content")
        if content_tag is not None:
            m = PUBLISHED_RE.search(_clean_text(content_tag.get_text(" ")) or "")
            published_at = m.group(1) if m else None

        pdf_url = None
        details_available = False
        for btn in card.select(".product-grid-item-bottom button"):
            title = btn.get("title") or ""
            if title == "Telecharger" or title == "Télécharger":
                onclick = btn.get("onclick") or ""
                m = PDF_RE.search(onclick)
                if m:
                    pdf_url = m.group(1)
            elif title == "Details" or title == "Détails":
                details_available = not btn.has_attr("disabled")

        if pdf_url and pdf_url.startswith("./"):
            pdf_url = f"https://marchepublic.cd/portail/{pdf_url[2:]}"

        if authority is None and reference is None and description is None:
            raise UnexpectedShape(
                "a product-grid-item card has neither authority, reference, nor description -- "
                "page shape has likely changed"
            )

        rows.append(
            {
                "categoryCode": category_code,
                "categoryLabel": category_label,
                "authority": authority,
                "reference": reference,
                "description": description,
                "publishedAt": published_at,
                "pdfUrl": pdf_url,
                "detailsAvailable": details_available,
            }
        )
    return rows


def build_list_record(list_type: str, group_label: str, row: dict) -> dict:
    return {
        "_input": f"list:{list_type}",
        "_source": "S1-listing",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_LIST",
        "listType": list_type,
        "listGroup": group_label,
        **row,
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
