"""Parsing + record builders for gov.sr's two public tender data sources:
`tenders` (the `aanbestedingen` custom post type -- thin, ministry-level,
mostly Dutch) and `notices` (regular posts tagged "Aanbestedingen" -- richer,
internationally/donor-financed, mostly English, full body content included).

Both sources are genuine JSON REST responses, not HTML scraping -- see
constants.py for the full recon summary of why no OCDS API, RSS feed, or JS
bundle was needed here.
"""

import html as html_module
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Raised when a response no longer matches the structure this parser
    was written against -- must NOT be swallowed (see project convention:
    fail loud, never silently emit an empty/corrupt record)."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = html_module.unescape(value).strip()
    return value or None


def _iso_z(gmt_value: str | None) -> str | None:
    """WordPress `*_gmt` fields come back as naive `YYYY-MM-DDTHH:MM:SS`
    (already UTC, no offset/suffix) -- normalize to a proper `Z`-suffixed
    ISO 8601 string rather than passing the ambiguous naive form through."""
    if not gmt_value:
        return None
    return gmt_value if gmt_value.endswith("Z") else f"{gmt_value}Z"


def _html_to_text(rendered_html: str | None) -> str | None:
    if not rendered_html:
        return None
    soup = BeautifulSoup(rendered_html, "lxml")
    text = soup.get_text("\n", strip=True)
    return text or None


def parse_wp_json_list(body: str, endpoint_label: str) -> list[dict]:
    """Parses a WordPress REST API list response. Raises UnexpectedShape if
    the body isn't a JSON array of objects (a legitimately empty page --
    `[]` -- is NOT an error; that's the normal end-of-pagination signal and
    is returned as-is for the caller to detect)."""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"{endpoint_label} returned non-JSON body: {e}") from e

    if not isinstance(payload, list):
        raise UnexpectedShape(
            f"{endpoint_label} returned a JSON {type(payload).__name__}, not a list "
            f"-- likely a WP REST error object (shape may have changed): {str(payload)[:300]}"
        )
    for item in payload:
        if not isinstance(item, dict) or "id" not in item or "title" not in item:
            raise UnexpectedShape(f"{endpoint_label} list item missing expected id/title fields -- shape may have changed")
    return payload


def _embedded_terms(raw: dict) -> list[dict]:
    embedded = raw.get("_embedded") or {}
    term_groups = embedded.get("wp:term") or []
    terms: list[dict] = []
    for group in term_groups:
        for term in group:
            if term.get("taxonomy") == "category":
                terms.append(term)
    return terms


# ---------------------------------------------------------------------------
# tenders -- `aanbestedingen` custom post type (thin, ministry-level)
# ---------------------------------------------------------------------------


def build_tender_record(raw: dict) -> dict:
    terms = _embedded_terms(raw)
    return {
        "id": raw.get("id"),
        "title": _clean((raw.get("title") or {}).get("rendered")),
        "slug": raw.get("slug"),
        "link": raw.get("link"),
        "status": raw.get("status"),
        "publishedAt": _iso_z(raw.get("date_gmt")),
        "modifiedAt": _iso_z(raw.get("modified_gmt")),
        "ministry": _clean(terms[0]["name"]) if terms else None,
        "ministrySlug": terms[0].get("slug") if terms else None,
        "ministryCategories": [_clean(t["name"]) for t in terms] if len(terms) > 1 else None,
        "categoryIds": raw.get("categories"),
    }


# ---------------------------------------------------------------------------
# notices -- regular `post`s tagged "Aanbestedingen" (rich, donor-financed)
# ---------------------------------------------------------------------------


def build_notice_record(raw: dict) -> dict:
    terms = _embedded_terms(raw)
    content_html = (raw.get("content") or {}).get("rendered")
    excerpt_html = (raw.get("excerpt") or {}).get("rendered")
    return {
        "id": raw.get("id"),
        "title": _clean((raw.get("title") or {}).get("rendered")),
        "slug": raw.get("slug"),
        "link": raw.get("link"),
        "status": raw.get("status"),
        "publishedAt": _iso_z(raw.get("date_gmt")),
        "modifiedAt": _iso_z(raw.get("modified_gmt")),
        "categories": [_clean(t["name"]) for t in terms] or None,
        "excerptText": _html_to_text(excerpt_html),
        "contentText": _html_to_text(content_html),
        "contentHtml": content_html,
    }


# ---------------------------------------------------------------------------
# Dataset envelope
# ---------------------------------------------------------------------------

RECORD_TYPES = {"tenders": "TENDER", "notices": "TENDER_NOTICE"}
SOURCE_TAGS = {
    "tenders": "S1-wp-rest-aanbestedingen-cpt",
    "notices": "S1-wp-rest-posts-category-aanbestedingen",
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
