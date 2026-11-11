"""Record shaping for NOCOPO.

Two upstream shapes feed this actor:

1. `PublishedRecordHandler.ashx` (list mode) -- a legacy (pre-1.10) jQuery
   DataTables server-side listing endpoint. Each row is a raw internal
   database record with roughly 250 columns, almost all null/zero/
   placeholder ("0001-01-01") internal workflow-tracking fields never meant
   for external consumption (the handler ignores the requested column list
   and always returns the full row). This actor deliberately keeps only the
   handful of columns NOCOPO's own "Open Data" page renders in its visible
   table -- ID, OCID code, procuring entity, project title, date published,
   package number, lot number, budget year -- rather than dumping ~250
   mostly-empty legacy fields. See CRAWLING_METHOD.md.

2. `ocdsjson.ashx` (detail mode) -- returns a small zip containing one
   genuine OCDS (Open Contracting Data Standard) release package for a
   single ocid: a `releases` array (each entry a dated snapshot tagged
   planning/tender/award/contract/implementation/...) plus `uri`/`version`/
   `publishedDate`/`publisher`/`license`/`publicationPolicy`. This is
   passed through verbatim; the only addition is a lightweight same-actor
   fold across the `releases` array into flat summary fields for the
   Console table. NOCOPO's API has no server-side "compiled record" view
   the way Tanzania's NeST does, so this merge is this actor's own -- not
   an upstream OCDS "compiled release" -- and is documented as such.
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_list_record(row: dict, search: str) -> dict:
    if not isinstance(row, dict) or "MDA_Code" not in row or "ID" not in row:
        raise UnexpectedShape(
            f"[list search={search!r}] row missing 'ID'/'MDA_Code' -- keys seen: "
            f"{list(row.keys()) if isinstance(row, dict) else type(row)} -- "
            "upstream table shape has likely changed"
        )
    return {
        "_input": f"list:search={search}" if search else "list",
        "_source": "S1-published-record-handler",
        "_scrapedAt": utc_now_iso(),
        "id": row.get("ID"),
        "ocid": row.get("MDA_Code"),
        "procuringEntity": row.get("MDA_NAME_ONLY"),
        "projectTitle": row.get("pi_Project_Title"),
        "datePublished": row.get("DatePublished"),
        "packageNumber": row.get("pi_Package_Number"),
        "lotNumber": row.get("pi_Lot_Number"),
        "budgetYear": row.get("pb_BudgetYear"),
    }


def _merge_releases(releases: list) -> dict:
    """This actor's own lightweight fold across the raw `releases` array, in
    ascending date order, keeping the latest non-null value seen for each
    field of interest. NOT an OCDS-spec "compiled release" -- see module
    docstring."""

    def _date_key(rel):
        return rel.get("date") or ""

    ordered = sorted((r for r in releases if isinstance(r, dict)), key=_date_key)

    tender_id = tender_title = tender_status = procurement_method = None
    buyer_name = None
    budget_amount = budget_currency = None
    all_awards: list = []
    all_contracts: list = []
    tags: set = set()

    for rel in ordered:
        tags.update(rel.get("tag") or [])

        buyer = rel.get("buyer") or {}
        if buyer.get("name"):
            buyer_name = buyer["name"]

        planning = rel.get("planning") or {}
        budget_amount_obj = (planning.get("budget") or {}).get("amount") or {}
        if budget_amount_obj.get("amount") is not None:
            budget_amount = budget_amount_obj.get("amount")
            budget_currency = budget_amount_obj.get("currency")

        tender = rel.get("tender") or {}
        if tender.get("id"):
            tender_id = tender["id"]
        if tender.get("title") or tender.get("description"):
            tender_title = tender.get("title") or tender.get("description")
        if tender.get("status"):
            tender_status = tender["status"]
        if tender.get("procurementMethod"):
            procurement_method = tender["procurementMethod"]

        if rel.get("awards"):
            all_awards.extend(rel["awards"])
        if rel.get("contracts"):
            all_contracts.extend(rel["contracts"])

    total_award_amount = None
    award_currency = None
    for a in all_awards:
        value = (a or {}).get("value") or {}
        amount = value.get("amount")
        if isinstance(amount, (int, float)):
            total_award_amount = (total_award_amount or 0) + amount
            award_currency = award_currency or value.get("currency")

    return {
        "tenderId": tender_id,
        "tenderTitle": tender_title,
        "tenderStatus": tender_status,
        "procurementMethod": procurement_method,
        "buyerName": buyer_name,
        "budgetAmount": budget_amount,
        "budgetCurrency": budget_currency,
        "tags": sorted(tags),
        "awardsCount": len(all_awards),
        "contractsCount": len(all_contracts),
        "totalAwardAmount": total_award_amount,
        "awardCurrency": award_currency,
        "latestReleaseDate": ordered[-1].get("date") if ordered else None,
    }


def build_detail_record(ocid: str, data: dict) -> dict:
    releases = data.get("releases")
    if not isinstance(releases, list) or not releases:
        raise UnexpectedShape(
            f"[detail ocid={ocid}] response missing a non-empty 'releases' list -- "
            f"keys seen: {list(data.keys()) if isinstance(data, dict) else type(data)} -- "
            "upstream API shape has likely changed"
        )
    return {
        "_input": ocid,
        "_source": "S1-ocdsjson-detail",
        "_scrapedAt": utc_now_iso(),
        **_merge_releases(releases),
        "ocid": ocid,
        "releases": releases,
        "publisher": data.get("publisher"),
        "publishedDate": data.get("publishedDate"),
        "license": data.get("license"),
        "publicationPolicy": data.get("publicationPolicy"),
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
