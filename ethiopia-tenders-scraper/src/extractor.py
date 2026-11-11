"""Parse Ethiopia eGP's CMS "Publication Plan Lots" JSON API into
dataset-ready records.

Per this portfolio's raw-passthrough convention
(.ai/conventions/dataset-envelope.md) every field the upstream API returns
is kept, spread verbatim into the record alongside a small set of flattened
convenience fields (title/organization/fiscalYear/...) added on top for
readability in the dataset's Overview table -- nothing upstream is renamed
or dropped.
"""

from datetime import datetime, timezone

from src.constants import DETAIL_URL, LIST_URL, ORDER_BY_FIELD, PAGE_SIZE


class UnexpectedShape(Exception):
    """Raised when a response that returned HTTP 200 doesn't contain the
    JSON structure this actor expects -- signals an upstream API change
    rather than a normal empty-result response. See .ai/CLAUDE.md
    principle #6: fail loud, never emit a silently-empty "success" record.
    """


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def loc(value, lang: str = "en") -> str | None:
    """Picks one language out of Ethiopia eGP's bilingual {"am": ..., "en":
    ...} field objects, falling back to Amharic then any other populated
    language if English is missing/empty."""
    if not isinstance(value, dict):
        return value
    if value.get(lang):
        return value[lang]
    for v in value.values():
        if v:
            return v
    return None


def build_list_params(skip: int, top: int, fiscal_year_id: str | None) -> dict:
    """CollectionQuery params for `get-publication-lots`.

    `Count=false` + a non-empty `OrderBy` are both required -- omitting
    OrderBy (or using most business-meaningful field names) triggers a
    server-side bug on this platform's sibling endpoints (see
    CRAWLING_METHOD.md). `timestamp` is the one field confirmed to sort
    correctly here, newest first with direction=1.
    """
    params = {
        "Skip": skip,
        "Top": top,
        "Count": "false",
        "OrderBy[0].field": ORDER_BY_FIELD,
        "OrderBy[0].direction": "1",
    }
    if fiscal_year_id:
        params["Filter[0][0].field"] = "fiscalYearId"
        params["Filter[0][0].value"] = fiscal_year_id
        params["Filter[0][0].operator"] = "="
    return params


def parse_list_response(data) -> tuple[list[dict], int | None]:
    if not isinstance(data, dict) or "items" not in data:
        raise UnexpectedShape(f"Response is not a {{total, items}} object: {str(data)[:300]!r}")
    items = data["items"]
    if not isinstance(items, list):
        raise UnexpectedShape(f"'items' is not a list: {type(items)}")
    return items, data.get("total")


def parse_detail_response(data) -> dict:
    if not isinstance(data, dict) or "items" not in data:
        raise UnexpectedShape(f"Detail response is not an {{items, milestones}} object: {str(data)[:300]!r}")
    if not data["items"]:
        raise UnexpectedShape("Detail response has an empty 'items' array -- lot id likely does not exist")
    return data


def build_list_record(query: str, item: dict) -> dict:
    mechanism = item.get("procurementMechanism") or {}
    return {
        "_input": query,
        "_source": "S1-cms-publication-lots-api",
        "_scrapedAt": utc_now_iso(),
        "title": loc(item.get("name")) or loc(item.get("description")),
        "description": loc(item.get("description")),
        "organization": loc(item.get("organizationName")),
        "fiscalYear": loc(item.get("budgetYearName")),
        "procurementCategory": mechanism.get("procurementCategory")
        or item.get("publicationProcurementMechanismProcurementCategory"),
        "procurementMethod": mechanism.get("procurementMethod")
        or item.get("publicationProcurementMechanismProcurementMethod"),
        **item,
    }


def build_detail_record(query: str, lot_id: str, detail: dict) -> dict:
    return {
        "_input": query,
        "_source": "S1-cms-publication-lot-detail-api",
        "_scrapedAt": utc_now_iso(),
        "lotId": lot_id,
        "items": detail.get("items"),
        "milestones": detail.get("milestones"),
    }


def build_error(query: str, error_kind: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
    }
    if detail:
        record["_errorDetail"] = detail
    return record


__all__ = [
    "UnexpectedShape",
    "build_detail_record",
    "build_error",
    "build_list_params",
    "build_list_record",
    "loc",
    "parse_detail_response",
    "parse_list_response",
    "utc_now_iso",
    "DETAIL_URL",
    "LIST_URL",
    "PAGE_SIZE",
]
