"""Input normalisation and record builders.

Records follow the portfolio envelope (_input/_source/_scrapedAt + recordType)
and pass upstream fields through verbatim. The few extra fields we add
(videoUrl, createdAt, hashtags, ...) are additions, never renames.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from .constants import SITE

# Hashtags in captions mix scripts (Urdu, Bengali, Indonesian...) and the app
# glues them together ("#viral#fyp"), so match any run of word characters.
HASHTAG_RE = re.compile(r"#([^\s#.,!?;:()\[\]{}\"'`]+)", re.UNICODE)
DIGITS_RE = re.compile(r"^\d{6,}$")
KWAI_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{2,64}$")

# Route patterns from the web app's router table.
VIDEO_PATH_RE = re.compile(r"/(?:video|embed|picture)/(\d{6,})")
PLAYLIST_PATH_RE = re.compile(r"/playlist/(\d{6,})")
HANDLE_PATH_RE = re.compile(r"^/@([^/?#]+)")
TOPIC_PATH_RE = re.compile(r"^/topic/([^/?#]+)")

SNACK_HOSTS = ("snackvideo.com", "www.snackvideo.com", "m.snackvideo.com")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ms_to_iso(ms: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def encode_uri_component(value: str) -> str:
    """JavaScript encodeURIComponent - the web app sends topic/search words this way."""
    return urllib.parse.quote(value, safe="-_.!~*'()")


def slug_word(value: str) -> str:
    """How the app turns a typed word into a topic/search key: trim, spaces -> '-'."""
    return re.sub(r"\s+", "-", value.strip())


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://")) or value.startswith(("www.", "snackvideo.com"))


def _as_url(value: str) -> urllib.parse.ParseResult:
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    return urllib.parse.urlparse(value)


def is_snack_url(value: str) -> bool:
    return is_url(value) and _as_url(value).netloc.lower() in SNACK_HOSTS


def parse_handle(value: str) -> str | None:
    """'@name', 'name' or any snackvideo.com/@name/... URL -> 'name'."""
    value = value.strip()
    if is_url(value):
        m = HANDLE_PATH_RE.match(_as_url(value).path)
        return urllib.parse.unquote(m.group(1)) if m else None
    value = value.lstrip("@")
    return value if KWAI_ID_RE.match(value) else None


def parse_video_id(value: str) -> str | None:
    value = value.strip()
    if DIGITS_RE.match(value):
        return value
    if is_url(value):
        m = VIDEO_PATH_RE.search(_as_url(value).path)
        return m.group(1) if m else None
    return None


def parse_playlist_id(value: str) -> str | None:
    value = value.strip()
    if DIGITS_RE.match(value):
        return value
    if is_url(value):
        m = PLAYLIST_PATH_RE.search(_as_url(value).path)
        return m.group(1) if m else None
    return None


def parse_hashtag(value: str) -> str | None:
    value = value.strip()
    if is_url(value):
        m = TOPIC_PATH_RE.match(_as_url(value).path)
        value = urllib.parse.unquote(m.group(1)) if m else ""
    value = value.lstrip("#").strip()
    return value or None


def keyword_matches(keyword: str, caption: str | None) -> bool:
    """Every word of the keyword appears in the caption (case-insensitive)."""
    text = html.unescape(caption or "").lower()
    words = [w for w in re.split(r"[\s\-]+", keyword.lower()) if w]
    return bool(words) and all(w in text for w in words)


def _first_url(items: Any) -> str | None:
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict) and it.get("url"):
                return it["url"]
    return None


def envelope(input_value: str, source: str, record_type: str) -> dict[str, Any]:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }


def video_record(
    feed: dict[str, Any],
    *,
    input_value: str,
    source: str,
    include_manifest: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = dict(feed)
    if not include_manifest:
        # ~40% of a record's bytes: per-bitrate stream ladder with signed,
        # expiring URLs. main_mv_urls already carries a playable URL.
        raw.pop("transcode_manifest_info", None)
    photo_id = str(raw.get("photo_id_str") or raw.get("photo_id") or "")
    kwai_id = raw.get("kwai_id")
    # Some captions arrive HTML-escaped ("#Com&eacute;dia"); the raw caption is
    # kept verbatim, captionText/hashtags use the decoded text.
    caption = html.unescape(raw.get("caption") or "")
    ext = raw.get("ext_params") if isinstance(raw.get("ext_params"), dict) else {}
    rec = envelope(input_value, source, "VIDEO")
    rec.update({
        "id": photo_id or None,
        "videoUrl": f"{SITE}/@{kwai_id}/video/{photo_id}" if kwai_id and photo_id else None,
        "profileUrl": f"{SITE}/@{kwai_id}" if kwai_id else None,
        "captionText": caption,
        "createdAt": ms_to_iso(raw.get("timestamp")),
        "hashtags": HASHTAG_RE.findall(caption),
        "durationMs": ext.get("video"),
        "playUrl": _first_url(raw.get("main_mv_urls")),
        "coverUrl": _first_url(raw.get("cover_thumbnail_urls")),
    })
    if extra:
        rec.update(extra)
    for k, v in raw.items():
        rec.setdefault(k, v)
    return rec


def profile_record(data: dict[str, Any], *, input_value: str) -> dict[str, Any]:
    up = data["userProfile"]
    prof = up.get("profile") or {}
    counts = up.get("ownerCount") or {}
    kwai_id = prof.get("kwai_id")
    rec = envelope(input_value, "S1-api-profile", "PROFILE")
    rec.update({
        "id": kwai_id,
        "profileUrl": f"{SITE}/@{kwai_id}" if kwai_id else None,
        "kwai_id": kwai_id,
        "user_id": prof.get("user_id"),
        "user_name": prof.get("user_name"),
        "followers": counts.get("fan"),
        "following": counts.get("follow"),
        "publicVideos": counts.get("photo_public"),
        "encryptUid": data.get("encryptUid"),
    })
    for k, v in up.items():
        rec.setdefault(k, v)
    return rec


def playlist_record(album: dict[str, Any], *, input_value: str, source: str, kwai_id: str | None = None) -> dict[str, Any]:
    album_id = str(album.get("albumIdStr") or album.get("albumId") or "")
    rec = envelope(input_value, source, "PLAYLIST")
    rec.update({
        "id": album_id or None,
        "playlistUrl": f"{SITE}/@{kwai_id}/playlist/{album_id}" if kwai_id and album_id else (
            f"{SITE}/playlist/{album_id}" if album_id else None
        ),
        "coverUrl": _first_url(album.get("firstPhotoCover")),
    })
    for k, v in album.items():
        rec.setdefault(k, v)
    return rec


def error_record(input_value: str, kind: str, detail: str = "", record_type: str = "ERROR") -> dict[str, Any]:
    rec = envelope(input_value, "none", record_type)
    rec.update({"id": None, "_error": kind, "_errorDetail": detail})
    return rec
