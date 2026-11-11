"""Turn a user-supplied target into the exact /api/v1/playlist query params.

This is a direct port of the mapping found in Haystack's own minified web
bundle (the `Od` helper), which switches on an internal entity-type enum:

    case Category: {category: n, firstVideo: `${SITE}/${n}`, serverParams?}
    case Channel:  {category: `channel/${n}`}
    case Show:     {category: n, firstVideo: `${SITE}/channel/${n}`}
    case Topic:    {firstVideo: `${SITE}/tag/${n}`}
    case Location: {firstVideo: `${SITE}/location/${n}`}
    case Slug:     {firstVideo: `${SITE}/v/${n}`}
    case Id:       {firstVideo: `${SITE}/id/${n}`}
    case Search:   {search: n}

`firstVideo` therefore acts as a universal resolver: hand the API any
haystack.tv URL and it works out which feed that URL belongs to. Note it pins
the feed's starting position -- it is NOT a pagination cursor (verified: passing
the last video id returns the identical set).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from .constants import SITE_URL

# Route prefixes that carry their own entity semantics. Anything else at the
# root of the site is a category (/news, /sports, /live, /weather, ...).
_PREFIX_KINDS = {
    "v": "video",
    "id": "video",
    "channel": "channel",
    "tag": "topic",
    "location": "location",
    "local-events": "location",
}

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class Target:
    """A resolved scrape target."""

    kind: str          # category | channel | topic | location | video | search
    value: str         # the bare identifier (news, abc7, trump, houston-tx, ...)
    raw: str           # exactly what the user typed, for the _input envelope

    def playlist_params(self) -> dict[str, str]:
        """Params for GET /api/v1/playlist for this target."""
        if self.kind == "channel":
            return {"category": f"channel/{self.value}"}
        if self.kind == "topic":
            return {"firstVideo": f"{SITE_URL}/tag/{self.value}"}
        if self.kind == "location":
            return {"firstVideo": f"{SITE_URL}/location/{self.value}"}
        if self.kind == "video":
            # A bare id goes through /id/, a hyphenated slug through /v/.
            path = "id" if "-" not in self.value else "v"
            return {"firstVideo": f"{SITE_URL}/{path}/{self.value}"}
        if self.kind == "search":
            return {"search": self.value}
        # category
        return {"category": self.value, "firstVideo": f"{SITE_URL}/{self.value}"}


class InvalidTarget(ValueError):
    """The target string could not be parsed into a Haystack entity."""


def parse_target(raw: str, default_kind: str = "category") -> Target:
    """Parse a URL or bare identifier into a Target.

    Accepts, all interchangeably:
        https://www.haystack.tv/news          -> category  news
        haystack.tv/channel/abc7              -> channel   abc7
        /tag/trump                            -> topic     trump
        location/houston-tx                   -> location  houston-tx
        /v/trump-love-unified-ireland-6daOFLevf -> video   <slug>
        news                                  -> category  news   (default_kind)
        channel/abc7                          -> channel   abc7
    """
    if not isinstance(raw, str):
        raise InvalidTarget(f"Target must be a string, got {type(raw).__name__}.")

    text = raw.strip()
    if not text:
        raise InvalidTarget("Target is empty.")

    # Strip the scheme/host if the user pasted a full URL.
    path = text
    if "://" in text or text.lower().startswith("www.haystack.tv"):
        candidate = text if "://" in text else f"https://{text}"
        parsed = urlparse(candidate)
        host = (parsed.netloc or "").lower()
        if host and "haystack.tv" not in host:
            raise InvalidTarget(f"Not a haystack.tv URL: {raw!r}")
        path = parsed.path or "/"

    segments = [s for s in path.split("?")[0].split("#")[0].split("/") if s]

    if not segments:
        # The site root is the personalised "My Headlines" feed.
        return Target(kind="category", value="", raw=raw)

    head = segments[0].lower()

    if head in _PREFIX_KINDS:
        kind = _PREFIX_KINDS[head]
        # /local-events/location/<slug> carries an extra hop.
        rest = [s for s in segments[1:] if s.lower() != "location"]
        if not rest:
            raise InvalidTarget(f"URL {raw!r} has prefix /{head}/ but no identifier.")
        return Target(kind=kind, value=rest[0], raw=raw)

    if len(segments) == 1:
        value = segments[0]
        if not _SLUG_RE.match(value):
            raise InvalidTarget(f"{value!r} is not a valid Haystack identifier.")
        return Target(kind=default_kind, value=value, raw=raw)

    raise InvalidTarget(f"Could not classify target {raw!r}.")


def parse_targets(raws: list, default_kind: str = "category") -> tuple[list[Target], list[tuple[str, str]]]:
    """Parse many targets. Returns (targets, [(raw, error_detail), ...]).

    Bad inputs are returned rather than raised so the caller can emit one error
    record per bad input instead of failing the whole run.
    """
    ok: list[Target] = []
    bad: list[tuple[str, str]] = []
    for raw in raws or []:
        # Apify's "Start URLs" editor yields [{"url": "..."}] objects.
        if isinstance(raw, dict):
            raw = raw.get("url") or raw.get("value") or ""
        try:
            ok.append(parse_target(raw, default_kind=default_kind))
        except InvalidTarget as exc:
            bad.append((str(raw), str(exc)))
    return ok, bad


def location_slug_to_query(slug: str) -> str:
    """'salt-lake-city-ut' -> 'salt lake city' for the /suggest lookup."""
    parts = slug.split("-")
    if len(parts) > 1 and len(parts[-1]) == 2:
        parts = parts[:-1]
    return " ".join(parts)
