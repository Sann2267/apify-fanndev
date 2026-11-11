"""Keyword harvesting, expansion and competition measurement."""

import logging
from datetime import datetime, timezone
from urllib.parse import quote

from src.constants import (
    ALPHABET,
    AUTOCOMPLETE_API,
    COMPETITION_BANDS,
    COMPETITION_TOP,
    CURATED_API,
    DIGITS,
    ORIGIN,
    REFINE_API,
    SEARCH_API,
    SEARCH_URL,
    SOURCE_AUTOCOMPLETE,
    SOURCE_CURATED,
    SOURCE_EXPANSION,
    SOURCE_RELATED,
    SOURCE_TRENDING,
    TRENDING_API,
)

logger = logging.getLogger(__name__)


class InvalidInput(ValueError):
    """The input could not be used."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def search_url(keyword: str) -> str:
    return SEARCH_URL.format(keyword=quote(keyword))


def competition_level(count) -> str | None:
    """Readability band over the measured product count."""
    if not isinstance(count, (int, float)):
        return None
    for threshold, label in COMPETITION_BANDS:
        if count < threshold:
            return label
    return COMPETITION_TOP


def expansion_prefixes(seed: str, mode: str) -> list[str]:
    """Prefixes to query for one seed.

    The bare seed returns only a handful of suggestions; appending a letter
    pulls a different slice of Blibli's suggestion index each time, which is
    what turns 6 suggestions into 60+.
    """
    prefixes = [seed]
    if mode in ("alphabet", "alphanumeric", "full"):
        prefixes += [f"{seed} {c}" for c in ALPHABET]
    if mode in ("alphanumeric", "full"):
        prefixes += [f"{seed} {c}" for c in DIGITS]
    return prefixes


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

async def fetch_suggestions(client, prefix: str) -> list[str]:
    """Autocomplete terms for one prefix, in Blibli's own order."""
    payload = await client.get_json(
        AUTOCOMPLETE_API, params={"searchTermPrefix": prefix}, referer="/"
    )
    data = payload.get("data") or {}
    return [
        s["term"] for s in (data.get("suggestions") or [])
        if isinstance(s, dict) and s.get("term")
    ]


async def fetch_related(client, keyword: str) -> list[str]:
    """"Refine your search" terms for a keyword."""
    try:
        payload = await client.get_json(
            REFINE_API, params={"searchTerm": keyword}, referer="/"
        )
    except Exception as exc:  # noqa: BLE001 - one source failing is not fatal
        logger.warning("Related terms failed for %r: %s", keyword, exc)
        return []
    data = payload.get("data") or {}
    return [
        r["term"] for r in (data.get("refineKeywords") or [])
        if isinstance(r, dict) and r.get("term")
    ]


async def fetch_trending(client) -> list[str]:
    try:
        payload = await client.get_json(TRENDING_API, referer="/")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Trending searches unavailable: %s", exc)
        return []
    content = (payload.get("data") or {}).get("content") or []
    return [c["id"] for c in content if isinstance(c, dict) and c.get("id")]


async def fetch_curated(client) -> list[dict]:
    try:
        payload = await client.get_json(CURATED_API, referer="/")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Curated keywords unavailable: %s", exc)
        return []
    return [c for c in (payload.get("data") or []) if isinstance(c, dict) and c.get("keyword")]


async def measure_competition(client, keyword: str):
    """How many products Blibli returns for this keyword.

    This is the real, measured figure this actor offers in place of the
    search volume Blibli does not publish.
    """
    try:
        payload = await client.get_json(
            SEARCH_API,
            params={
                "searchTerm": keyword, "page": "1", "start": "0", "itemPerPage": "1",
                "channelId": "web", "showFacet": "false", "sort": "0",
            },
            referer="/",
        )
    except Exception as exc:  # noqa: BLE001 - enrichment, never fatal
        logger.warning("Competition lookup failed for %r: %s", keyword, exc)
        return None
    return ((payload.get("data") or {}).get("paging") or {}).get("total_item")


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

def keyword_record(keyword, seed, source, position, prefix=None, extra=None) -> dict:
    words = keyword.split()
    record = {
        "_input": seed,
        "_source": source,
        "_scrapedAt": _now(),
        "keyword": keyword,
        "seedKeyword": seed,
        "source": source,
        "sourcePrefix": prefix,
        # Rank inside Blibli's own autocomplete ordering. An ordinal
        # popularity signal from their relevance model -- NOT a volume.
        "suggestPosition": position,
        "wordCount": len(words),
        "characterCount": len(keyword),
        # A long-tail term is easier to rank for and converts better; 3+
        # words is the usual marketplace-SEO cut-off.
        "isLongTail": len(words) >= 3,
        "containsSeed": seed.lower() in keyword.lower() if seed else None,
        "searchUrl": search_url(keyword),
        "competingProducts": None,
        "competitionLevel": None,
    }
    if extra:
        record.update(extra)
    return record


async def harvest(client, seed: str, mode: str, max_keywords: int):
    """Collect deduped keywords for one seed across autocomplete + related.

    Yields `(keyword, source, position, prefix)` tuples; the caller turns
    them into records and optionally measures competition.
    """
    seen: set[str] = set()
    emitted = 0

    for prefix in expansion_prefixes(seed, mode):
        if max_keywords and emitted >= max_keywords:
            return
        try:
            terms = await fetch_suggestions(client, prefix)
        except Exception as exc:  # noqa: BLE001 - skip a bad prefix, keep going
            logger.warning("Autocomplete failed for %r: %s", prefix, exc)
            continue
        source = SOURCE_AUTOCOMPLETE if prefix == seed else SOURCE_EXPANSION
        for position, term in enumerate(terms, start=1):
            key = term.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            yield term, source, position, (None if prefix == seed else prefix)
            emitted += 1
            if max_keywords and emitted >= max_keywords:
                return

    if mode in ("related", "full"):
        for term in await fetch_related(client, seed):
            key = term.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            yield term, SOURCE_RELATED, None, None
            emitted += 1
            if max_keywords and emitted >= max_keywords:
                return


def trending_record(keyword: str, position: int) -> dict:
    return keyword_record(keyword, "", SOURCE_TRENDING, position)


def curated_record(item: dict, position: int) -> dict:
    record = keyword_record(item["keyword"], "", SOURCE_CURATED, position)
    url = item.get("url")
    if url:
        record["promoUrl"] = url if url.startswith("http") else ORIGIN + url
    return record
