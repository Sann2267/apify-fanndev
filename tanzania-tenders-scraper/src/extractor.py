"""Record shaping for NeST's OCDS ("Open Contracting Data Standard") JSON API.

The API is already structured, self-describing JSON -- there is no HTML to
parse, so this module does NOT reshape the upstream data beyond the
project's raw-passthrough convention: the exact `ocid` / `compiledRelease` /
`releases` object returned by NeST is spread onto the output record
untouched (nested `tender`/`awards`/`contracts`/`parties` objects and all),
alongside a handful of convenience top-level fields pulled up for the
Console's table view. A record missing the two fields this actor actually
relies on (`ocid`, `compiledRelease`) raises UnexpectedShape rather than
being silently dropped or mis-mapped -- see CRAWLING_METHOD.md.
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(d, *path):
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def validate_record_item(item: dict, context: str) -> dict:
    if not isinstance(item, dict) or "ocid" not in item or "compiledRelease" not in item:
        raise UnexpectedShape(
            f"[{context}] record item missing 'ocid'/'compiledRelease' -- keys seen: "
            f"{list(item.keys()) if isinstance(item, dict) else type(item)} -- "
            "upstream API shape has likely changed"
        )
    return item


def _summary_fields(cr: dict) -> dict:
    """Pulls a handful of commonly-wanted fields up to the top level for
    readability in the Console table -- purely additive, the full nested
    `compiledRelease` is still included untouched on the output record."""
    tender = cr.get("tender") or {}
    buyer = cr.get("buyer") or {}
    procuring_entity = tender.get("procuringEntity") or {}
    tender_period = tender.get("tenderPeriod") or {}
    awards = cr.get("awards") or []
    contracts = cr.get("contracts") or []

    total_award_amount = None
    award_currency = None
    for a in awards:
        value = (a or {}).get("value") or {}
        amount = value.get("amount")
        if isinstance(amount, (int, float)):
            total_award_amount = (total_award_amount or 0) + amount
            award_currency = award_currency or value.get("currency")

    return {
        "tenderId": tender.get("id"),
        "tenderTitle": tender.get("title") or tender.get("description"),
        "tenderStatus": tender.get("status"),
        "procurementMethod": tender.get("procurementMethod"),
        "procurementMethodDetails": tender.get("procurementMethodDetails"),
        "buyerName": buyer.get("name"),
        "procuringEntityName": procuring_entity.get("name"),
        "tenderPeriodStartDate": tender_period.get("startDate"),
        "tenderPeriodEndDate": tender_period.get("endDate"),
        "recordDate": cr.get("date"),
        "tags": cr.get("tag"),
        "awardsCount": len(awards),
        "contractsCount": len(contracts),
        "totalAwardAmount": total_award_amount,
        "awardCurrency": award_currency,
    }


def build_list_record(item: dict, since_param: str) -> dict:
    item = validate_record_item(item, f"list since={since_param}")
    cr = item["compiledRelease"]
    return {
        "_input": f"list:since={since_param}",
        "_source": "S1-records-list",
        "_scrapedAt": utc_now_iso(),
        **_summary_fields(cr),
        "ocid": item["ocid"],
        "compiledRelease": cr,
        "releases": item.get("releases"),
    }


def build_detail_record(ocid: str, item: dict) -> dict:
    item = validate_record_item(item, f"detail ocid={ocid}")
    cr = item["compiledRelease"]
    return {
        "_input": ocid,
        "_source": "S1-records-detail",
        "_scrapedAt": utc_now_iso(),
        **_summary_fields(cr),
        "ocid": item["ocid"],
        "compiledRelease": cr,
        "releases": item.get("releases"),
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
