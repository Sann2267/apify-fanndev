"""Builds dataset-ready records from ODPIC's `publication_registre` WordPress
REST rows.

The API already returns clean, flat-ish JSON per filing -- no HTML/tree
parsing needed (contrast with `botswana-cipa-scraper` or
`malawi-cripc-scraper`). This module strips the generic WordPress CMS/
hypermedia scaffolding (`guid`, `content`, `template`, `class_list`,
`_links`, duplicate `modified*` timestamps) that carries no registry
information for this post type, unwraps `title.rendered` the same way this
portfolio's news actors already do, and otherwise does raw passthrough of
every substantive field ODPIC returns (per `.ai/CLAUDE.md` principle 5),
wrapped in this portfolio's standard `_input`/`_source`/`_scrapedAt`
envelope. See `constants.py` for why this flattening was chosen.
"""

from datetime import datetime, timezone

SOURCE = "S1-odpic-rest"

# Substantive fields kept verbatim from each upstream row, in addition to
# the identification fields (id/slug/link/date) and the unwrapped title.
PASSTHROUGH_FIELDS = [
    "file_nbr",
    "file_ser",
    "registration_date",
    "filing_date",
    "main_owner_person_nbr",
    "person_name",
    "addresses",
    "disclaimers",
]


class UnexpectedShape(Exception):
    """Raised when the API response doesn't look like anything this client
    recognizes -- propagates and fails the run loudly rather than silently
    emitting an empty/partial record, per `.ai/CLAUDE.md` principle 6."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def flatten_row(row: dict) -> dict:
    if "id" not in row or "title" not in row:
        raise UnexpectedShape(f"publication_registre row missing id/title: keys={sorted(row)}")
    title = row.get("title", {})
    flat = {
        "id": row["id"],
        "title": title.get("rendered") if isinstance(title, dict) else title,
        "slug": row.get("slug"),
        "link": row.get("link"),
        "date": row.get("date"),
    }
    for field in PASSTHROUGH_FIELDS:
        if field in row:
            flat[field] = row[field]
    return flat


def build_record(query_label: str, row: dict) -> dict:
    return {
        "_input": query_label,
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        **flatten_row(row),
    }


def extract_error(query_label: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": query_label,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
