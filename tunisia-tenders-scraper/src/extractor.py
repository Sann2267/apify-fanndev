"""Record shaping for TUNEPS's public tender ("Appel d'offres") JSON API.

The API already returns flat, self-describing JSON objects -- there is no
HTML to parse and no deeply nested structure to summarize. Per the project's
raw-passthrough convention, every field TUNEPS returns for a record is
spread onto the output item verbatim (list rows are a sparse ~10-field
summary; detail records are a rich ~90-field object including trilingual
Fr/Ar/En labels for every coded value). A record missing the one field this
actor actually relies on for identity (`epBidMasterId`) raises
UnexpectedShape rather than being silently dropped -- see CRAWLING_METHOD.md.
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_bid_item(item: dict, context: str) -> dict:
    if not isinstance(item, dict) or "epBidMasterId" not in item:
        raise UnexpectedShape(
            f"[{context}] tender item missing 'epBidMasterId' -- keys seen: "
            f"{list(item.keys()) if isinstance(item, dict) else type(item)} -- "
            "upstream API shape has likely changed"
        )
    return item


def build_list_record(item: dict, context: str) -> dict:
    item = validate_bid_item(item, context)
    return {
        "_input": context,
        "_source": "S1-portail-bid-master-list",
        "_scrapedAt": utc_now_iso(),
        **item,
    }


def build_detail_record(bid_id: str, body: dict) -> dict:
    payload = body.get("payload") if isinstance(body, dict) else None
    payload = validate_bid_item(payload, f"detail bidId={bid_id}")
    return {
        "_input": bid_id,
        "_source": "S1-portail-bid-master-detail",
        "_scrapedAt": utc_now_iso(),
        **payload,
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
