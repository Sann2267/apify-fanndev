"""Parsing logic for treasury.gov.lk's Next.js-embedded page data.

Every page on this site ships its data pre-rendered inline as
`<script id="__NEXT_DATA__" type="application/json">{...}</script>`. This
module extracts that JSON blob and validates the two shapes this actor
depends on:

- Current notices page: `pageProps == {"notices": [...], "count": N}`
- Archive page:         `pageProps == {"sections": [...], "count": N, "page": N, ...}`

Both are parsed generically (raw passthrough of upstream's own field names)
rather than mapped to a fixed set of named columns, since the Ministry's own
field set already varies notice-to-notice (see CRAWLING_METHOD.md) --
a `<h2>`/label reshuffle degrades gracefully, while the __NEXT_DATA__ script
tag disappearing entirely (a genuine site rewrite) raises UnexpectedShape
instead of silently returning nothing.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import BASE, CURRENT_FILE_DOWNLOAD_URL_TMPL

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)


class UnexpectedShape(Exception):
    """Upstream page shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _html_to_text(html_fragment: str | None) -> str | None:
    if not html_fragment:
        return None
    text = BeautifulSoup(html_fragment, "lxml").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def extract_next_data(html_text: str) -> dict:
    """Returns the parsed __NEXT_DATA__ JSON object, or raises
    UnexpectedShape if the script tag is missing or not valid JSON --
    this is the actor's single choke point for "the site changed shape
    entirely" (e.g. migrated off Next.js)."""
    import json

    m = NEXT_DATA_RE.search(html_text)
    if not m:
        raise UnexpectedShape("no <script id=\"__NEXT_DATA__\"> found -- page shape has likely changed")
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"__NEXT_DATA__ script tag content is not valid JSON: {e}") from e


# ---------------------------------------------------------------------------
# Current notices
# ---------------------------------------------------------------------------


def parse_current_notices(html_text: str) -> dict:
    """Returns {"notices": [...], "count": N}."""
    data = extract_next_data(html_text)
    page_props = data.get("props", {}).get("pageProps", {})
    if "notices" not in page_props or not isinstance(page_props["notices"], list):
        raise UnexpectedShape(
            f"pageProps missing a 'notices' list (keys found: {list(page_props)}) -- page shape has likely changed"
        )
    return {"notices": page_props["notices"], "count": page_props.get("count")}


def _resolve_current_attachment(att: dict) -> dict:
    file_id = att.get("link")
    download_url = CURRENT_FILE_DOWNLOAD_URL_TMPL.format(file_id=file_id) if file_id else None
    return {**att, "downloadUrl": download_url}


def build_current_record(notice: dict, total_count: int | None) -> dict:
    attachments = [_resolve_current_attachment(a) for a in (notice.get("attachments") or [])]
    return {
        "_input": "latest",
        "_source": "S1-current-notices",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_CURRENT",
        "_totalAvailable": total_count,
        **{k: v for k, v in notice.items() if k != "attachments"},
        "descriptionText": _html_to_text(notice.get("description")),
        "attachments": attachments,
    }


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------


def parse_archive_page(html_text: str) -> dict:
    """Returns {"sections": [...], "count": N, "page": N}."""
    data = extract_next_data(html_text)
    page_props = data.get("props", {}).get("pageProps", {})
    if "sections" not in page_props or not isinstance(page_props["sections"], list):
        raise UnexpectedShape(
            f"pageProps missing a 'sections' list (keys found: {list(page_props)}) -- page shape has likely changed"
        )
    return {
        "sections": page_props["sections"],
        "count": page_props.get("count"),
        "page": page_props.get("page"),
    }


def _resolve_archive_attachments(section: dict) -> list[dict]:
    raw = [item for item in (section.get("data") or []) if item]
    resolved = []
    for item in raw:
        link = item.get("link")
        download_url = (BASE + link) if link and link.startswith("/") else link
        resolved.append({**item, "downloadUrl": download_url})
    return resolved


def build_archive_record(section: dict, page: int, total_count: int | None) -> dict:
    return {
        "_input": f"archive:page{page}",
        "_source": "S1-archive",
        "_scrapedAt": utc_now_iso(),
        "recordType": "TENDER_ARCHIVE",
        "_page": page,
        "_totalAvailable": total_count,
        "id": section.get("id"),
        "label": section.get("label"),
        "descriptionHtml": section.get("html"),
        "descriptionText": _html_to_text(section.get("html")),
        "attachments": _resolve_archive_attachments(section),
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
