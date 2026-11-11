"""Turn a sample of live ads into benchmarks for a niche.

Every number here is computed from ads that are actually running right now, and
every benchmark row carries the `sampleSize` it came from. That matters more
than it sounds: the Ad Library does not publish spend or impressions for
commercial ads, so no honest tool can report CPM, CTR or ROAS from it. What it
*can* report -- and what this actor does -- is what an entire niche is choosing
to say and how long each choice survives.

Longevity is the closest thing to a performance signal that public data allows.
An advertiser keeps paying for a creative that works and stops paying for one
that does not, so "median days on air" per CTA, per format and per copy length
is a revealed preference, not a guess. It is stated that way in the output
rather than dressed up as a conversion metric.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Iterable

# Deliberately small and English/Indonesian-leaning: an aggressive stop list
# hides the words that make ad copy distinctive ("free", "now", "off").
STOPWORDS = {
    "a", "about", "all", "also", "am", "an", "and", "any", "are", "as", "at",
    "be", "been", "but", "by", "can", "do", "does", "for", "from", "get", "had",
    "has", "have", "he", "her", "here", "him", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "just", "me", "more", "most", "my", "no", "not",
    "of", "on", "one", "or", "our", "out", "over", "own", "s", "she", "so",
    "some", "such", "t", "than", "that", "the", "their", "them", "then",
    "there", "these", "they", "this", "to", "too", "up", "us", "very", "was",
    "we", "were", "what", "when", "where", "which", "while", "who", "will",
    "with", "would", "you", "your",
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "ini", "itu", "pada",
    "adalah", "akan", "atau", "juga", "sudah", "bisa", "ada", "tidak", "saja",
}

WORD = re.compile(r"[A-Za-zÀ-ɏ]{2,}", re.UNICODE)
TOKEN = re.compile(r"\{\{[^}]+\}\}")


def _words(text: str | None) -> list[str]:
    """Lower-cased content words, with Meta's dynamic-creative tokens removed.

    `{{product.name}}` is real published text but it is a placeholder, not
    copy -- counting it would put "product" at the top of every ecommerce niche.
    """
    if not text:
        return []
    cleaned = TOKEN.sub(" ", text)
    return [w.lower() for w in WORD.findall(cleaned) if w.lower() not in STOPWORDS]


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[int(position)]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _round(value: float | None, places: int = 1) -> float | None:
    return None if value is None else round(value, places)


def _share(part: int, whole: int) -> float | None:
    return None if not whole else round(100.0 * part / whole, 1)


def _top(counter: Counter, limit: int, total: int) -> list[dict]:
    out = []
    for rank, (value, count) in enumerate(counter.most_common(limit), start=1):
        out.append(
            {
                "rank": rank,
                "value": value,
                "count": count,
                "share": _share(count, total),
            }
        )
    return out


def _longevity(ads: Iterable[dict]) -> dict:
    days = [a["runningDays"] for a in ads if isinstance(a.get("runningDays"), int)]
    return {
        "sampleWithDates": len(days),
        "medianRunningDays": _round(_percentile(days, 0.5), 0),
        "p90RunningDays": _round(_percentile(days, 0.9), 0),
        "maxRunningDays": max(days) if days else None,
    }


def _grouped_longevity(ads: list[dict], key: str, limit: int, min_sample: int) -> list[dict]:
    """Median days on air per value of `key`, for values with enough ads behind them.

    Groups thinner than `min_sample` are dropped rather than reported: a median
    computed from two ads is noise wearing a number's clothes.
    """
    buckets: dict[Any, list[int]] = {}
    for ad in ads:
        value = ad.get(key)
        if value in (None, ""):
            continue
        days = ad.get("runningDays")
        if not isinstance(days, int):
            continue
        buckets.setdefault(value, []).append(days)

    rows = []
    for value, days in buckets.items():
        if len(days) < min_sample:
            continue
        rows.append(
            {
                "value": value,
                "count": len(days),
                "medianRunningDays": _round(_percentile(days, 0.5), 0),
                "p90RunningDays": _round(_percentile(days, 0.9), 0),
            }
        )
    rows.sort(key=lambda r: (r["medianRunningDays"] or 0, r["count"]), reverse=True)
    for rank, row in enumerate(rows[:limit], start=1):
        row["rank"] = rank
    return rows[:limit]


def _phrases(ads: list[dict], size: int, limit: int) -> list[dict]:
    """Most repeated word sequences across the niche's ad copy.

    Counted once per ad, not once per occurrence: an ad that repeats its slogan
    six times should not outvote six advertisers who each said it once.
    """
    counter: Counter = Counter()
    for ad in ads:
        words = _words(ad.get("adText"))
        seen = {
            " ".join(words[i:i + size])
            for i in range(max(0, len(words) - size + 1))
        }
        counter.update(seen)
    return _top(counter, limit, len(ads))


def benchmark(niche: str, ads: list[dict], settings: dict) -> list[dict]:
    """One niche's sample -> a list of benchmark rows, each a dataset record."""
    total = len(ads)
    if not total:
        return []

    limit = int(settings.get("topN", 10))
    min_sample = int(settings.get("minGroupSample", 3))
    rows: list[dict] = []

    def add(metric: str, entries: list[dict], **extra) -> None:
        for entry in entries:
            rows.append(
                {
                    "niche": niche,
                    "metric": metric,
                    "sampleSize": total,
                    **entry,
                    **extra,
                }
            )

    active = sum(1 for a in ads if a.get("isActive"))
    with_video = sum(1 for a in ads if a.get("hasVideo"))
    advertisers = Counter(a.get("pageName") for a in ads if a.get("pageName"))
    longevity = _longevity(ads)
    word_counts = [a["adTextWordCount"] for a in ads if a.get("adTextWordCount")]

    # -- the headline row: one per niche, everything at a glance ---------------
    rows.append(
        {
            "niche": niche,
            "metric": "OVERVIEW",
            "rank": 1,
            "value": niche,
            "sampleSize": total,
            "activeShare": _share(active, total),
            "videoShare": _share(with_video, total),
            "distinctAdvertisers": len(advertisers),
            "adsPerAdvertiser": _round(total / len(advertisers)) if advertisers else None,
            "medianCopyWords": _round(_percentile(word_counts, 0.5), 0),
            "p90CopyWords": _round(_percentile(word_counts, 0.9), 0),
            **longevity,
        }
    )

    add("TOP_CTA", _top(Counter(a.get("ctaText") for a in ads if a.get("ctaText")), limit, total))
    add("TOP_FORMAT", _top(
        Counter(a.get("displayFormat") for a in ads if a.get("displayFormat")), limit, total))
    add("TOP_ADVERTISER", _top(advertisers, limit, total))
    add("TOP_PLATFORM", _top(
        Counter(p for a in ads for p in (a.get("publisherPlatforms") or [])), limit, total))
    add("TOP_HEADLINE", _top(
        Counter(a.get("title") for a in ads if a.get("title")), limit, total))
    add("TOP_LANDING_DOMAIN", _top(
        Counter(_domain(a.get("linkUrl")) for a in ads if _domain(a.get("linkUrl"))),
        limit, total))
    add("TOP_WORD", _phrases(ads, 1, limit))
    add("TOP_PHRASE_2", _phrases(ads, 2, limit))
    add("TOP_PHRASE_3", _phrases(ads, 3, limit))

    add("LONGEVITY_BY_CTA", _grouped_longevity(ads, "ctaText", limit, min_sample))
    add("LONGEVITY_BY_FORMAT", _grouped_longevity(ads, "displayFormat", limit, min_sample))
    add("LONGEVITY_BY_COPY_LENGTH",
        _grouped_longevity(
            [{**a, "copyLengthBand": _length_band(a.get("adTextWordCount"))} for a in ads],
            "copyLengthBand", limit, min_sample))

    return rows


DOMAIN = re.compile(r"^https?://(?:www\.)?([^/?#]+)", re.I)


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    match = DOMAIN.match(url)
    return match.group(1).lower() if match else None


def _length_band(words: Any) -> str | None:
    """Copy length in bands, because a median over raw word counts hides the shape."""
    if not isinstance(words, int) or words <= 0:
        return None
    if words <= 10:
        return "1-10 words"
    if words <= 25:
        return "11-25 words"
    if words <= 50:
        return "26-50 words"
    if words <= 100:
        return "51-100 words"
    return "100+ words"


def compare(rows: list[dict], metric: str, limit: int = 10) -> list[dict]:
    """Cross-niche view of one metric: which niche leans hardest on each value.

    Only produced when more than one niche was run, because a comparison of one
    thing against itself is a table nobody needs.
    """
    by_value: dict[Any, dict[str, Any]] = {}
    for row in rows:
        if row.get("metric") != metric or row.get("value") in (None, ""):
            continue
        entry = by_value.setdefault(
            row["value"], {"value": row["value"], "niches": {}, "totalCount": 0}
        )
        entry["niches"][row["niche"]] = row.get("share")
        entry["totalCount"] += row.get("count") or 0

    ordered = sorted(by_value.values(), key=lambda e: e["totalCount"], reverse=True)
    out = []
    for rank, entry in enumerate(ordered[:limit], start=1):
        out.append(
            {
                "niche": "ALL_NICHES",
                "metric": f"COMPARE_{metric}",
                "rank": rank,
                "value": entry["value"],
                "count": entry["totalCount"],
                "sharePerNiche": entry["niches"],
            }
        )
    return out
