"""Record builders for Fiji ROC's `/BuyInformation/Search` +
`/BuyInformation/GetSearchResults` search flow.

No tree-walking needed here (unlike the Verne/Foster Moore registries in
this portfolio) -- the grid endpoint already returns clean, flat JSON rows.
This module's job is: (1) turn each row into a raw-passthrough record, and
(2) distinguish the two "no data" outcomes the recon uncovered --
genuinely zero matches vs. upstream silently capping an overly broad result
set (see constants.py's docstring, gotcha #2) -- so neither is ever silently
swallowed as an empty/missing row.
"""

from datetime import datetime, timezone

from src.constants import LIKELY_TOO_BROAD_THRESHOLD

BASE_URL = "https://roc.digital.gov.fj"


class NoResultsFound(Exception):
    """The search legitimately matched zero entities (POST search() count
    was 0)."""


class ResultSetTooBroad(Exception):
    """POST search() returned a nonzero count, but GetSearchResults came
    back with an empty grid -- the confirmed upstream cap on very large
    result sets (see constants.py gotcha #2), not a genuine zero-match."""

    def __init__(self, count: int):
        self.count = count
        super().__init__(f"search matched {count} entities but grid returned none (likely capped upstream)")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_search_record(query: str, search_by: str, row: dict) -> dict:
    """Raw-passthrough record for one `Data[]` row from GetSearchResults.
    Drops `FilteredFields` (internal Kendo grid filter metadata, not entity
    data) and `Id` (always observed null). Renames `Url` -> `entityDetailUrl`
    for clarity and prefixes it with the origin so it's directly followable
    (upstream returns it as a bare relative path, e.g.
    `BuyInformation/Application?entityNumber=10658&isAuthChallenged=false`)
    -- note that URL redirects to a ROC Pass login, it is NOT fetched by
    this actor.
    """
    record = {
        "_input": query,
        "_searchBy": search_by,
        "_source": "S1-buyinformation-search",
        "_scrapedAt": utc_now_iso(),
        "EntityName": row.get("EntityName"),
        "LegalElement": row.get("LegalElement"),
        "EntityNumber": row.get("EntityNumber"),
        "Type": row.get("Type"),
        "Status": row.get("Status"),
    }
    url = row.get("Url")
    if url:
        record["entityDetailUrl"] = f"{BASE_URL}/{url}" if not url.startswith("http") else url
    return record


def extract_error(query: str, search_by: str, error: str, detail: str | None = None) -> dict:
    record = {
        "_input": query,
        "_searchBy": search_by,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error,
    }
    if detail:
        record["_errorDetail"] = detail
    return record


def is_likely_too_broad(count: int) -> bool:
    """Heuristic pre-check so callers can warn/cap BEFORE spending a request
    on a grid page that's known (from recon) to come back empty. Not a hard
    guarantee -- the actual failure is confirmed by an empty grid response,
    see main.py."""
    return count >= LIKELY_TOO_BROAD_THRESHOLD
