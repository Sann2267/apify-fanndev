"""Local smoke test -- runs the actor's real code paths without the Apify platform.

Usage:
    python test_local.py            # every mode, small caps
    python test_local.py polls      # one mode
"""

from __future__ import annotations

import asyncio
import json
import sys

from src.client import ChilizClient
from src.main import (
    run_fan_tokens,
    run_partners,
    run_polls,
    run_reference,
    run_vote_tokens,
)


class Log:
    def info(self, message):
        print(f"  [info] {message}")

    def warning(self, message):
        print(f"  [warn] {message}")

    def error(self, message):
        print(f"  [err ] {message}")


LOG = Log()


def show(title: str, records: list[dict], fields: list[str]) -> None:
    print(f"\n=== {title}: {len(records)} record(s) ===")
    if not records:
        print("  (empty)")
        return
    for record in records[:3]:
        line = {f: record.get(f) for f in fields}
        print("  " + json.dumps(line, ensure_ascii=True, default=str)[:320])
    keys = sorted(records[0].keys())
    print(f"  keys({len(keys)}): {', '.join(keys)}")


async def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    client = ChilizClient()
    try:
        if which in ("all", "polls"):
            records, errors = await run_polls(
                client,
                {"partners": ["AC Milan"], "pollStatuses": ["closed"], "maxItems": 5},
                LOG,
            )
            show(
                "POLLS (AC Milan, closed)",
                records,
                ["recordType", "partnerName", "question", "status", "type",
                 "leadingAnswer", "leadingAnswerPercentage", "totalVoteTokensUsed"],
            )
            show("POLL ERRORS", errors, ["_input", "_error"])

            records, errors = await run_polls(
                client, {"partners": ["$ACM", "Not A Real Club"], "maxItems": 2}, LOG
            )
            show("POLLS (symbol + bad input)", records, ["partnerName", "question"])
            show("POLL ERRORS", errors, ["_input", "_error", "_errorDetail"])

            records, _ = await run_polls(
                client, {"pollTypes": ["prediction"], "maxItems": 3}, LOG
            )
            show("POLLS (prediction only)", records,
                 ["partnerName", "type", "question", "leadingAnswer", "outcome"])

        if which in ("all", "partners"):
            records = await run_partners(
                client, {"activePartnersOnly": True, "maxItems": 5}, LOG
            )
            show("PARTNERS (active)", records,
                 ["recordType", "name", "tokenSymbol", "type", "status", "mainColour"])

        if which in ("all", "fanTokens"):
            records = await run_fan_tokens(client, LOG)
            show("FAN TOKENS", records,
                 ["recordType", "shortCode", "label", "type", "smartContractAddress",
                  "partnerName", "logoUrl"])

        if which in ("all", "voteTokens"):
            records = await run_vote_tokens(client, LOG)
            show("VOTE TOKENS", records,
                 ["recordType", "tokenSymbol", "tokenName", "supply", "status",
                  "partnerName", "blockchainAddress"])

        if which in ("all", "reference"):
            records = await run_reference(client, LOG)
            show("REFERENCE", records,
                 ["recordType", "name", "sportName", "countryName", "iso2"])
            kinds = {}
            for record in records:
                kinds[record["recordType"]] = kinds.get(record["recordType"], 0) + 1
            print(f"  breakdown: {kinds}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
