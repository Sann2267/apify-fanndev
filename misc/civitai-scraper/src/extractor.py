"""Record shaping -- raw passthrough of Civitai's own JSON shape plus the
portfolio-standard envelope tags.

Per .ai/conventions/dataset-envelope.md, upstream field names are kept
verbatim (no renaming) and nested structures (a model's `modelVersions`,
each with its own `files`/`images`) are kept intact rather than exploded
into separate rows -- consistent with how `walmart-product-scraper`
keeps nested `variants` in this portfolio's e-commerce project.
"""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def wrap(item: dict, input_value: str, source: str = "S1-api") -> dict:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        **item,
    }


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
