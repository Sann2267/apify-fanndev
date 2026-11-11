"""Record shaping for SERCOP's Contrataciones Abiertas Ecuador OCDS API.

Two upstream shapes feed this actor:

1. `search_ocds` (list mode) -- a purpose-built public search API, not an
   internal admin grid reused as-is (contrast with Nigeria's NOCOPO). Each
   row is already a small, clean summary: id, ocid, date, buyer id/name,
   title, description, year, internal_type (the Spanish-language procurement
   modality, e.g. "Licitacion", "Subasta Inversa Electronica"), and
   single_provider (populated only for direct-award/"Ínfima Cuantia"-style
   processes with one named contractor already known at publish time).

2. `record` (detail mode) -- a genuine OCDS *release package* for a single
   ocid: `uri`/`license`/`version`/`publisher`/`extensions`/`publishedDate`/
   `publicationPolicy` plus a `releases` array, one dated snapshot per tag
   (planning/tender/award/contract/...). NOTE: SERCOP's own API docs page
   shows this nested one level deeper, under a top-level `records` array
   (an OCDS "record package" shape) -- the live response confirmed during
   this actor's build has `releases` directly at the top level instead (no
   `records` wrapper at all). This actor follows the live shape; see
   CRAWLING_METHOD.md. Passed through verbatim; the only addition is a
   lightweight same-actor fold across `releases` into flat summary fields
   for the Console table, exactly as this portfolio's other OCDS-based
   tender actors (e.g. Nigeria NOCOPO) already do -- SERCOP's API has no
   server-side "compiled record" view either.
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_list_record(row: dict, year: int, search: str) -> dict:
    if not isinstance(row, dict) or "ocid" not in row:
        raise UnexpectedShape(
            f"[list year={year} search={search!r}] row missing 'ocid' -- keys seen: "
            f"{list(row.keys()) if isinstance(row, dict) else type(row)} -- "
            "upstream search_ocds shape has likely changed"
        )
    return {
        "_input": f"list:year={year}:search={search}",
        "_source": "S1-search-ocds",
        "_scrapedAt": utc_now_iso(),
        "id": row.get("id"),
        "ocid": row.get("ocid"),
        "date": row.get("date"),
        "buyerId": row.get("buyerId"),
        "buyerName": row.get("buyerName"),
        "title": row.get("title"),
        "description": row.get("description"),
        "year": row.get("year"),
        "internalType": row.get("internal_type"),
        "singleProvider": row.get("single_provider"),
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

    suppliers: list = []
    for a in all_awards:
        for supplier in (a or {}).get("suppliers") or []:
            name = (supplier or {}).get("name")
            if name and name not in suppliers:
                suppliers.append(name)

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
        "suppliers": suppliers,
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
        "_source": "S1-record-ocds",
        "_scrapedAt": utc_now_iso(),
        **_merge_releases(releases),
        "ocid": ocid,
        "releases": releases,
        "uri": data.get("uri"),
        "version": data.get("version"),
        "publisher": data.get("publisher"),
        "extensions": data.get("extensions"),
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
