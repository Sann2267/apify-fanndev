"""Bulk Email Verifier -- Apify actor entry point.

Pipeline per address: parse -> classify -> MX lookup -> optional SMTP probe
-> verdict. Each stage is cheap and can only narrow the answer, so an address
that fails syntax never costs a DNS query and a domain with no MX never costs
an SMTP session.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from apify import Actor

from src.dnsmx import MxResolver
from src.exporters import BUILDERS
from src.scoring import score_record, summarise
from src.smtpcheck import SmtpProbe
from src.syntax import parse
from src.input_errors import input_error

MAX_EMAILS = 100_000


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_emails(actor_input: dict) -> tuple[list[str], int]:
    """Collect addresses from every accepted input shape, de-duplicated.

    Returns (addresses, duplicates_removed). A list exported from a CRM is
    usually 5-15% duplicates, and charging twice for the same mailbox is the
    fastest way to lose a buyer.
    """
    raw: list[str] = []
    for item in actor_input.get("emails") or []:
        raw.append(str(item))

    blob = actor_input.get("emailText") or ""
    if blob:
        for chunk in str(blob).replace(";", "\n").replace(",", "\n").split("\n"):
            if chunk.strip():
                raw.append(chunk.strip())

    seen: set[str] = set()
    ordered: list[str] = []
    duplicates = 0
    for value in raw:
        key = value.strip().lower()
        if not key:
            continue
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        ordered.append(value.strip())
    return ordered, duplicates


async def verify_one(address: str, resolver: MxResolver, probe: SmtpProbe | None,
                     semaphore: asyncio.Semaphore, treat_role_as_risky: bool,
                     include_mx_records: bool) -> dict:
    async with semaphore:
        started = time.perf_counter()
        parsed = parse(address)

        dns_result: dict = {"domainStatus": None, "mxRecords": [], "mxHost": None,
                            "disposableMx": False, "dnsError": None}
        smtp_result: dict = {"smtpChecked": False, "smtpDeliverable": None, "smtpCode": None,
                             "smtpMessage": None, "smtpStage": "skipped_disabled",
                             "isCatchAll": None}

        if parsed["syntaxValid"] and parsed["domain"]:
            dns_result = await resolver.lookup(parsed["domain"])
            if probe is not None and dns_result.get("mxHost"):
                smtp_result = await probe.check(
                    parsed["normalizedEmail"] or parsed["email"],
                    parsed["domain"],
                    dns_result["mxHost"],
                )

        verdict = score_record(parsed, dns_result, smtp_result, treat_role_as_risky)

        record = {
            "_input": address,
            "_source": "mx+smtp" if smtp_result.get("smtpChecked") else "mx-only",
            "_scrapedAt": utc_now_iso(),
            "recordType": "EMAIL",
            **parsed,
            **verdict,
            "domainStatus": dns_result.get("domainStatus"),
            "mxHost": dns_result.get("mxHost"),
            "implicitMx": dns_result.get("implicitMx", False),
            "dnsError": dns_result.get("dnsError"),
            **smtp_result,
            "checkDurationMs": int((time.perf_counter() - started) * 1000),
        }
        if include_mx_records:
            record["mxRecords"] = dns_result.get("mxRecords") or []
        return record


def keep(record: dict, wanted: list[str], only_safe: bool) -> bool:
    if only_safe and not record.get("safeToSend"):
        return False
    if wanted and record.get("status") not in wanted:
        return False
    return True


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        emails, duplicates = read_emails(actor_input)
        if not emails:
            raise input_error(
                "No addresses to verify. Supply `emails` as a list, or paste a list "
                "into `emailText` (one per line, or comma/semicolon separated)."
            )
        if len(emails) > MAX_EMAILS:
            Actor.log.warning(
                f"{len(emails):,} addresses supplied; verifying the first {MAX_EMAILS:,}."
            )
            emails = emails[:MAX_EMAILS]

        verify_smtp = bool(actor_input.get("verifySmtp", True))
        detect_catch_all = bool(actor_input.get("detectCatchAll", True))
        treat_role_as_risky = bool(actor_input.get("treatRoleAsRisky", True))
        include_mx_records = bool(actor_input.get("includeMxRecords", True))
        only_safe = bool(actor_input.get("onlySafeToSend", False))
        wanted = actor_input.get("onlyStatuses") or []
        emit_summary = bool(actor_input.get("emitSummary", True))
        export_formats = actor_input.get("exportFormats") or []
        concurrency = max(1, min(int(actor_input.get("concurrency", 20)), 100))
        dns_timeout = float(actor_input.get("dnsTimeoutSeconds", 8))
        smtp_timeout = float(actor_input.get("smtpTimeoutSeconds", 12))
        helo = str(actor_input.get("heloHostname") or "mail.example.com").strip()
        mail_from = str(actor_input.get("mailFromAddress") or "verify@example.com").strip()

        resolver = MxResolver(timeout=dns_timeout)

        # Port 25 is blocked outbound on the platform, so the only possible
        # route to a mail server is an HTTP proxy that allows CONNECT to a
        # non-443 port. Off by default: when the proxy refuses, every address
        # pays a tunnel attempt to learn what one probe already established.
        proxy_input = actor_input.get("proxyConfiguration") or {}
        smtp_proxy_url: str | None = None
        if verify_smtp and proxy_input.get("useApifyProxy"):
            try:
                configuration = await Actor.create_proxy_configuration(
                    groups=proxy_input.get("apifyProxyGroups") or None,
                    country_code=proxy_input.get("apifyProxyCountry") or None,
                )
                if configuration:
                    smtp_proxy_url = await configuration.new_url()
                    Actor.log.info("Attempting SMTP through the Apify proxy (CONNECT tunnel).")
            except Exception as exc:
                Actor.log.warning(f"Proxy unavailable ({exc}); trying SMTP directly instead.")

        probe: SmtpProbe | None = None
        egress_ok: bool | None = None
        if verify_smtp:
            probe = SmtpProbe(timeout=smtp_timeout, helo=helo, mail_from=mail_from,
                              detect_catch_all=detect_catch_all, log=Actor.log,
                              proxy_url=smtp_proxy_url)
            # One connection settles it for the whole run. Without this every
            # address on a port-blocked host would pay a full timeout to learn
            # the same thing.
            egress_ok = await probe.probe_egress()
            if not egress_ok:
                Actor.log.warning(
                    "Port 25 is not reachable from this run, so mailbox-level checks are "
                    "skipped. Syntax, classification and MX results below are unaffected; "
                    "addresses that would have been confirmed come back as 'unknown'."
                )
        else:
            Actor.log.info("SMTP verification disabled by input -- running MX-only.")

        Actor.log.info(
            f"Verifying {len(emails):,} address(es) "
            f"({duplicates:,} duplicate(s) removed), concurrency {concurrency}."
        )

        semaphore = asyncio.Semaphore(concurrency)
        records = await asyncio.gather(*(
            verify_one(address, resolver, probe, semaphore,
                       treat_role_as_risky, include_mx_records)
            for address in emails
        ))

        kept: list[dict] = []
        for record in records:
            if not keep(record, wanted, only_safe):
                continue
            kept.append(record)
            await Actor.push_data(record)

        all_records = list(kept)
        if emit_summary and records:
            summary = summarise(records)
            summary_record = {
                "_input": f"{len(emails)} address(es)",
                "_source": "mx+smtp" if (probe and egress_ok) else "mx-only",
                "_scrapedAt": utc_now_iso(),
                "recordType": "RUN_SUMMARY",
                **summary,
                "duplicatesRemoved": duplicates,
                "domainsResolved": resolver.cached_domains,
                # The operational fact this run establishes about its own host.
                # Worth reading before trusting any 'unknown' verdict above.
                "smtpEnabled": verify_smtp,
                "smtpRoute": probe.route if probe else "none",
                "smtpPortReachable": egress_ok,
                "smtpEgressDetail": probe.egress_detail if probe else "not tested",
                "smtpChecksAttempted": probe.attempted if probe else 0,
                "smtpChecksAnswered": probe.answered if probe else 0,
            }
            await Actor.push_data(summary_record)
            all_records.append(summary_record)
            Actor.log.info(
                f"deliverable={summary['deliverable']} "
                f"undeliverable={summary['undeliverable']} "
                f"risky={summary['risky']} unknown={summary['unknown']} "
                f"(rate {summary['deliverableRate']:.1%})"
            )

        if export_formats and all_records:
            store = await Actor.open_key_value_store()
            for fmt in export_formats:
                spec = BUILDERS.get(fmt)
                if not spec:
                    Actor.log.warning(f"Unknown export format {fmt!r} -- skipped.")
                    continue
                filename, content_type, builder = spec
                payload = builder(all_records)
                if payload is None:
                    Actor.log.warning(f"{fmt}: exporter unavailable -- skipped.")
                    continue
                await store.set_value(filename, payload, content_type=content_type)
                Actor.log.info(f"Exported {filename} ({len(payload):,} bytes)")

        Actor.log.info(f"Finished: {len(kept):,} record(s) written.")
        if records and not kept:
            Actor.log.warning(
                "Every address was filtered out by onlyStatuses / onlySafeToSend -- "
                "the run succeeded, the filters just matched nothing."
            )
