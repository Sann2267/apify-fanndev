"""Dataset envelope helpers. Raw-passthrough: upstream field shapes are kept
verbatim; only the `_input`/`_source`/`_scrapedAt`/`recordType` meta-fields are
added (see .ai/conventions/dataset-envelope.md)."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(payload: dict, source: str, record_type: str, input_value: str) -> dict:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
        **payload,
    }


def error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
