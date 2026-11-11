"""Parsing logic for armp.cm (ARMP Cameroon) pages.

Listing pages (homepage "/" mixing every publication type, or
"/filtres?type=avis&val=<n>" filtered to one procurement category) share the
same `<ul id="tout_les_avis"><li class="list-group-item ...">` row shell.
Labels inside each row (procuring entity, region, amount, dates...) are
rendered in whichever UI language the visitor's session defaults to (French
"MO/AC"/"Publie le" or English "PO/CA"/"Published on the" were both observed
live, seemingly session-dependent, not URL-controlled) -- so fields are
extracted **positionally** (first `.d-table-row` in the left column is always
the procuring entity, second is always the category type, etc.) rather than
matched by label text, and the row layout raises UnexpectedShape if the
expected number of sub-rows isn't found.

The publication-detail page (`/details?type_publication=X&id_publication=Y`)
has two distinct genuine shapes depending on `type_publication`:
- Tender/quotation notices (AO, DC, AMI, ...) -- server-templated numbered
  sections ("1.Objet", "2.Consistance des prestations", ...).
- Award decisions/communiques/addenda (DEC-ATTR, COMM, ADDITIF, ...) --
  free-form HTML pasted from Word (MsoNormal/table markup), no numbered
  sections at all.
Both are handled; which shape a given record actually has is reported via
`_source` so nothing is silently forced into the wrong shape.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

RESOURCE_LINK_RE = re.compile(r"type_publication=([A-Za-z-]+)&id_publication=(\d+)")


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


def _clean_block_text(text: str | None) -> str | None:
    """Like _clean_text but preserves paragraph/line breaks (collapses
    whitespace within a line, drops blank lines) -- used for the free-form
    Word-pasted detail body, where flattening everything to one line would
    make a multi-paragraph decision/communique much harder to read."""
    if text is None:
        return None
    lines = [re.sub(r"\s+", " ", ln.replace("\xa0", " ")).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines) or None


def _row_value_cell(row_div) -> tuple[str | None, bool]:
    """Given a `.d-table-row` div with (label-cell, value-cell) children,
    returns (value text, is_visible). is_visible is False when the value
    cell itself carries the `d-none` class (armp.cm's own way of marking a
    field as not applicable for this record, e.g. closing date/time on an
    award-decision row) -- the raw text is still returned either way."""
    cells = row_div.find_all("div", recursive=False)
    if len(cells) < 2:
        raise UnexpectedShape(f"expected a label+value pair in a .d-table-row, got {len(cells)} child div(s)")
    value_cell = cells[1]
    classes = value_cell.get("class") or []
    return _clean_text(value_cell.get_text(" ", strip=True)), "d-none" not in classes


# ---------------------------------------------------------------------------
# Listing pages
# ---------------------------------------------------------------------------


def find_category_total(html_text: str, val: str) -> int | None:
    """Reads the exact total-record count for one "avis" category straight
    from the page's own sidebar badge (present on every page, not just the
    homepage) -- this is armp.cm's own live count, not something we compute
    from pagination. Returns None for the "latest" (mixed, val=None) view,
    which has no single matching badge."""
    if val is None:
        return None
    soup = BeautifulSoup(html_text, "lxml")
    target_href = f"./filtres?type=avis&val={val}"
    for a in soup.select("a.armp-color-black"):
        if a.get("href") == target_href:
            badge = a.select_one("span.badge")
            if badge:
                digits = re.sub(r"[^\d]", "", badge.get_text())
                return int(digits) if digits else None
    return None


def find_last_page_seen(html_text: str) -> int | None:
    """Scans the pagination nav for the highest page number linked from the
    current page (Laravel's paginator only renders a window around the
    current page plus first/last, so this grows as later pages are visited
    -- it's a floor on total pages, reported honestly rather than implying a
    firm total)."""
    soup = BeautifulSoup(html_text, "lxml")
    nav = soup.select_one("#my_pagination")
    if nav is None:
        return None
    pages = [int(m.group(1)) for a in nav.select("a.page-link") if (m := re.search(r"page=(\d+)", a.get("href", "")))]
    return max(pages) if pages else None


def parse_list_page(html_text: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")
    ul = soup.select_one("ul#tout_les_avis")
    if ul is None:
        raise UnexpectedShape("no ul#tout_les_avis found -- page shape has likely changed")

    rows = []
    for li in ul.find_all("li", class_="list-group-item", recursive=False):
        strong = li.select_one(".text-left.line-clamp strong")
        title = _clean_text(strong.get("title") or strong.get_text(" ", strip=True)) if strong else None

        left_col = li.select_one(".col-md-6.d-table")
        right_col = li.select_one(".col-md-5.d-table")
        if left_col is None or right_col is None:
            raise UnexpectedShape("listing row missing the col-md-6/col-md-5 info columns -- page shape has likely changed")

        left_rows = left_col.find_all("div", class_="d-table-row", recursive=False)
        if len(left_rows) != 4:
            raise UnexpectedShape(
                f"expected 4 .d-table-row in the left info column (procuring entity/type/region/amount), got {len(left_rows)}"
            )
        procuring_entity, _ = _row_value_cell(left_rows[0])
        type_label, _ = _row_value_cell(left_rows[1])
        region, _ = _row_value_cell(left_rows[2])
        amount, _ = _row_value_cell(left_rows[3])

        right_rows = right_col.find_all("div", class_="d-table-row", recursive=False)
        if len(right_rows) != 4:
            raise UnexpectedShape(
                f"expected 4 .d-table-row in the right info column (published/closing date/closing time/links), got {len(right_rows)}"
            )
        published_at, _ = _row_value_cell(right_rows[0])
        closing_date, closing_date_visible = _row_value_cell(right_rows[1])
        closing_time, closing_time_visible = _row_value_cell(right_rows[2])

        links_row = right_rows[3]
        notice_link = links_row.find("a")
        notice_pdf_url = notice_link.get("href") if notice_link else None

        buttons_col = li.select_one(".col-md-1")
        details_url = None
        dao_pdf_url = None
        type_publication = None
        id_publication = None
        if buttons_col is not None:
            for a in buttons_col.find_all("a"):
                href = a.get("href") or ""
                classes = a.get("class") or []
                m = RESOURCE_LINK_RE.search(href)
                if "/details?" in href:
                    details_url = href
                    if m:
                        type_publication, id_publication = m.group(1), m.group(2)
                elif "0903_dao_dl" in href and "d-none" not in classes:
                    dao_pdf_url = href

        if details_url is None or type_publication is None:
            raise UnexpectedShape("listing row has no /details link with a type_publication/id_publication pair")

        rows.append(
            {
                "typePublication": type_publication,
                "idPublication": id_publication,
                "title": title,
                "procuringEntity": procuring_entity,
                "type": type_label,
                "region": region,
                "amount": amount,
                "publishedAt": published_at,
                "closingDate": closing_date if closing_date_visible else None,
                "closingTime": closing_time if closing_time_visible else None,
                "noticePdfUrl": notice_pdf_url,
                "daoPdfUrl": dao_pdf_url,
                "detailsUrl": f"https://armp.cm{details_url}" if details_url.startswith("/") else details_url,
            }
        )

    return {"rows": rows}


def build_list_record(list_type: str, row: dict, total_available: int | None, last_page_seen: int | None, page: int) -> dict:
    return {
        "_input": f"list:{list_type}",
        "_source": "S1-listing",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_LIST",
        "listType": list_type,
        "_page": page,
        "_totalAvailable": total_available,
        "_lastPageSeen": last_page_seen,
        **row,
    }


# ---------------------------------------------------------------------------
# Publication detail page
# ---------------------------------------------------------------------------

SECTION_RE = re.compile(r"^\s*(\d+)\s*[.\-]\s*(.+)$", re.DOTALL)


def _slugify_label(label: str) -> str:
    label = label.replace("\xa0", " ").strip()
    words = [w for w in re.split(r"[^A-Za-z0-9]+", label) if w]
    if not words:
        return "field"
    first, rest = words[0].lower(), words[1:]
    return first + "".join(w.capitalize() for w in rest)


def parse_detail_page(html_text: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    ac_mo_tag = soup.select_one("div.ac_mo")
    entete_tag = soup.select_one("div.entete_avis")
    if ac_mo_tag is None and entete_tag is None:
        raise UnexpectedShape("neither div.ac_mo nor div.entete_avis found -- page shape has likely changed")

    procuring_entity = _clean_text(ac_mo_tag.get_text(" ", strip=True)) if ac_mo_tag else None

    title = None
    source_financement = None
    if entete_tag is not None:
        sf_tag = entete_tag.select_one("div.source-financement")
        sf_visible = sf_tag is not None and "d-none" not in (sf_tag.get("class") or [])
        if sf_tag is not None:
            sf_value_tag = sf_tag.find_all("div")
            sf_text = _clean_text(sf_value_tag[-1].get_text(" ", strip=True)) if sf_value_tag else None
            source_financement = sf_text if sf_visible else None
            sf_tag.extract()  # remove so the title text below doesn't include it
        title = _clean_text(entete_tag.get_text(" ", strip=True))

    notice_pdf_url = None
    dao_pdf_url = None
    clearfix = soup.select_one("div.clearfix")
    if clearfix is not None:
        left = clearfix.select_one("div.float-left")
        right = clearfix.select_one("div.float-right")
        if left is not None:
            a = left.find("a")
            notice_pdf_url = a.get("href") if a else None
        if right is not None and "d-none" not in (right.get("class") or []):
            a = right.find("a")
            dao_pdf_url = a.get("href") if a else None

    # The real content wrapper is the `div.my-4` sibling right after
    # div.clearfix -- NOT just "the first div.my-4 in the page", because
    # div.ac_mo (the procuring-entity header, already parsed above) itself
    # also carries a `my-4` class (`class="ac_mo text-center font-weigth-bold
    # my-4"`), so a plain `soup.select_one("div.my-4")` silently grabs that
    # instead of the actual body -- confirmed by inspecting the real DOM.
    content_div = clearfix.find_next_sibling("div", class_="my-4") if clearfix is not None else None
    if content_div is None:
        all_my4 = soup.select("div.my-4")
        content_div = all_my4[-1] if all_my4 else None

    # Structured shape: numbered "N.Label" sections (tender/quotation notices).
    sections = {}
    section_list = []
    for row in (content_div.select("div.my-1.row") if content_div is not None else []):
        label_tag = row.select_one(".my-1.font-weight-bolder strong")
        body_tag = row.select_one(".my-1.w-100:not(.font-weight-bolder)")
        if label_tag is None or body_tag is None:
            continue
        label_tag = BeautifulSoup(str(label_tag), "lxml")  # work on a detached copy
        for badge in label_tag.select("span.badge"):
            badge.extract()
        raw_label = _clean_text(label_tag.get_text(" ", strip=True))
        if not raw_label:
            continue
        m = SECTION_RE.match(raw_label)
        if not m:
            continue
        number, label = m.group(1), _clean_text(m.group(2))
        text = _clean_text(body_tag.get_text(" ", strip=True))
        key = _slugify_label(label) if label else f"section{number}"
        sections[key] = text
        section_list.append({"number": int(number), "label": label, "text": text})

    if section_list:
        return {
            "shape": "structured",
            "procuringEntity": procuring_entity,
            "title": title,
            "sourceFinancement": source_financement,
            "noticePdfUrl": notice_pdf_url,
            "daoPdfUrl": dao_pdf_url,
            "sections": sections,
            "sectionList": sorted(section_list, key=lambda s: s["number"]),
        }

    # Free-form shape: award decisions / communiques / addenda (Word-pasted HTML).
    body_text = _clean_block_text(content_div.get_text("\n", strip=True)) if content_div is not None else None

    return {
        "shape": "freeform",
        "procuringEntity": procuring_entity,
        "title": title,
        "sourceFinancement": source_financement,
        "noticePdfUrl": notice_pdf_url,
        "daoPdfUrl": dao_pdf_url,
        "bodyText": body_text,
    }


def build_detail_record(type_publication: str, id_publication: str, parsed: dict) -> dict:
    return {
        "_input": f"{type_publication}:{id_publication}",
        "_source": f"S1-detail-{parsed['shape']}",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_DETAIL",
        "typePublication": type_publication,
        "idPublication": id_publication,
        "detailsUrl": f"https://armp.cm/details?type_publication={type_publication}&id_publication={id_publication}",
        **{k: v for k, v in parsed.items() if k != "shape"},
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
