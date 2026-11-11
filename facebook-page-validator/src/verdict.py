"""Turn a parsed page into a validation verdict.

Two questions are answered separately, because they fail independently:

  exists      does this slug resolve to a page at all?
  brandMatch  if the caller said which brand they expected, is this it?

The second one is not decoration. facebook.com/bukalapak does not belong to the
Indonesian marketplace -- it is an app page called "Eoddata beeip.com" with 124
followers. A list of guessed brand slugs is full of these, and a checker that
only answers "exists" would wave every one of them through.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from src.constants import TIER_FULL, TIER_HOLLOW, TIER_REDUCED

# Tokens that carry no brand meaning, so their absence must not count against a
# match ("Kopi Kenangan | South Jakarta" should still match "Kopi Kenangan").
NOISE_TOKENS = {
    "official", "page", "indonesia", "id", "inc", "ltd", "llc", "co", "corp",
    "company", "group", "global", "store", "shop", "the", "and",
}

STATUS_NOT_FOUND = "NOT_FOUND"
STATUS_ACTIVE = "ACTIVE"

MATCH_EXACT = "EXACT"
MATCH_STRONG = "STRONG"
MATCH_WEAK = "WEAK"
MATCH_MISMATCH = "MISMATCH"
MATCH_UNKNOWN = "UNKNOWN"


def normalise(value: str) -> str:
    """Casefold, strip accents and punctuation, collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = re.sub(r"[^\w\s]", " ", stripped.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def tokens(value: str) -> set[str]:
    return {t for t in normalise(value).split() if t and t not in NOISE_TOKENS}


def brand_match(expected: str | None, actual: str | None) -> dict:
    """Compare the brand the caller expected against the page's real name."""
    if not expected or not actual:
        return {"brandMatch": MATCH_UNKNOWN, "brandMatchScore": None}

    want, got = normalise(expected), normalise(actual)
    if want and want == got:
        return {"brandMatch": MATCH_EXACT, "brandMatchScore": 1.0}

    want_tokens, got_tokens = tokens(expected), tokens(actual)
    if not want_tokens:
        return {"brandMatch": MATCH_UNKNOWN, "brandMatchScore": None}

    overlap = want_tokens & got_tokens
    score = round(len(overlap) / len(want_tokens), 3)

    # Substring containment rescues "Nike" inside "Nike Football", which token
    # overlap already catches, but also "Tokopedia" inside "Tokopediacare",
    # which it does not.
    contained = bool(want) and (want in got or got in want)

    if score == 1.0 or contained:
        label = MATCH_STRONG
    elif score >= 0.5:
        label = MATCH_WEAK
    else:
        label = MATCH_MISMATCH
    return {"brandMatch": label, "brandMatchScore": score}


def assess(slug: str, tier: str, parsed: dict, expected_brand: str | None) -> dict:
    """Build the verdict fields for one slug."""
    exists = tier != TIER_HOLLOW
    verdict: dict[str, Any] = {
        "slug": slug,
        "profileUrl": f"https://www.facebook.com/{slug}",
        "exists": exists,
        "status": STATUS_ACTIVE if exists else STATUS_NOT_FOUND,
        "payloadTier": tier,
        # A REDUCED payload carries the header but not the feed, so "0 posts"
        # there is an absence of evidence, not evidence of absence.
        "postsAreTrustworthy": tier == TIER_FULL,
    }

    if not exists:
        verdict.update({
            "name": None,
            "followers": None,
            "expectedBrand": expected_brand,
            "brandMatch": MATCH_UNKNOWN,
            "brandMatchScore": None,
        })
        return verdict

    verdict["expectedBrand"] = expected_brand
    verdict.update(brand_match(expected_brand, parsed.get("name")))
    return verdict


def summarise(rows: list[dict]) -> dict:
    """Roll the run up into the counts a list-cleaning buyer acts on."""
    total = len(rows)
    existing = [r for r in rows if r.get("exists")]
    checked = [r for r in rows if r.get("brandMatch") not in (None, MATCH_UNKNOWN)]
    mismatched = [r for r in checked if r["brandMatch"] == MATCH_MISMATCH]
    weak = [r for r in checked if r["brandMatch"] == MATCH_WEAK]
    return {
        "slugsChecked": total,
        "existing": len(existing),
        "notFound": total - len(existing),
        "brandChecked": len(checked),
        "brandMismatch": len(mismatched),
        "brandWeakMatch": len(weak),
        "mismatchedSlugs": [r["slug"] for r in mismatched][:50],
        "reducedPayloads": sum(1 for r in existing if r.get("payloadTier") == TIER_REDUCED),
        "fullPayloads": sum(1 for r in existing if r.get("payloadTier") == TIER_FULL),
    }


def matches_filters(row: dict, filters: dict) -> bool:
    if filters.get("onlyExisting") and not row.get("exists"):
        return False
    if filters.get("onlyNotFound") and row.get("exists"):
        return False
    if filters.get("onlyBrandMismatch") and row.get("brandMatch") not in (
        MATCH_MISMATCH, MATCH_WEAK
    ):
        return False
    minimum = filters.get("minFollowers")
    if minimum is not None:
        followers = row.get("followers")
        if followers is None or followers < minimum:
            return False
    return True
