"""Turn the collected signals into one verdict a buyer can sort on.

Four statuses, chosen so that the two a sender acts on are unambiguous:

    deliverable   -- send it
    undeliverable -- remove it, it will bounce
    risky         -- it may accept the mail and still hurt you (catch-all,
                     disposable, role mailbox)
    unknown       -- we could not establish enough to say; never silently
                     folded into one of the other three

`safeToSend` is the single boolean for the common case, and it is deliberately
conservative: risky and unknown both answer false.
"""

from __future__ import annotations

from src.dnsmx import DOMAIN_ERROR, DOMAIN_NO_MX, DOMAIN_NXDOMAIN, DOMAIN_OK, DOMAIN_TIMEOUT

DELIVERABLE = "deliverable"
UNDELIVERABLE = "undeliverable"
RISKY = "risky"
UNKNOWN = "unknown"


def score_record(parsed: dict, dns_result: dict, smtp_result: dict,
                 treat_role_as_risky: bool = True) -> dict:
    """Return status / subStatus / score / safeToSend / reason for one address."""

    if not parsed["syntaxValid"]:
        return _verdict(UNDELIVERABLE, parsed.get("syntaxError") or "invalid_syntax", 0,
                        f"Address is not a valid mailbox: {parsed.get('syntaxError')}.")

    domain_status = dns_result.get("domainStatus")
    if domain_status == DOMAIN_NXDOMAIN:
        return _verdict(UNDELIVERABLE, "nxdomain", 0,
                        "The domain does not exist, so nothing can be delivered to it.")
    if domain_status == DOMAIN_NO_MX:
        return _verdict(UNDELIVERABLE, "no_mx_record", 2,
                        "The domain exists but accepts no mail (no MX and no usable A record).")
    if domain_status in (DOMAIN_TIMEOUT, DOMAIN_ERROR):
        return _verdict(UNKNOWN, "dns_unavailable", 50,
                        "The DNS lookup failed, which is a fact about this run, not about the address.")

    disposable = parsed["isDisposable"] or dns_result.get("disposableMx")
    smtp_deliverable = smtp_result.get("smtpDeliverable")
    catch_all = smtp_result.get("isCatchAll")

    # An SMTP rejection outranks everything else: the server that owns the
    # mailbox said no.
    if smtp_deliverable is False:
        return _verdict(UNDELIVERABLE, "mailbox_not_found", 0,
                        f"The mail server rejected this recipient (SMTP {smtp_result.get('smtpCode')}).")

    if disposable:
        return _verdict(RISKY, "disposable", 15,
                        "Throwaway mailbox provider -- it may accept mail today and vanish tomorrow.")

    if smtp_deliverable is True:
        if catch_all:
            return _verdict(RISKY, "catch_all", 55,
                            "The domain accepts every address, so acceptance proves nothing about "
                            "this particular mailbox.")
        if parsed["isRoleAccount"] and treat_role_as_risky:
            return _verdict(RISKY, "role_account", 70,
                            "Deliverable, but it is a shared function mailbox -- higher complaint "
                            "risk on cold sends.")
        return _verdict(DELIVERABLE, "mailbox_exists", 98,
                        "The mail server accepted this recipient.")

    # No usable SMTP answer: everything below rests on DNS plus classification.
    if smtp_result.get("smtpStage") in ("skipped_port_blocked", "skipped_disabled"):
        base_reason = "SMTP verification was not performed"
    elif smtp_result.get("smtpChecked"):
        base_reason = f"The mail server gave no usable answer ({smtp_result.get('smtpStage')})"
    else:
        base_reason = "SMTP verification was not performed"

    if parsed["hasTypo"]:
        return _verdict(RISKY, "domain_typo", 30,
                        f"{base_reason}; the domain looks like a typo for "
                        f"{parsed['suggestedEmail'].split('@')[1]}.")
    if parsed["isRoleAccount"] and treat_role_as_risky:
        return _verdict(RISKY, "role_account", 45,
                        f"{base_reason}; this is a shared function mailbox.")
    if domain_status == DOMAIN_OK:
        return _verdict(UNKNOWN, "mx_only", 65,
                        f"{base_reason}. The domain accepts mail, but mailbox existence is unconfirmed.")
    return _verdict(UNKNOWN, "insufficient_signal", 40, base_reason + ".")


def _verdict(status: str, sub_status: str, score: int, reason: str) -> dict:
    return {
        "status": status,
        "subStatus": sub_status,
        "score": score,
        "safeToSend": status == DELIVERABLE,
        "reason": reason,
    }


def summarise(rows: list[dict]) -> dict:
    """Run-level counts. Rates are of the addresses actually verified."""
    total = len(rows)
    by_status: dict[str, int] = {}
    by_sub: dict[str, int] = {}
    for row in rows:
        by_status[row.get("status", UNKNOWN)] = by_status.get(row.get("status", UNKNOWN), 0) + 1
        sub = row.get("subStatus") or "unspecified"
        by_sub[sub] = by_sub.get(sub, 0) + 1
    deliverable = by_status.get(DELIVERABLE, 0)
    return {
        "emailsChecked": total,
        "deliverable": deliverable,
        "undeliverable": by_status.get(UNDELIVERABLE, 0),
        "risky": by_status.get(RISKY, 0),
        "unknown": by_status.get(UNKNOWN, 0),
        "deliverableRate": round(deliverable / total, 4) if total else 0.0,
        "roleAccounts": sum(1 for r in rows if r.get("isRoleAccount")),
        "disposable": sum(1 for r in rows if r.get("isDisposable")),
        "freeProviders": sum(1 for r in rows if r.get("isFreeProvider")),
        "typoSuspects": sum(1 for r in rows if r.get("hasTypo")),
        "catchAllDomains": len({r.get("domain") for r in rows if r.get("isCatchAll")}),
        "statusBreakdown": dict(sorted(by_status.items(), key=lambda kv: -kv[1])),
        "reasonBreakdown": dict(sorted(by_sub.items(), key=lambda kv: -kv[1])),
    }
