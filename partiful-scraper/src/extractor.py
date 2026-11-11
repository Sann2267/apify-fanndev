"""Record shaping -- raw passthrough of Partiful's own Next.js SSR JSON
shape (`__NEXT_DATA__.props.pageProps`) plus the portfolio-standard
envelope tags.

Per .ai/conventions/dataset-envelope.md, upstream field names are kept
verbatim (no renaming). The only fields ever dropped are per-request SSR
tracing noise (`_sentryTraceData`, `_sentryBaggage`, `scriptLoader`) --
these are random per HTTP call, not entity data, the same class of noise
the envelope convention already excludes (`_userAgent`, `_proxyIp`).
"""

import json
import re
from datetime import datetime, timezone

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_HOST_RE = re.compile(r"^(?:https?://)?(?:www\.)?partiful\.com/", re.IGNORECASE)

_NOISE_KEYS = ("_sentryTraceData", "_sentryBaggage", "scriptLoader")


class UnexpectedShape(Exception):
    """Partiful's page markup no longer carries a __NEXT_DATA__ blob, or
    it isn't valid JSON -- the site's SSR shape has changed. Not caught
    by the worker loop; must crash the run per
    .ai/conventions/error-handling.md Category 3."""


def extract_next_data(html: str) -> dict:
    m = _NEXT_DATA_RE.search(html)
    if not m:
        raise UnexpectedShape("__NEXT_DATA__ script tag not found in response body")
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"__NEXT_DATA__ is not valid JSON: {e}") from e


def extract_id(raw: str, path_prefix: str) -> str:
    """Accepts a bare id ("S9m7mAA0avBXnFR6rgf0"), a path
    ("partiful.com/e/S9m7mAA0avBXnFR6rgf0"), or a full URL
    ("https://partiful.com/e/S9m7mAA0avBXnFR6rgf0?rsvp=yes") and returns
    just the id. `path_prefix` is "e" for events or "u" for host
    profiles."""
    s = raw.strip()
    s = _HOST_RE.sub("", s)
    prefix = f"{path_prefix}/"
    if s.lower().startswith(prefix):
        s = s[len(prefix):]
    s = s.split("?")[0].split("#")[0]
    return s.strip("/")


def strip_noise(page_props: dict) -> dict:
    return {k: v for k, v in page_props.items() if k not in _NOISE_KEYS}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def wrap(item: dict, input_value: str, source: str = "S1-nextdata", record_type: str | None = None) -> dict:
    record = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
    }
    if record_type:
        record["recordType"] = record_type
    record.update(item)
    return record


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
