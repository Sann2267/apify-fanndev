"""Match free text against Spotify's catalogue and say how sure the match is.

The hard part of this job is not finding candidates -- Spotify's search returns
something for anything. Ask it for ``"zzzz nonexistent song xyzq 12345"`` and it
answers with a real track called *Zzz*. A matcher that simply takes the first
result therefore has a 100% "hit rate" and is wrong whenever the input is.

So every candidate is scored against the parsed title and artist, and anything
below a threshold is reported as **unmatched with its best guess attached**,
rather than silently passed off as a match. Getting told "no confident match,
closest was X at 0.41" is useful; being handed X as if it were right is not.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from src.entities import dig, ms_to_clock
from src.uris import id_from_uri, url_from_uri

# The separators people actually paste between a title and an artist.
SEPARATORS = re.compile(r"\s+(?:--|[-–—|/~])\s+|\s+by\s+|\s*\t\s*|\s*;\s*", re.I)
FEATURING = re.compile(r"\s*[\(\[]?\s*(?:feat\.?|ft\.?|featuring|with)\s+[^)\]]*[\)\]]?", re.I)
VERSION = re.compile(
    r"\s*[-(\[]\s*(?:\d{4}\s*)?(?:remaster(?:ed)?|remix|live|radio edit|acoustic|"
    r"single version|album version|mono|stereo|deluxe|extended|edit|version)"
    r"[^)\]]*[\)\]]?\s*$",
    re.I,
)
NOISE = re.compile(r"[^\w\s]", re.UNICODE)
LEADING_INDEX = re.compile(r"^\s*\d{1,3}\s*[.)\]-]\s+")


def fold(text: str | None) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(NOISE.sub(" ", stripped).lower().split())


def similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    ratio = SequenceMatcher(None, left, right).ratio()

    # One title fully contained in the other is usually the same recording with
    # a suffix ("sial" vs "sial remix version"), which a raw ratio punishes far
    # too hard. Two guards keep that from rescuing nonsense:
    #   - containment is checked on whole *words*, so "zzz" no longer counts as
    #     contained in "zzzz nonexistent song xyzq 12345";
    #   - the shorter side must be at least half the longer one, so a one-word
    #     candidate cannot claim a six-word query.
    short, long = sorted((left, right), key=len)
    short_words, long_words = short.split(), long.split()
    contained = short_words and all(word in long_words for word in short_words)
    if contained and len(short) >= 0.5 * len(long):
        ratio = max(ratio, 0.88)
    return ratio


def split_query(text: str) -> tuple[str, str | None]:
    """Split ``"Title - Artist"`` into parts without guessing which side is which.

    Both orders are common and neither can be told apart from the text alone,
    so the caller scores both arrangements and keeps whichever matches better.
    """
    cleaned = LEADING_INDEX.sub("", (text or "").strip())
    parts = [p.strip() for p in SEPARATORS.split(cleaned) if p and p.strip()]
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return cleaned, None


def parse_entry(entry) -> dict:
    """Accept a plain line or a structured object and normalise it."""
    if isinstance(entry, dict):
        title = str(entry.get("title") or entry.get("track") or entry.get("name") or "").strip()
        artist = str(entry.get("artist") or entry.get("artists") or "").strip() or None
        raw = " - ".join(p for p in (title, artist) if p) or str(entry)
        return {
            "raw": raw,
            "title": title,
            "artist": artist,
            "album": (entry.get("album") or None),
            "isrc": (entry.get("isrc") or None),
            "durationMs": entry.get("durationMs"),
            "structured": True,
        }
    title, artist = split_query(str(entry))
    return {
        "raw": str(entry).strip(),
        "title": title,
        "artist": artist,
        "album": None,
        "isrc": None,
        "durationMs": None,
        "structured": False,
    }


def candidate_from_hit(data: dict) -> dict | None:
    uri = data.get("uri")
    if not uri:
        return None
    artists = [
        dig(a, "profile", "name")
        for a in dig(data, "artists", "items", default=[]) or []
        if isinstance(a, dict)
    ]
    artists = [a for a in artists if a]
    duration = dig(data, "duration", "totalMilliseconds")
    album = data.get("albumOfTrack") or {}
    return {
        "trackName": data.get("name"),
        "trackId": data.get("id") or id_from_uri(uri),
        "trackUri": uri,
        "trackUrl": url_from_uri(uri),
        "artistNames": artists,
        "artistName": artists[0] if artists else None,
        "albumName": album.get("name"),
        "albumUrl": url_from_uri(album.get("uri")),
        "durationMs": duration,
        "duration": ms_to_clock(duration),
        "explicit": dig(data, "contentRating", "label") == "EXPLICIT",
    }


def score(candidate: dict, title: str, artist: str | None, raw: str,
          duration_ms=None) -> tuple[float, dict]:
    """Score one candidate against the parsed query. Returns (score, detail)."""
    wanted_title = fold(VERSION.sub("", FEATURING.sub("", title)))
    got_title_raw = fold(candidate.get("trackName"))
    got_title = fold(VERSION.sub("", FEATURING.sub("", candidate.get("trackName") or "")))
    title_score = max(
        similarity(wanted_title, got_title),
        similarity(fold(title), got_title_raw),
    )

    candidate_artists = [fold(a) for a in candidate.get("artistNames") or []]
    if artist:
        wanted_artist = fold(FEATURING.sub("", artist))
        artist_score = max(
            (similarity(wanted_artist, a) for a in candidate_artists), default=0.0
        )
        combined = 0.62 * title_score + 0.38 * artist_score
    else:
        # No artist was given, so the best available evidence is whether an
        # artist name shows up anywhere in the original line.
        folded_raw = fold(raw)
        artist_score = 1.0 if any(a and a in folded_raw for a in candidate_artists) else 0.0
        combined = title_score if not artist_score else 0.85 * title_score + 0.15

    detail = {"titleScore": round(title_score, 3), "artistScore": round(artist_score, 3)}

    if duration_ms and candidate.get("durationMs"):
        delta = abs(int(duration_ms) - int(candidate["durationMs"]))
        detail["durationDeltaMs"] = delta
        # Two seconds apart is the same recording; a minute apart is not.
        if delta <= 2000:
            combined = min(1.0, combined + 0.05)
        elif delta > 30000:
            combined -= 0.10

    return max(0.0, min(1.0, combined)), detail


CONFIDENCE = ((0.93, "exact"), (0.82, "high"), (0.70, "medium"))


def label(value: float) -> str:
    for threshold, name in CONFIDENCE:
        if value >= threshold:
            return name
    return "low"


def best_match(entry: dict, hits: list[dict], minimum: float) -> dict:
    """Pick the best candidate for one input line, or report no confident match."""
    candidates = []
    for hit in hits:
        if hit["kind"] != "Track":
            continue
        candidate = candidate_from_hit(hit["data"])
        if candidate:
            candidates.append(candidate)

    if not candidates:
        return {
            "matched": False,
            "matchConfidence": "none",
            "matchScore": 0.0,
            "unmatchedReason": "Spotify returned no tracks for this query.",
        }

    # Try the query both ways round -- "Title - Artist" and "Artist - Title" --
    # and keep whichever reading scores better. Neither order can be told from
    # the text alone, and both are common in exported setlists.
    arrangements = [(entry["title"], entry["artist"])]
    if entry["artist"] and not entry.get("structured"):
        arrangements.append((entry["artist"], entry["title"]))

    best = None
    for title, artist in arrangements:
        for candidate in candidates:
            value, detail = score(
                candidate, title, artist, entry["raw"], entry.get("durationMs")
            )
            if best is None or value > best[0]:
                best = (value, candidate, detail, title, artist)

    value, candidate, detail, used_title, used_artist = best
    confidence = label(value)
    # With no artist anywhere in the input there is nothing to corroborate a
    # title match, so the result is capped below "exact" however well the
    # strings line up -- several different recordings share a title.
    if not used_artist and not detail.get("artistScore") and confidence == "exact":
        confidence = "high"
    result = {
        "matchScore": round(value, 3),
        "matchConfidence": confidence,
        "queryTitle": used_title,
        "queryArtist": used_artist,
        "candidatesConsidered": len(candidates),
        **detail,
    }
    if value >= minimum:
        result["matched"] = True
        result.update(candidate)
    else:
        result["matched"] = False
        result["unmatchedReason"] = (
            f"Best candidate {candidate.get('trackName')!r} by "
            f"{candidate.get('artistName')} scored {value:.2f}, below the "
            f"{minimum:.2f} threshold."
        )
        result["bestGuessName"] = candidate.get("trackName")
        result["bestGuessArtist"] = candidate.get("artistName")
        result["bestGuessUri"] = candidate.get("trackUri")
        result["bestGuessUrl"] = candidate.get("trackUrl")
    return result
