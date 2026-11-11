"""Dataset envelope and the small set of computed fields each mode adds.

Upstream field names pass through verbatim -- no renaming, no restructuring --
so that a new field Chiliz adds tomorrow appears in the dataset without a code
change. The handful of fields added here are additions, never replacements, and
each one exists because the raw payload makes a common question awkward:

* a poll's result lives in a nested ``answers`` array, so the winner is invisible
  in a flat table view and in every CSV export;
* a fan token's contract address and logo live one and two levels down inside
  ``currencyNetworks`` and ``images``;
* every cross-reference in this API is a bare UUID, so ``partnerName`` on a
  token or a league is the difference between a usable row and a puzzle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SOURCE = "S1-chiliz-acl"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(raw_input: str, record_type: str, payload: dict) -> dict:
    return {
        "_input": raw_input,
        "_source": SOURCE,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
        **payload,
    }


def error_record(raw_input: str, error: str, detail: str) -> dict:
    return {
        "_input": raw_input,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "recordType": "ERROR",
        "_error": error,
        "_errorDetail": detail,
    }


def _number(value: Any) -> float | None:
    """Vote counts and percentages arrive as decimal strings, ints or None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def poll_extras(poll: dict) -> dict:
    """Flatten a poll's result so the winner is visible without opening ``answers``.

    ``totalVoteTokensUsed`` is summed from the answers rather than read from the
    poll's own ``usedTokenCount``: the two agree on settled polls, but on a poll
    that is still open ``usedTokenCount`` is the figure the chain has confirmed
    while the answers carry what has actually been cast, and the leading answer
    should be consistent with the percentages next to it.
    """
    answers = poll.get("answers")
    if not isinstance(answers, list) or not answers:
        return {
            "answerCount": 0,
            "totalVoteTokensUsed": _number(poll.get("usedTokenCount")),
            "leadingAnswer": None,
            "leadingAnswerVotes": None,
            "leadingAnswerPercentage": None,
            "isDisclosed": bool(poll.get("disclosedAt")),
        }

    usable = [a for a in answers if isinstance(a, dict)]
    total = sum(_number(a.get("totalVoteTokensUsed")) or 0.0 for a in usable)
    leader = max(usable, key=lambda a: _number(a.get("totalVoteTokensUsed")) or 0.0)
    # An all-zero poll has no winner, only a tie at nothing.
    has_votes = total > 0

    return {
        "answerCount": len(usable),
        "totalVoteTokensUsed": total,
        "leadingAnswer": leader.get("answer") if has_votes else None,
        "leadingAnswerVotes": _number(leader.get("totalVoteTokensUsed")) if has_votes else None,
        "leadingAnswerPercentage": _number(leader.get("votePercentage")) if has_votes else None,
        "isDisclosed": bool(poll.get("disclosedAt")),
    }


def token_extras(currency: dict, partner_by_currency: dict[str, dict]) -> dict:
    """Surface a fan token's contract address, logo and owning club."""
    networks = currency.get("currencyNetworks")
    network = networks[0] if isinstance(networks, list) and networks else {}
    images = currency.get("images")
    logo = None
    if isinstance(images, list):
        for image in images:
            if isinstance(image, dict) and image.get("url"):
                logo = image["url"]
                break
    partner = partner_by_currency.get(currency.get("id")) or {}
    return {
        "smartContractAddress": (network or {}).get("smartContractAddress"),
        "decimals": (network or {}).get("decimalDetail"),
        "networkCount": len(networks) if isinstance(networks, list) else 0,
        "logoUrl": logo,
        "partnerId": partner.get("id"),
        "partnerName": partner.get("name"),
        "partnerType": partner.get("type"),
    }


def named(row: dict, key: str, lookup: dict[str, dict], field: str, as_key: str) -> dict:
    """Resolve one UUID reference into a human-readable name."""
    target = lookup.get(row.get(key))
    return {as_key: (target or {}).get(field)}
