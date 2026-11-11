"""Local smoke test -- runs the whole pipeline without the Apify SDK.

    python test_local.py            # syntax + MX only (no port 25 needed)
    python test_local.py --smtp     # also try the mailbox probe

Checks the parts that are cheap to get subtly wrong: alias normalisation,
typo distance, null MX, and that an SMTP timeout never becomes "undeliverable".
"""

from __future__ import annotations

import asyncio
import json
import sys

from src.dnsmx import MxResolver
from src.scoring import score_record, summarise
from src.smtpcheck import SmtpProbe
from src.syntax import parse

CASES = [
    "support@apify.com",
    "Jane Doe <jane.doe+news@gmail.com>",
    "info@shopify.com",
    "someone@mailinator.com",
    "typo@gmial.com",
    "nobody@this-domain-should-not-exist-8x2q7.com",
    "not-an-email",
    "double..dot@example.com",
    "spaced address@example.com",
]

BLANK_SMTP = {"smtpChecked": False, "smtpDeliverable": None, "smtpCode": None,
              "smtpMessage": None, "smtpStage": "skipped_disabled", "isCatchAll": None}


def test_syntax() -> None:
    """Pure-function expectations, no network."""
    cases = [
        ("jane.doe+news@gmail.com", True, "janedoe@gmail.com", True),
        ("Jane+x@googlemail.com", True, "jane@googlemail.com", True),
        ("plain@example.com", True, "plain@example.com", False),
        ("double..dot@example.com", False, None, False),
        ("no-at-sign.com", False, None, False),
        ("spaced address@example.com", False, None, False),
        ("a@b", False, None, False),
    ]
    for raw, valid, normalised, alias in cases:
        got = parse(raw)
        assert got["syntaxValid"] is valid, f"{raw}: syntaxValid {got['syntaxValid']} != {valid}"
        if valid:
            assert got["normalizedEmail"] == normalised, f"{raw}: {got['normalizedEmail']}"
            assert got["isAlias"] is alias, f"{raw}: isAlias {got['isAlias']}"
    assert parse("info@acme.com")["isRoleAccount"] is True
    assert parse("jane@acme.com")["isRoleAccount"] is False
    assert parse("x@gmial.com")["suggestedEmail"] == "x@gmail.com"
    assert parse("x@gmail.com")["suggestedEmail"] is None, "valid domain must not be 'corrected'"
    assert parse("x@mailinator.com")["isDisposable"] is True
    print("syntax: OK")


def test_scoring_never_guesses() -> None:
    """A timeout or blocked port must never read as undeliverable."""
    parsed = parse("jane@acme.com")
    dns_ok = {"domainStatus": "ok", "mxRecords": [{"host": "mx.acme.com", "preference": 10}],
              "mxHost": "mx.acme.com", "disposableMx": False, "dnsError": None}
    timed_out = {**BLANK_SMTP, "smtpChecked": True, "smtpStage": "timeout"}
    assert score_record(parsed, dns_ok, timed_out)["status"] == "unknown"
    blocked = {**BLANK_SMTP, "smtpStage": "skipped_port_blocked"}
    assert score_record(parsed, dns_ok, blocked)["status"] == "unknown"
    rejected = {**BLANK_SMTP, "smtpChecked": True, "smtpDeliverable": False,
                "smtpCode": 550, "smtpStage": "rcpt_to"}
    assert score_record(parsed, dns_ok, rejected)["status"] == "undeliverable"
    accepted = {**BLANK_SMTP, "smtpChecked": True, "smtpDeliverable": True,
                "smtpCode": 250, "smtpStage": "rcpt_to"}
    verdict = score_record(parsed, dns_ok, accepted)
    assert verdict["status"] == "deliverable" and verdict["safeToSend"] is True
    catch_all = {**accepted, "isCatchAll": True}
    assert score_record(parsed, dns_ok, catch_all)["status"] == "risky"
    no_mx = {"domainStatus": "no_mx", "mxRecords": [], "mxHost": None,
             "disposableMx": False, "dnsError": "null_mx"}
    assert score_record(parsed, no_mx, BLANK_SMTP)["status"] == "undeliverable"
    print("scoring: OK")


async def run(use_smtp: bool) -> None:
    resolver = MxResolver()
    probe = None
    if use_smtp:
        probe = SmtpProbe()
        reachable = await probe.probe_egress()
        print(f"port 25 reachable: {reachable} -- {probe.egress_detail}")

    rows = []
    for address in CASES:
        parsed = parse(address)
        dns_result = {"domainStatus": None, "mxRecords": [], "mxHost": None,
                      "disposableMx": False, "dnsError": None}
        smtp_result = dict(BLANK_SMTP)
        if parsed["syntaxValid"]:
            dns_result = await resolver.lookup(parsed["domain"])
            if probe is not None and dns_result.get("mxHost"):
                smtp_result = await probe.check(parsed["normalizedEmail"],
                                                parsed["domain"], dns_result["mxHost"])
        row = {**parsed, **score_record(parsed, dns_result, smtp_result),
               **dns_result, **smtp_result}
        rows.append(row)
        print(f"{row['status']:<14} {row['subStatus']:<20} {address[:44]:<46} "
              f"mx={row.get('mxHost') or '-'}")

    print("\nsummary:")
    print(json.dumps(summarise(rows), indent=2)[:900])


if __name__ == "__main__":
    test_syntax()
    test_scoring_never_guesses()
    asyncio.run(run("--smtp" in sys.argv))
