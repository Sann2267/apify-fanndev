"""Turn whatever a buyer pastes into a Spotify (type, id) pair.

People paste share links with ``?si=`` tracking tails, localised links with an
``/intl-pt/`` segment, ``spotify:`` URIs copied from the desktop app, and bare
22-character ids. All four mean the same thing, so all four are accepted.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

SPOTIFY_ID = re.compile(r"^[A-Za-z0-9]{22}$")
URI_PATTERN = re.compile(r"^spotify:(?:[a-z]+:)*?([a-z]+):([A-Za-z0-9]{22})$")
# open.spotify.com/intl-pt/track/<id>, /embed/track/<id>, /track/<id>
URL_PATTERN = re.compile(
    r"open\.spotify\.com/(?:embed/)?(?:intl-[a-z]{2}/)?"
    r"(track|album|artist|playlist|show|episode|user)/([A-Za-z0-9._-]+)",
    re.I,
)

KINDS = ("track", "album", "artist", "playlist", "show", "episode", "user")


class BadReference(ValueError):
    """The text is not a Spotify link, URI or id of the expected kind."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_reference(text: str, default_kind: str | None = None) -> tuple[str, str]:
    """Return ``(kind, id)`` for a Spotify link, URI or bare id.

    ``default_kind`` is what a bare id is assumed to be -- an actor that only
    ever handles playlists can accept a naked playlist id, while one that takes
    several entity kinds cannot guess and should leave it unset.
    """
    value = (text or "").strip()
    if not value:
        raise BadReference("Empty reference.")

    match = URI_PATTERN.match(value)
    if match:
        return match.group(1).lower(), match.group(2)

    match = URL_PATTERN.search(value)
    if match:
        return match.group(1).lower(), match.group(2)

    if SPOTIFY_ID.match(value):
        if not default_kind:
            raise BadReference(
                f"{value!r} is a bare Spotify id, but it could be a track, album, "
                f"artist or playlist -- paste the full link instead."
            )
        return default_kind, value

    # A user handle is not 22 characters and has its own alphabet, so a bare
    # string is only ever a plausible user id.
    if default_kind == "user" and re.fullmatch(r"[A-Za-z0-9._-]{2,64}", value):
        return "user", value

    raise BadReference(
        f"{value!r} is not a Spotify link, URI or id. Expected something like "
        f"https://open.spotify.com/playlist/37i9dQZEVXbMDoHDwVN2tF or "
        f"spotify:playlist:37i9dQZEVXbMDoHDwVN2tF."
    )


def expect(text: str, kind: str) -> str:
    """Parse a reference and insist it is of ``kind``, returning the id."""
    found, identifier = parse_reference(text, default_kind=kind)
    if found != kind:
        raise BadReference(
            f"{text!r} points at a Spotify {found}, but this input needs a {kind}."
        )
    return identifier


def uri_of(kind: str, identifier: str) -> str:
    return f"spotify:{kind}:{identifier}"


def url_of(kind: str, identifier: str) -> str:
    return f"https://open.spotify.com/{kind}/{identifier}"


def id_from_uri(uri: str | None) -> str | None:
    """Last segment of a ``spotify:kind:id`` URI, or None."""
    if not uri or not isinstance(uri, str):
        return None
    parts = uri.split(":")
    return parts[-1] if len(parts) >= 3 else None


def kind_from_uri(uri: str | None) -> str | None:
    if not uri or not isinstance(uri, str):
        return None
    parts = uri.split(":")
    return parts[-2] if len(parts) >= 3 else None


def url_from_uri(uri: str | None) -> str | None:
    kind, identifier = kind_from_uri(uri), id_from_uri(uri)
    if not kind or not identifier:
        return None
    return url_of(kind, identifier)
