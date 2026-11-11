"""Parsers that turn Spotify's GraphQL unions into flat, stable records.

Everything here reads defensively. Spotify's pathfinder payloads are deeply
nested and it routinely adds, renames and nulls fields, so a missing branch
yields ``None`` rather than raising -- the actor should lose one column, not
the whole run. The one exception is the top-level entity check in
``SpotifyClient.entity``, which does raise, because an entity that is not there
at all is a different problem from a field that moved.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

from src.uris import id_from_uri, url_from_uri

TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"[ \t\r\f\v]+")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(raw_input: str, source: str, record_type: str, payload: dict) -> dict:
    """Wrap a payload in the dataset envelope every row in this actor carries."""
    return {
        "_input": raw_input,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
        **payload,
    }


def error_record(raw_input: str, error: str, detail: str) -> dict:
    return {
        "_input": raw_input,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "recordType": "ERROR",
        "_error": error,
        "_errorDetail": detail,
    }


def dig(node: Any, *path: Any, default: Any = None) -> Any:
    """Walk a nested payload by keys and list indices, returning default if it ends."""
    current = node
    for step in path:
        if current is None:
            return default
        if isinstance(step, int):
            if not isinstance(current, (list, tuple)) or len(current) <= step:
                return default
            current = current[step]
        else:
            if not isinstance(current, dict):
                return default
            current = current.get(step)
    return default if current is None else current


def plain_text(value: str | None) -> str | None:
    """Strip HTML tags and unescape entities from a description field.

    Spotify returns podcast descriptions twice -- once as ``htmlDescription``
    with real markup and once as ``description`` which is *usually* plain but
    still carries entities. Running both through this keeps the two comparable.
    """
    if not value:
        return None
    text = TAG.sub(" ", value)
    text = html.unescape(text)
    text = WHITESPACE.sub(" ", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip() or None


def _image_sources(node: Any) -> list[dict]:
    """Flatten Spotify's three different image containers into one list.

    Covers arrive as ``{"sources": [...]}`` on tracks and albums, but playlists
    wrap them once more as ``{"items": [{"sources": [...]}]}``. Reading only the
    first shape is why a playlist cover silently comes back null.
    """
    if isinstance(node, dict):
        if isinstance(node.get("sources"), list):
            return [s for s in node["sources"] if isinstance(s, dict)]
        if isinstance(node.get("items"), list):
            flattened: list[dict] = []
            for item in node["items"]:
                flattened.extend(_image_sources(item))
            return flattened
        return []
    if isinstance(node, list):
        flattened = []
        for item in node:
            if isinstance(item, dict) and item.get("url"):
                flattened.append(item)
            else:
                flattened.extend(_image_sources(item))
        return flattened
    return []


def _pixels(source: dict) -> int:
    """Area of an image source, whichever of Spotify's two spellings it uses.

    Covers report ``width``/``height``; artist header and avatar images report
    ``maxWidth``/``maxHeight`` for the identical concept. Reading only one
    spelling makes every artist image tie at zero and picks an arbitrary size.
    """
    width = source.get("width") or source.get("maxWidth") or 0
    height = source.get("height") or source.get("maxHeight") or 0
    return int(width) * int(height)


def pick_image(node: Any, largest: bool = True) -> str | None:
    """Largest (or smallest) image URL from any Spotify image container.

    Spotify lists image sources in no reliable order -- a 300px cover routinely
    comes before the 64px and 640px ones -- so picking by position silently
    yields thumbnails. Always pick by dimension. Playlist covers carry null
    dimensions, in which case every candidate ties and the first URL wins.
    """
    usable = [s for s in _image_sources(node) if s.get("url")]
    if not usable:
        return None
    chooser = max if largest else min
    return chooser(usable, key=_pixels).get("url")


def all_images(node: Any) -> list[dict]:
    return [
        {
            "url": s.get("url"),
            "width": s.get("width") or s.get("maxWidth"),
            "height": s.get("height") or s.get("maxHeight"),
        }
        for s in _image_sources(node)
        if s.get("url")
    ]


def real_items(node: Any, key: str = "data") -> list[dict]:
    """Unwrap a Spotify item list, dropping the hollow entries it mixes in.

    Spotify pads several lists -- artist ``discoveredOnV2`` is the usual one --
    with ``{"__typename": "GenericError"}`` placeholders where an entity could
    not be resolved. They sit in the same array as real results, so a caller
    that does not filter them emits rows of nulls.
    """
    items = node.get("items") if isinstance(node, dict) else node
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        payload = (item or {}).get(key) if isinstance(item, dict) else None
        if payload is None and isinstance(item, dict) and item.get("__typename"):
            payload = item
        if not isinstance(payload, dict):
            continue
        if payload.get("__typename") in ("GenericError", "NotFound", "RestrictedContent"):
            continue
        out.append(payload)
    return out


def ms_to_clock(milliseconds: Any) -> str | None:
    """``225834`` -> ``"3:45"``; hours appear only when there are some."""
    try:
        total = int(milliseconds) // 1000
    except (TypeError, ValueError):
        return None
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def as_int(value: Any) -> int | None:
    """Spotify sends playcount as a decimal *string*; other counts as ints."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def iso_date(node: Any) -> str | None:
    """Release dates arrive as ``{"isoString": ..., "precision": "DAY"}``."""
    if isinstance(node, dict):
        iso = node.get("isoString")
        if iso:
            return str(iso)[:10] if len(str(iso)) >= 10 else str(iso)
        year = node.get("year")
        return str(year) if year else None
    if isinstance(node, str):
        return node[:10]
    return None


def artist_refs(node: Any) -> list[dict]:
    """``{"items": [{"uri":..., "profile": {"name":...}}]}`` -> flat list."""
    items = node.get("items") if isinstance(node, dict) else node
    if not isinstance(items, list):
        return []
    refs = []
    for item in items:
        if not isinstance(item, dict):
            continue
        uri = item.get("uri")
        name = dig(item, "profile", "name") or item.get("name")
        if not name and not uri:
            continue
        refs.append({"name": name, "id": id_from_uri(uri), "uri": uri,
                     "url": url_from_uri(uri)})
    return refs


def parse_track(data: dict) -> dict:
    """A track as it appears inside a playlist, album or chart payload."""
    uri = data.get("uri")
    album = data.get("albumOfTrack") or {}
    artists = artist_refs(data.get("artists"))
    duration_ms = dig(data, "trackDuration", "totalMilliseconds") or dig(
        data, "duration", "totalMilliseconds"
    )
    return {
        "trackName": data.get("name"),
        "trackId": id_from_uri(uri),
        "trackUri": uri,
        "trackUrl": url_from_uri(uri),
        "artistNames": [a["name"] for a in artists if a.get("name")],
        "artistName": artists[0]["name"] if artists else None,
        "artists": artists,
        "albumName": album.get("name"),
        "albumId": id_from_uri(album.get("uri")),
        "albumUri": album.get("uri"),
        "albumUrl": url_from_uri(album.get("uri")),
        "releaseDate": iso_date(album.get("date")),
        "durationMs": duration_ms,
        "duration": ms_to_clock(duration_ms),
        "discNumber": data.get("discNumber"),
        "trackNumber": data.get("trackNumber"),
        "explicit": (dig(data, "contentRating", "label") == "EXPLICIT"),
        # playcount is Spotify's own lifetime stream count. It has no equivalent
        # in the official Web API, which only exposes a 0-100 popularity score.
        "playcount": as_int(data.get("playcount")),
        "playable": dig(data, "playability", "playable"),
        "coverArt": pick_image(album.get("coverArt")),
        "coverArtSmall": pick_image(album.get("coverArt"), largest=False),
    }
