"""Parsing + record builders for MDN Algeria's tender-notice pages
(`appels_fr.php` / `archives_appels_fr.php`).

Both pages share one simple, hand-rolled (no CMS/JS framework) shape: a
flat sequence of `<button class="accordion">DATE</button>` headers, each
followed by a `<div class="panel">` holding one `<p><a href="...pdf"
target="_blank">FULL NOTICE TEXT</a></p>` per notice published that day.
There is no JSON/XML API and no RSS feed -- this is the site's only public
view of its own tender notices.
"""

import html as html_module
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

from src.constants import FRENCH_MONTHS

ACCORDION_RE = re.compile(
    r'<button class="accordion">([^<]+)</button>\s*<div class="panel">(.*?)</div>'
    r'\s*(?=<button class="accordion">|\Z|<!--)',
    re.S,
)
ITEM_RE = re.compile(r'<a href="([^"]+)"[^>]*target="_blank">\s*(.*?)\s*</a>', re.S)
DATE_RE = re.compile(r"(\d{1,2})\s+([A-Za-z\xc0-\xff]+)\s+(\d{4})")
REF_RE = re.compile(r"N[°ºØ]\s*([^\s]+)")

# Keyword -> notice-type classification, checked against the uppercased,
# accent-stripped start of each notice's own text. Best-effort only: this
# is a convenience field layered on top of the full raw text (always kept
# verbatim in `description`), never a substitute for it.
NOTICE_TYPE_RULES = [
    ("MISE EN DEMEURE", "DEFAULT_NOTICE"),
    ("AVIS D INFRUCTUOSITE", "UNSUCCESSFUL_TENDER_NOTICE"),
    ("INFRUCTUEU", "UNSUCCESSFUL_TENDER_NOTICE"),
    ("PROROGATION", "DEADLINE_EXTENSION_NOTICE"),
    ("ATTRIBUTION PROVISOIRE", "PROVISIONAL_AWARD_NOTICE"),
    ("ATTRIBUTION", "AWARD_NOTICE"),
    ("ANNULATION", "CANCELLATION_NOTICE"),
    ("RECTIFICATIF", "CORRIGENDUM_NOTICE"),
    ("APPEL D OFFRE", "TENDER_NOTICE"),
    ("CONSULTATION", "CONSULTATION_NOTICE"),
]


class UnexpectedShape(Exception):
    """Raised when a page no longer matches the structure this parser was
    written against -- must NOT be swallowed (project convention: fail
    loud, never silently emit an empty/corrupt record)."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _clean_text(raw_html: str) -> str:
    text = html_module.unescape(raw_html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_french_date(date_text: str) -> str | None:
    m = DATE_RE.search(date_text)
    if not m:
        return None
    day, month_name, year = m.groups()
    month = FRENCH_MONTHS.get(_strip_accents(month_name).lower())
    if month is None:
        return None
    return f"{int(year):04d}-{month:02d}-{int(day):02d}"


def _classify_notice(text: str) -> str:
    stripped = _strip_accents(text).upper().replace("'", " ").replace("’", " ")
    for keyword, notice_type in NOTICE_TYPE_RULES:
        if keyword in stripped:
            return notice_type
    return "OTHER"


def parse_tenders_page(html: str, page_url: str) -> list[dict]:
    day_blocks = ACCORDION_RE.findall(html)
    if not day_blocks:
        raise UnexpectedShape(
            "No '<button class=\"accordion\">...<div class=\"panel\">' day blocks found -- page shape may have changed"
        )

    rows: list[dict] = []
    for date_text_raw, panel_html in day_blocks:
        date_text = html_module.unescape(date_text_raw).strip()
        date_iso = _parse_french_date(date_text)
        items = ITEM_RE.findall(panel_html)
        for href, desc_html in items:
            description = _clean_text(desc_html)
            if not description:
                continue
            ref_match = REF_RE.search(description)
            rows.append(
                {
                    "date": date_iso,
                    "dateRaw": date_text,
                    "noticeType": _classify_notice(description),
                    "reference": ref_match.group(1).rstrip(".,;") if ref_match else None,
                    "description": description,
                    "pdfUrl": urljoin(page_url, href),
                }
            )

    if not rows:
        raise UnexpectedShape("Found day blocks but zero notice items -- panel/item shape may have changed")
    return rows


# ---------------------------------------------------------------------------
# Dataset envelope
# ---------------------------------------------------------------------------


def build_record(mode: str, source: str, fields: dict) -> dict:
    return {
        "_input": f"mode:{mode}",
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_NOTICE",
        **fields,
    }


def build_error_record(mode: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": f"mode:{mode}",
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
