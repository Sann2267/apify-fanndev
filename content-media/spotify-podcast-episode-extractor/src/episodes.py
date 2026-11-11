"""Read a Spotify podcast and mine what its episode descriptions actually hold.

The show metadata and the episode list come from two GraphQL queries. The rest
of this module is about the *description*, because that is where the useful
material lives: an episode description is where a podcast lists its guests, its
chapter timestamps and its sponsors, and none of that is structured data on
Spotify's side. It is one long HTML blob.

So descriptions are parsed: timestamps into a chapter list, URLs into links and
sponsor domains, and the title into guest hints. The mining is deliberately
conservative and every derived field is named so it reads as derived -- a
promo-code URL is a fact, "this episode's guest" is a guess.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from src.entities import as_int, dig, ms_to_clock, pick_image, plain_text
from src.uris import id_from_uri, url_from_uri

URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
HANDLE = re.compile(r"(?<![\w@])@([A-Za-z0-9._]{2,30})\b")
# A chapter line looks like "12:34 Something" or "1:02:03 - Something".
TIMESTAMP = re.compile(
    r"(?m)^[\s\-\*•\(\[]*((?:\d{1,2}:)?\d{1,2}:\d{2})[\s\-–—:.\)\]]*(.{2,120})$"
)
# Podcast titles overwhelmingly separate episode number from guest with one of
# these. "#2512 - Joey Diaz" and "Ep 14: Jane Roe on burnout" both give a guest.
TITLE_SPLIT = re.compile(r"\s+[-–—|:]\s+")
EPISODE_NUMBER = re.compile(r"(?:^|\s)#?(?:ep(?:isode)?\.?\s*)?(\d{1,5})\b", re.I)

# Domains that are never a sponsor: the podcast's own distribution and socials.
NOT_SPONSORS = {
    "spotify.com", "open.spotify.com", "podcasters.spotify.com", "anchor.fm",
    "apple.com", "podcasts.apple.com", "youtube.com", "youtu.be",
    "twitter.com", "x.com", "instagram.com", "facebook.com", "tiktok.com",
    "linktr.ee", "patreon.com", "bit.ly",
}


def _seconds(stamp: str) -> int:
    parts = [int(p) for p in stamp.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _domain(url: str) -> str | None:
    try:
        host = urlsplit(url).netloc.lower()
    except ValueError:
        return None
    return host[4:] if host.startswith("www.") else host or None


def mine_description(text: str | None, duration_ms: Any) -> dict:
    """Pull chapters, links, sponsor domains and handles out of a description."""
    if not text:
        return {"chapterCount": 0, "linkCount": 0}

    limit = as_int(duration_ms)
    chapters = []
    for stamp, label in TIMESTAMP.findall(text):
        seconds = _seconds(stamp)
        # A "timestamp" past the end of the episode is a date, a price or a
        # score that happens to look like one. Without the duration to check
        # against, obvious nonsense is still dropped.
        if limit and seconds * 1000 > limit:
            continue
        if not limit and seconds > 24 * 3600:
            continue
        cleaned = re.sub(r"\s+", " ", label).strip(" -–—:|")
        if cleaned:
            chapters.append({"time": stamp, "seconds": seconds, "title": cleaned[:200]})

    links = []
    seen = set()
    for url in URL.findall(text):
        url = url.rstrip(".,;:)")
        if url not in seen:
            seen.add(url)
            links.append(url)

    domains = []
    for url in links:
        host = _domain(url)
        if host and host not in NOT_SPONSORS and host not in domains:
            domains.append(host)

    handles = []
    for handle in HANDLE.findall(text):
        if handle.lower() not in {h.lower() for h in handles}:
            handles.append(handle)

    return {
        "chapters": chapters,
        "chapterCount": len(chapters),
        "links": links,
        "linkCount": len(links),
        "sponsorDomains": domains,
        "mentionedHandles": handles[:40],
    }


def guest_hints(title: str | None) -> list[str]:
    """Names a title *probably* contains, clearly labelled as a guess.

    Podcast titles are free text; nothing on Spotify marks who the guest is.
    This splits on the separators podcast titles conventionally use and keeps
    the parts that look like a person's name -- two or three capitalised words,
    no digits. It will miss guests and occasionally propose a segment name, so
    it is emitted as ``guestHints`` and never as ``guest``.
    """
    if not title:
        return []
    hints = []
    for part in TITLE_SPLIT.split(title):
        candidate = part.strip().strip("\"'")
        candidate = re.split(r"\s+\b(?:on|about|talks|discusses|and)\b\s+", candidate)[0]
        words = candidate.split()
        if not 2 <= len(words) <= 3:
            continue
        if any(any(ch.isdigit() for ch in word) for word in words):
            continue
        if all(word[:1].isupper() for word in words if word):
            hints.append(candidate)
    return hints


def parse_show(show: dict) -> dict:
    uri = show.get("uri")
    rating = show.get("rating") or {}
    average = dig(rating, "averageRating", "average")
    return {
        "showName": show.get("name"),
        "showId": show.get("id") or id_from_uri(uri),
        "showUri": uri,
        "showUrl": url_from_uri(uri),
        "publisher": dig(show, "publisher", "name"),
        "showDescription": plain_text(show.get("htmlDescription") or show.get("description")),
        "episodeCount": dig(show, "episodesV2", "totalCount"),
        "contentType": show.get("contentType"),
        "mediaType": show.get("mediaType"),
        "explicit": "EXPLICIT" in (dig(show, "contentRatingV2", "labels") or []),
        "topics": [
            topic.get("title")
            for topic in (show.get("topics") or [])
            if isinstance(topic, dict) and topic.get("title")
        ],
        "averageRating": round(average, 2) if isinstance(average, (int, float)) else None,
        "totalRatings": as_int(dig(rating, "averageRating", "totalRatings")),
        "coverArt": pick_image(show.get("coverArt")),
        "shareUrl": dig(show, "sharingInfo", "shareUrl"),
        "consumptionOrder": show.get("consumptionOrderV2"),
    }


def parse_episode(data: dict, mine: bool) -> dict:
    uri = data.get("uri")
    duration_ms = dig(data, "duration", "totalMilliseconds")
    description = plain_text(data.get("htmlDescription") or data.get("description"))
    released = dig(data, "releaseDate", "isoString")
    media_types = data.get("mediaTypes") or []
    record: dict[str, Any] = {
        "episodeName": data.get("name"),
        "episodeId": data.get("id") or id_from_uri(uri),
        "episodeUri": uri,
        "episodeUrl": url_from_uri(uri),
        "description": description,
        "descriptionLength": len(description) if description else 0,
        "releaseDate": released[:10] if isinstance(released, str) else None,
        "releasedAt": released,
        "durationMs": duration_ms,
        "duration": ms_to_clock(duration_ms),
        "durationMinutes": round(duration_ms / 60000) if as_int(duration_ms) else None,
        "explicit": dig(data, "contentRating", "label") == "EXPLICIT",
        "hasVideo": "VIDEO" in media_types,
        "mediaTypes": list(media_types),
        "hasTranscript": bool(dig(data, "transcripts", "items")),
        "isPaywalled": bool(dig(data, "restrictions", "paywallContent")),
        "playable": dig(data, "playability", "playable"),
        "shareUrl": dig(data, "sharingInfo", "shareUrl"),
        "coverArt": pick_image(data.get("coverArt")),
        "audioPreviewUrl": dig(data, "audio", "items", 0, "url"),
    }
    number = EPISODE_NUMBER.search(record["episodeName"] or "")
    record["episodeNumberHint"] = int(number.group(1)) if number else None
    if mine:
        record.update(mine_description(description, duration_ms))
        record["guestHints"] = guest_hints(record["episodeName"])
    return record
