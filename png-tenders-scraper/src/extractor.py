"""Parses NPC (National Procurement Commission, Papua New Guinea) HTML pages
and REST rows into dataset-ready records.

Three extraction paths, matching the three record types documented in
`constants.py`:

- `parse_tender_cards`: the `/tender-advertisement/` listing page -- every
  open tender's full data lives inline in the listing HTML itself (no
  separate detail page exists for this JetEngine Custom Content Type).
- `flatten_rest_row`: one row from `/wp-json/wp/v2/<disposals-notice|
  contracts-awarded>` -- list-only fields (id/title/slug/link/date); real
  post types, so this is clean JSON, no HTML parsing.
- `parse_detail_fields`: the individual detail page for a disposals-notice
  or contracts-awarded row -- JetEngine "Dynamic Field" widgets rendered as
  `<b>Label:</b> value` inside `<main id="jet-theme-core-single">`, kept as
  a raw `{label: value}` dict per `.ai/CLAUDE.md` principle 5 (upstream
  label text is free-form, not a fixed schema).
"""

import html as ihtml
import re
from datetime import datetime, timezone

SOURCE_TENDERS = "S1-tender-advertisement-html"
SOURCE_REST_LIST = "S1-wp-rest-list"
SOURCE_DETAIL = "S2-detail-html"


class UnexpectedShape(Exception):
    """Raised when a page/response doesn't look like anything this parser
    recognizes -- propagates and fails the run loudly rather than silently
    emitting an empty/partial record, per `.ai/CLAUDE.md` principle 6."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = ihtml.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Tender Advertisement listing page (open tenders, no detail page)
# ---------------------------------------------------------------------------

_TENDER_ITEM_RE = re.compile(
    r'jet-listing-grid__item jet-listing-dynamic-post-(\d+)"\s*data-post-id="\d+"'
)
_DYNAMIC_FIELD_RE = re.compile(
    r'<(h4|h2|p|div)[^>]*\bjet-listing-dynamic-field__content\b[^>]*>(.*?)</\1>', re.S
)
_BUTTON_TEXT_RE = re.compile(r'elementor-button-text">([^<]*)</span>')
_PDF_HREF_RE = re.compile(r'href="([^"]+\.pdf)"')
_CLOSING_DATE_RE = re.compile(r"CLOSING DATE\s*&?\s*(?:TIME)?:?\s*(.*)", re.I)


def parse_tender_cards(page_html: str) -> list[dict]:
    """Parses every open-tender card on `/tender-advertisement/`. Each card
    holds (in this order): a long-form description field, a short title
    field, a `NPC/YYYY-NN`-style reference-number button, a closing-date
    line, and a "Download Tender Advert" button linking the PDF. Confirmed
    consistent across all 6 cards observed during recon (2026-08-27).

    Raises `UnexpectedShape` if the page no longer contains the listing
    grid marker at all (site redesign). Returns an empty list if the marker
    is present but there are genuinely zero open tenders right now (a real,
    valid state -- NPC's tender count fluctuates).
    """
    if "jet-listing-grid__items" not in page_html:
        raise UnexpectedShape(
            "tender-advertisement page missing 'jet-listing-grid__items' marker -- "
            "site structure may have changed"
        )

    matches = list(_TENDER_ITEM_RE.finditer(page_html))
    if not matches:
        return []

    bounds = [m.start() for m in matches] + [len(page_html)]
    cards = []
    for i, m in enumerate(matches):
        # Bound each card to the next item's start (or a following <footer>,
        # whichever comes first) so the last card doesn't swallow unrelated
        # sitewide footer/nav PDF links.
        end = bounds[i + 1]
        footer_idx = page_html.find("<footer", bounds[i], end)
        if footer_idx != -1:
            end = footer_idx
        block = page_html[bounds[i]:end]

        post_id = m.group(1)
        fields = [_clean_text(content) for _tag, content in _DYNAMIC_FIELD_RE.findall(block)]
        buttons = [_clean_text(b) for b in _BUTTON_TEXT_RE.findall(block)]
        pdfs = _PDF_HREF_RE.findall(block)

        description = fields[0] if len(fields) > 0 else None
        title = fields[1] if len(fields) > 1 else None
        closing_date_line = fields[2] if len(fields) > 2 else None
        closing_date = None
        if closing_date_line:
            cm = _CLOSING_DATE_RE.search(closing_date_line)
            closing_date = cm.group(1).strip() if cm else closing_date_line

        reference_number = buttons[0] if buttons else None

        cards.append(
            {
                "post_id": post_id,
                "reference_number": reference_number,
                "title": title,
                "description": description,
                "closing_date": closing_date,
                "pdf_url": pdfs[0] if pdfs else None,
            }
        )
    return cards


def build_tender_record(card: dict, source_url: str) -> dict:
    return {
        "_input": "(open tenders)",
        "_source": SOURCE_TENDERS,
        "_scrapedAt": utc_now_iso(),
        "record_type": "tender_notice",
        "source_url": source_url,
        **card,
    }


# ---------------------------------------------------------------------------
# REST list discovery (disposals-notice / contracts-awarded)
# ---------------------------------------------------------------------------


def flatten_rest_row(row: dict, record_type: str) -> dict:
    if "id" not in row or "link" not in row:
        raise UnexpectedShape(f"{record_type} row missing id/link: keys={sorted(row)}")
    title = row.get("title", {})
    title_text = title.get("rendered") if isinstance(title, dict) else title
    return {
        "id": row["id"],
        "record_type": record_type,
        # WordPress's REST API always HTML-entity-escapes title.rendered
        # (e.g. "&#8211;" for an en dash) -- unescaped here the same way
        # this portfolio's WordPress-backed news actors already do.
        "title": ihtml.unescape(title_text) if isinstance(title_text, str) else title_text,
        "slug": row.get("slug"),
        "link": row.get("link"),
        "date": row.get("date"),
    }


# ---------------------------------------------------------------------------
# Detail pages (disposals-notice / contracts-awarded single-item template)
# ---------------------------------------------------------------------------

_MAIN_SINGLE_RE = re.compile(
    r'<main id="jet-theme-core-single".*?</main>', re.S
)
_LABELED_FIELD_RE = re.compile(
    r'<(h4|h2|p|div)[^>]*\bjet-listing-dynamic-field__content\b[^>]*>\s*<b>(.*?)</b>\s*(?:<br\s*/?>)?\s*(.*?)</\1>',
    re.S,
)


def parse_detail_fields(page_html: str) -> dict:
    """Parses the labeled `<b>Label:</b> value` fields and the single
    notice-specific PDF (if any) from a disposals-notice/contracts-awarded
    detail page, bounded to `<main id="jet-theme-core-single">` so sitewide
    header/sidebar/footer PDF links (Procurement Act, Good Procurement
    Manual, etc.) never leak in. Raises `UnexpectedShape` if that wrapper is
    missing entirely (template changed); an empty `fields` dict for a page
    that has the wrapper but no labeled fields is treated as valid (some
    records genuinely carry little beyond their title)."""
    m = _MAIN_SINGLE_RE.search(page_html)
    if not m:
        raise UnexpectedShape(
            "detail page missing '<main id=\"jet-theme-core-single\">' wrapper -- "
            "site structure may have changed"
        )
    block = m.group(0)

    fields = {}
    for _tag, label, value in _LABELED_FIELD_RE.findall(block):
        label_clean = _clean_text(label).rstrip(":")
        value_clean = _clean_text(value)
        if label_clean:
            fields[label_clean] = value_clean

    pdfs = _PDF_HREF_RE.findall(block)
    return {"fields": fields, "pdf_url": pdfs[0] if pdfs else None}


def build_listing_record(row: dict, detail: dict | None) -> dict:
    record = {
        "_input": row["record_type"],
        "_source": SOURCE_DETAIL if detail is not None else SOURCE_REST_LIST,
        "_scrapedAt": utc_now_iso(),
        **row,
    }
    if detail is not None:
        record["fields"] = detail["fields"]
        record["pdf_url"] = detail["pdf_url"]
    return record


def extract_error(input_label: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": input_label,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
