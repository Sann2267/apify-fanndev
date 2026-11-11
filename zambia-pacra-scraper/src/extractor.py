"""Parse the registrysearch API response into dataset-ready records.

Transport (client.py) and parsing (this file) are kept separate per this
portfolio's convention. Every raw entity dict from the API is passed through
close to verbatim (see conventions/dataset-envelope.md) -- only one derived
convenience field is added (`entityTypeLabel`), and the envelope tags
(`_input`/`_source`/`_scrapedAt`, or `_error`/`_errorDetail` on failure) are
attached on top.
"""

from datetime import datetime, timezone

from src.constants import ENTITY_TYPE_LABELS

SOURCE = "S1-registrysearch-api"


class UnexpectedShape(Exception):
    """Raised when the API returns something that isn't the expected
    JSON array of entity objects, or an entity object is missing a field
    this actor treats as load-bearing (entityID/entityName). Propagates and
    fails the run loudly rather than silently emitting a partial/empty
    record -- see .ai/CLAUDE.md principle #6."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def extract_records(data, query: str) -> list[dict]:
    """`data` is the parsed JSON body of a 200 response from
    /api/v1/Search/registrysearch. Returns one record per matching entity,
    or a single zero-match summary record if the search had no hits (not an
    error -- a valid, successful search outcome, so no `_error` tag)."""
    if not isinstance(data, list):
        raise UnexpectedShape(f"Expected a JSON array, got {type(data).__name__}: {data!r}"[:500])

    scraped_at = _now()

    if not data:
        return [
            {
                "_input": query,
                "_source": SOURCE,
                "_scrapedAt": scraped_at,
                "_matchCount": 0,
            }
        ]

    records = []
    for i, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise UnexpectedShape(f"Result item {i} is not an object: {raw!r}"[:500])
        if not raw.get("entityID") or not raw.get("entityName"):
            raise UnexpectedShape(
                f"Result item {i} missing entityID/entityName (schema drift?): {raw!r}"[:500]
            )

        entity_type_id = raw.get("entityTypeId")
        records.append(
            {
                # Raw passthrough -- every field the API returned, unrenamed.
                **raw,
                # One derived convenience field, kept separate from the raw
                # fields above (never overwrites an upstream key).
                "entityTypeLabel": ENTITY_TYPE_LABELS.get(
                    entity_type_id, f"Unknown Type {entity_type_id}"
                ),
                # Envelope tags.
                "_input": query,
                "_source": SOURCE,
                "_scrapedAt": scraped_at,
                "_matchCount": len(data),
            }
        )
    return records


def extract_error(query: str, error_kind: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_source": "none",
        "_scrapedAt": _now(),
        "_error": error_kind,
    }
    if detail:
        record["_errorDetail"] = detail
    return record
