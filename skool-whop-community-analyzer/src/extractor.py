"""Shared envelope helpers + the MRR-estimate calculation.

Per .ai/conventions/dataset-envelope.md, every record carries
_input/_source/_scrapedAt (and _error/_errorDetail on failures). Upstream
field names are kept verbatim under `raw` rather than renamed; the
top-level `memberCount` / `subscriptionPrice` / `estimatedMonthlyRevenue`
fields are this actor's own derived value-add, not a rename of an
upstream field, so they sit alongside `raw` rather than replacing it.
"""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_error(input_value: str, platform: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "platform": platform,
        "_error": error_kind,
        "_errorDetail": detail,
    }


def estimate_monthly_revenue(member_count: int | None, monthly_price_usd: float | None) -> dict:
    """Rough MRR signal for sponsorship/lead-gen triage -- NOT verified
    revenue. Neither platform publishes actual revenue publicly (Whop's
    real GMV field, if one exists, was not found during recon -- see
    CRAWLING_METHOD.md). This multiplies the community's total member
    count (which includes free-trial/non-paying/free-tier members on
    both platforms) by the disclosed subscription price, so it is a
    plausible upper bound, not a precise figure.
    """
    if member_count is None or monthly_price_usd is None:
        return {
            "estimatedMonthlyRevenue": None,
            "estimatedMonthlyRevenueBasis": "unavailable: member count or price not disclosed",
        }
    return {
        "estimatedMonthlyRevenue": round(member_count * monthly_price_usd, 2),
        "estimatedMonthlyRevenueBasis": (
            f"memberCount ({member_count}) x monthly price (${monthly_price_usd:.2f}) -- "
            "upper-bound estimate; memberCount includes free/trial members on both "
            "platforms, so treat this as a triage signal, not verified revenue."
        ),
    }


def wrap(
    input_value: str,
    platform: str,
    source: str,
    raw: dict,
    computed: dict,
) -> dict:
    record = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "platform": platform,
    }
    record.update(computed)
    record["raw"] = raw
    return record
