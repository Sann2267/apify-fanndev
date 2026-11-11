"""Record shaping for VNEPS's "contractor selection" search/detail services.

Both services already return structured JSON -- there is no HTML to parse.
Per the project's raw-passthrough convention, the exact upstream object is
spread onto the output record untouched, alongside a handful of convenience
top-level fields pulled up for the Console's table view. A record missing
the one field this actor actually depends on (`id` for search hits,
`bideContractorInputResultDTO` for detail lookups) raises UnexpectedShape
rather than being silently dropped or mis-mapped -- see CRAWLING_METHOD.md.
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _first_or_none(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def build_list_record(hit: dict, context: str) -> dict:
    if not isinstance(hit, dict) or "id" not in hit:
        raise UnexpectedShape(
            f"[{context}] search hit missing 'id' -- keys seen: "
            f"{list(hit.keys()) if isinstance(hit, dict) else type(hit)} -- "
            "upstream API shape has likely changed"
        )
    bid_name = _first_or_none(hit.get("bidName")) or hit.get("name")
    contractor_name = _first_or_none(hit.get("contractorName"))
    winning_price = _first_or_none(hit.get("bidWinningPrice"))
    bid_price = _first_or_none(hit.get("bidPrice"))
    locations = hit.get("locations") or []
    location_names = [loc.get("provName") for loc in locations if isinstance(loc, dict) and loc.get("provName")]

    return {
        "_input": context,
        "_source": "S1-smart-search",
        "_scrapedAt": utc_now_iso(),
        "titleDisplay": bid_name,
        "recordType": hit.get("type"),
        "stepCode": hit.get("stepCode"),
        "notifyNo": hit.get("notifyNo"),
        "planNo": hit.get("planNo"),
        "procuringEntityName": hit.get("procuringEntityName"),
        "investorName": hit.get("investorName"),
        "provinceNames": location_names or None,
        "publicDate": hit.get("publicDate"),
        "bidCloseDate": hit.get("bidCloseDate"),
        "decisionDate": hit.get("decisionDate"),
        "status": hit.get("status") or hit.get("statusForNotify"),
        "investField": hit.get("investField"),
        "investTotal": hit.get("investTotal"),
        "bidPriceDisplay": bid_price,
        "winningContractorDisplay": contractor_name,
        "bidWinningPriceDisplay": winning_price,
        "inputResultId": hit.get("inputResultId"),
        "raw": hit,
    }


def build_detail_record(input_result_id: str, data: dict) -> dict:
    dto = data.get("bideContractorInputResultDTO") if isinstance(data, dict) else None
    if not isinstance(dto, dict):
        raise UnexpectedShape(
            f"[detail inputResultId={input_result_id}] response missing "
            "'bideContractorInputResultDTO' object -- upstream API shape has "
            "likely changed"
        )
    lot_results = dto.get("lotResultDTO") or []
    all_contractors = []
    for lot in lot_results:
        for c in (lot or {}).get("contractorList") or []:
            if isinstance(c, dict):
                all_contractors.append(c)

    return {
        "_input": input_result_id,
        "_source": "S1-contractor-input-result-detail",
        "_scrapedAt": utc_now_iso(),
        "inputResultId": dto.get("id"),
        "notifyNo": dto.get("notifyNo"),
        "bidNo": dto.get("bidNo"),
        "bidName": dto.get("bidName"),
        "status": dto.get("status"),
        "procuringEntityName": dto.get("procuringEntityName"),
        "investorName": dto.get("investorName"),
        "publicDate": dto.get("publicDate"),
        "decisionNo": dto.get("decisionNo"),
        "decisionDate": dto.get("decisionDate"),
        "decisionAgency": dto.get("decisionAgency"),
        "lotCount": len(lot_results),
        # NOTE: this detail endpoint does not carry the winner's plain legal
        # name -- only its system org code and tax code. The human-readable
        # name (e.g. "CONG TY TNHH...") is only available from a 'list' mode
        # hit's own `contractorName` field for the same record.
        "winningContractorOrgCodes": [c.get("orgCode") for c in all_contractors if c.get("orgCode")] or None,
        "winningContractorTaxCodes": [c.get("taxCode") for c in all_contractors if c.get("taxCode")] or None,
        "winningPrices": [c.get("bidWiningPrice") for c in all_contractors if c.get("bidWiningPrice") is not None]
        or None,
        "fullDetail": data,
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
