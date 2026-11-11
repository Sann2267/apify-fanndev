"""Parsing logic -- turns `gateway2-beta.karir.com` JSON API responses
into dataset-ready records.

Per .ai/conventions/dataset-envelope.md, upstream field names are kept
verbatim (no renaming) -- karir.com's own `v1/opportunity/detail` object
is already rich and self-describing (job_position, location, salary_lower/
salary_upper, requirements, responsibilities, company{...}, ...), so
records are the raw upstream object plus the standard envelope tags.
"""

import re
from datetime import datetime, timezone

from src.constants import DISALLOWED_OPPORTUNITY_IDS


class UnexpectedShape(Exception):
    """Upstream JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def wrap(item: dict, input_value: str, source: str) -> dict:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        **item,
    }


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


_ID_RE = re.compile(r"/opportunities/(\d+)")


def parse_opportunity_id(value: str) -> str:
    """Accepts a bare numeric ID or a full karir.com/opportunities/<id> URL."""
    value = value.strip()
    if value.isdigit():
        return value
    m = _ID_RE.search(value)
    if m:
        return m.group(1)
    raise ValueError(f"Could not parse an opportunity ID out of {value!r}.")


def is_disallowed(opportunity_id: str) -> bool:
    return opportunity_id in DISALLOWED_OPPORTUNITY_IDS


def extract_search_page(body: dict) -> tuple[list[dict], int]:
    """Returns (raw_opportunities, total_opportunities) for one page of
    `v2/search/opportunities`."""
    if body.get("code") != 200:
        raise UnexpectedShape(f"Search API returned non-200 `code`: {body.get('code')} / {body.get('message')}")
    data = body.get("data")
    if data is None:
        raise UnexpectedShape("Search API response missing `data` -- shape has likely changed.")
    opportunities = data.get("opportunities")
    if opportunities is None:
        raise UnexpectedShape("Search API `data.opportunities` missing -- shape has likely changed.")
    total = data.get("total_opportunities")
    if total is None:
        raise UnexpectedShape("Search API `data.total_opportunities` missing -- shape has likely changed.")
    return opportunities, total


def wrap_search_item(item: dict, input_value: str) -> dict:
    return wrap(item, input_value, "S1-search-api")


def extract_detail(body: dict) -> dict | None:
    """Returns the full opportunity detail object, or None if the API
    reports the job as not found (rather than raising -- a legitimate
    not-found is a normal outcome for a stale/expired ID)."""
    code = body.get("code")
    if code == 404:
        return None
    if code != 200:
        raise UnexpectedShape(f"Detail API returned non-200 `code`: {code} / {body.get('message')}")
    data = body.get("data")
    if not data:
        return None
    if "job_position" not in data:
        raise UnexpectedShape("Detail API `data` missing `job_position` -- shape has likely changed.")
    return data


def wrap_detail(data: dict, input_value: str, is_urgent: bool | None = None) -> dict:
    record = dict(data)
    if is_urgent is not None:
        record["is_urgent"] = is_urgent
    return wrap(record, input_value, "S1-detail-api")
