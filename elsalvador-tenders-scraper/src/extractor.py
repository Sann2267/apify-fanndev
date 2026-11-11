"""Raw-passthrough record builders for COMPRASAL's public JSON API.

There is no HTML to parse -- every endpoint here already returns structured
JSON (see `constants.py` for the full recon writeup), so this module's job is
just: validate the shape isn't emptier/different than expected, then wrap it
in the portfolio's standard `_input`/`_source`/`_scrapedAt` envelope with
minimal renaming (raw passthrough of the upstream field names, per
`.ai/CLAUDE.md` principle 5).
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream response shape changed in a way that can't be interpreted.
    Investigate before the next run -- do not silently emit a partial/empty
    record."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# open (currently active/available) processes
# ---------------------------------------------------------------------------


def parse_open_response(payload) -> list[dict]:
    """`GET .../procesos/disponibles` returns a BARE JSON array (not
    `{data: [...]}` like every other endpoint here -- confirmed during
    recon, not a bug to normalize away). Raises `UnexpectedShape` if the
    top-level shape isn't a list at all (e.g. an error object was returned
    instead)."""
    if not isinstance(payload, list):
        raise UnexpectedShape(f"expected a bare JSON array from /procesos/disponibles, got {type(payload).__name__}")
    return payload


def build_open_record(row: dict, filters: dict) -> dict:
    return {
        "_input": filters,
        "_source": "S1-comprasal-api-disponibles",
        "_scrapedAt": utc_now_iso(),
        **row,
    }


# ---------------------------------------------------------------------------
# awarded / historical processes (with beneficiary data)
# ---------------------------------------------------------------------------


def parse_awarded_response(payload) -> list[dict]:
    """`GET .../procesos/publicos` returns `{"data": [...], "message": "..."}`.
    Raises `UnexpectedShape` if `data` is missing entirely (a real shape
    change) -- an empty `data: []` list is a legitimate "ran out of pages"
    signal, not an error, and is returned as `[]` here."""
    if not isinstance(payload, dict) or "data" not in payload:
        raise UnexpectedShape(f"expected {{'data': [...]}} from /procesos/publicos, got {payload!r:.200}")
    data = payload["data"]
    if not isinstance(data, list):
        raise UnexpectedShape(f"'data' field from /procesos/publicos was not a list: {type(data).__name__}")
    return data


def build_awarded_record(row: dict, filters: dict) -> dict:
    return {
        "_input": filters,
        "_source": "S1-comprasal-api-publicos",
        "_scrapedAt": utc_now_iso(),
        **row,
    }


# ---------------------------------------------------------------------------
# detail (single process)
# ---------------------------------------------------------------------------


def parse_detail_response(payload) -> dict:
    """`GET .../detalle/procesos/publicos/<id>` returns `{"data": {...}}`.
    Raises `UnexpectedShape` if `data` is missing or not an object."""
    if not isinstance(payload, dict) or "data" not in payload:
        raise UnexpectedShape(f"expected {{'data': {{...}}}} from detail endpoint, got {payload!r:.200}")
    data = payload["data"]
    if not isinstance(data, dict):
        raise UnexpectedShape(f"'data' field from detail endpoint was not an object: {type(data).__name__}")
    return data


def build_detail_record(process_id, detail: dict) -> dict:
    return {
        "_input": process_id,
        "_source": "S1-comprasal-api-detalle",
        "_scrapedAt": utc_now_iso(),
        **detail,
    }


# ---------------------------------------------------------------------------
# institutions catalog (used to resolve a name substring -> numeric id, for
# `open` mode's real `institucion=<id>` server-side filter)
# ---------------------------------------------------------------------------


def parse_institutions_response(payload) -> list[dict]:
    if not isinstance(payload, dict) or "data" not in payload:
        raise UnexpectedShape(f"expected {{'data': [...]}} from institutions catalog, got {payload!r:.200}")
    data = payload["data"]
    if not isinstance(data, list):
        raise UnexpectedShape(f"'data' field from institutions catalog was not a list: {type(data).__name__}")
    return data


def resolve_institution_id(institutions: list[dict], query: str) -> int | None:
    """Case-insensitive substring match of `query` against the institution
    catalog's `nombre` field. Returns the first match's numeric `id`, or
    `None` if nothing matched (caller falls back to no filter -- a
    usability nicety, not a hard failure, mirroring the analogous resolver
    in `honduras-tenders-scraper`)."""
    needle = (query or "").strip().lower()
    if not needle:
        return None
    for inst in institutions:
        name = inst.get("nombre") or ""
        if needle in name.lower():
            return inst.get("id")
    return None


# ---------------------------------------------------------------------------
# error records
# ---------------------------------------------------------------------------


def build_error_record(input_value, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
