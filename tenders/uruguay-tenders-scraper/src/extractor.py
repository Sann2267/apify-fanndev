"""Record shaping for ARCE's Uruguay OCDS API.

Two upstream shapes feed this actor:

1. RSS feed (list mode) -- one row per *release event* (a tender being
   published, amended, cancelled, or awarded -- ARCE's own `<category>`
   values: tender/tenderUpdate/tenderAmendment/tenderCancellation/award/
   awardUpdate), not one row per purchase. Several events can share the same
   `idCompra` over a purchase's lifecycle. Deliberately thin -- only what the
   feed itself carries (id_compra, release_id, pubDate, link, category) plus
   whatever `fetchDetail` adds. No `ocid` is fabricated for a bare list row;
   it only appears once a real release has actually been fetched and the
   upstream `ocid` field read from it.

2. record + followed release links (detail mode, or list mode with
   fetchDetail=true) -- ARCE's `record` endpoint is a *linked* OCDS record
   package: `records[0].releases` is a list of `{url, date, tag}`
   references, not full content inline (contrast Ecuador SERCOP's compiled
   record, which embeds everything in one response). This actor follows
   every link for one id_compra, then folds the resulting full release
   objects into flat summary fields for the Console table, the same pattern
   this portfolio's other OCDS integrations use (Ecuador SERCOP, Nigeria
   NOCOPO, Tanzania NeST) -- ARCE's API has no server-side "compiled record"
   view either. The raw fetched release objects are kept verbatim under
   `releases`.
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_list_record(item: dict) -> dict:
    if "idCompra" not in item or "releaseId" not in item:
        raise UnexpectedShape(f"RSS item missing idCompra/releaseId -- keys seen: {list(item.keys())}")
    return {
        "_input": f"list:idCompra={item['idCompra']}",
        "_source": "S1-ocds-rss",
        "_scrapedAt": utc_now_iso(),
        "idCompra": item["idCompra"],
        "releaseId": item["releaseId"],
        "eventType": item.get("eventType"),
        "pubDate": item.get("pubDate"),
        "releaseUrl": item.get("releaseUrl"),
        "guid": item.get("guid"),
    }


def _merge_releases(full_releases: list[dict]) -> dict:
    """This actor's own lightweight fold across the fetched full release
    objects, in ascending date order, keeping the latest non-null value seen
    for each field of interest. NOT an OCDS-spec "compiled release" -- see
    module docstring."""

    def _date_key(rel):
        return rel.get("date") or ""

    ordered = sorted((r for r in full_releases if isinstance(r, dict)), key=_date_key)

    ocid = None
    buyer_name = buyer_id = None
    tender_id = tender_title = tender_status = procurement_method = procurement_method_details = None
    tender_start = tender_end = None
    all_awards: list = []
    tags: set = set()

    for rel in ordered:
        if rel.get("ocid"):
            ocid = rel["ocid"]
        tags.update(rel.get("tag") or [])

        buyer = rel.get("buyer") or {}
        if buyer.get("name"):
            buyer_name = buyer["name"]
        if buyer.get("id"):
            buyer_id = buyer["id"]

        tender = rel.get("tender") or {}
        if tender.get("id"):
            tender_id = tender["id"]
        if tender.get("title") or tender.get("description"):
            tender_title = tender.get("title") or tender.get("description")
        if tender.get("status"):
            tender_status = tender["status"]
        if tender.get("procurementMethod"):
            procurement_method = tender["procurementMethod"]
        if tender.get("procurementMethodDetails"):
            procurement_method_details = tender["procurementMethodDetails"]
        tender_period = tender.get("tenderPeriod") or {}
        if tender_period.get("startDate"):
            tender_start = tender_period["startDate"]
        if tender_period.get("endDate"):
            tender_end = tender_period["endDate"]

        if rel.get("awards"):
            all_awards.extend(rel["awards"])

    # NOTE: unlike Ecuador SERCOP (award-level `awards[].value.amount`), ARCE's
    # award releases carry price only per line item, under
    # `awards[].items[].unit.value` -- no award-level total. This actor's own
    # `totalAwardAmount` is unit price * quantity, summed across every
    # awarded item on every award release seen -- a same-actor convenience
    # fold, not an upstream-provided total.
    total_award_amount = None
    award_currency = None
    for a in all_awards:
        for item in (a or {}).get("items") or []:
            value = (item.get("unit") or {}).get("value") or {}
            amount = value.get("amount")
            quantity = item.get("quantity")
            if isinstance(amount, (int, float)):
                line_total = amount * quantity if isinstance(quantity, (int, float)) else amount
                total_award_amount = (total_award_amount or 0) + line_total
                award_currency = award_currency or value.get("currency")

    suppliers: list = []
    for a in all_awards:
        for supplier in (a or {}).get("suppliers") or []:
            name = (supplier or {}).get("name")
            if name and name not in suppliers:
                suppliers.append(name)

    return {
        "ocid": ocid,
        "buyerId": buyer_id,
        "buyerName": buyer_name,
        "tenderId": tender_id,
        "tenderTitle": tender_title,
        "tenderStatus": tender_status,
        "procurementMethod": procurement_method,
        "procurementMethodDetails": procurement_method_details,
        "tenderStartDate": tender_start,
        "tenderEndDate": tender_end,
        "tags": sorted(tags),
        "awardsCount": len(all_awards),
        "totalAwardAmount": total_award_amount,
        "awardCurrency": award_currency,
        "suppliers": suppliers,
        "latestReleaseDate": ordered[-1].get("date") if ordered else None,
    }


def build_detail_record(id_compra: int, link_refs: list[dict], full_releases: list[dict]) -> dict:
    if not full_releases:
        raise UnexpectedShape(f"[detail idCompra={id_compra}] no release links could be followed -- record had {len(link_refs)} ref(s)")
    return {
        "_input": str(id_compra),
        "_source": "S1-record-plus-followed-releases",
        "_scrapedAt": utc_now_iso(),
        "idCompra": id_compra,
        **_merge_releases(full_releases),
        "releaseLinks": link_refs,
        "releases": full_releases,
    }


def build_error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
