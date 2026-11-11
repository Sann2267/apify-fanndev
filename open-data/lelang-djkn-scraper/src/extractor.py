"""Record shaping -- raw passthrough of DJKN's own JSON shape plus the
portfolio-standard envelope tags.

Per .ai/conventions/dataset-envelope.md, upstream field names are kept
verbatim in Indonesian (`namaLotLelang`, `nilaiLimit`, `uangJaminan`,
`tglMulaiLelang`, ...) and nested structures (`content.barangs`,
`photos`) are kept intact rather than exploded into separate rows.

Two derived conveniences are added on top (never replacing the originals):

* `_namaLotLelangText` -- `namaLotLelang` arrives with raw HTML in it
  (upstream literally stores "30131 m<sup>2</sup>"), which breaks CSV/Excel
  consumers. A tag-strip + entity-unescape of the same string is added
  alongside the untouched original.
* `_lotUrl` -- the public lelang.go.id page for the lot, so a dataset row
  links back to something a human can open. The pattern
  `/{unitKerjaId}/detail-auction/{lotLelangId}` was taken from the SPA's own
  router table in the JS bundle (`path: ":idKpknl/detail-auction/:lotId"`),
  NOT inferred from response codes: lelang.go.id is a client-side-routed SPA
  that answers **any** path with the same ~2.9 KB shell and a 200, so a
  wrong URL is indistinguishable from a right one over HTTP.
"""

import html
import re
from datetime import datetime, timezone

_TAG_RE = re.compile(r"<[^>]+>")
# Any 8-4-4-4-12 hex UUID, wherever it sits in a pasted URL or a bare ID.
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)

LOT_URL_TEMPLATE = "https://lelang.go.id/{office_id}/detail-auction/{lot_id}"


def extract_lot_id(raw: str) -> str:
    """Accepts a bare UUID, or any lelang.go.id URL containing one, and
    returns just the UUID the `/landing-page/info/{id}` endpoint expects."""
    m = _UUID_RE.search(raw or "")
    return m.group(0) if m else ""


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return html.unescape(_TAG_RE.sub("", value)).strip()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def wrap(item: dict, input_value: str, source: str = "S1-api", record_type: str | None = None) -> dict:
    record = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
    }
    if record_type:
        record["recordType"] = record_type

    name = item.get("namaLotLelang")
    if isinstance(name, str):
        record["_namaLotLelangText"] = clean_text(name)
    lot_id = item.get("lotLelangId") or item.get("id")
    office_id = item.get("unitKerjaId")
    if lot_id and office_id:
        record["_lotUrl"] = LOT_URL_TEMPLATE.format(office_id=office_id, lot_id=lot_id)

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
