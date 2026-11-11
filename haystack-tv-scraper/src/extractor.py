"""Pure parsing: upstream payload -> dataset records.

Follows the portfolio's raw-passthrough rule -- upstream field names are kept
verbatim and only the `_`-prefixed envelope plus `recordType` are added, so a
Haystack schema change flows through instead of silently dropping columns.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .constants import SITE_URL


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(input_value: str, source: str, record_type: str) -> dict:
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
    }


def error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    rec = envelope(input_value, "none", "ERROR")
    rec["_error"] = error_kind
    if detail:
        rec["_errorDetail"] = detail[:1000]
    return rec


# -- videos -------------------------------------------------------------------


def video_id_of(stream: dict) -> str | None:
    """Haystack's short video id, e.g. 6daOFLevf, taken from streamUrl."""
    url = stream.get("streamUrl") or ""
    if isinstance(url, str) and "/" in url:
        tail = url.rstrip("/").rsplit("/", 1)[-1]
        return tail or None
    return None


def video_record(
    stream: dict,
    input_value: str,
    source: str,
    record_type: str = "VIDEO",
    extra: dict | None = None,
) -> dict:
    """One video/stream row.

    `videoId` and `webUrl` are the only derived fields -- both are convenience
    keys the upstream payload does not carry directly but every consumer wants.
    """
    rec = envelope(input_value, source, record_type)
    vid = video_id_of(stream)
    if vid:
        rec["videoId"] = vid
    slug = stream.get("slug")
    if slug:
        rec["webUrl"] = f"{SITE_URL}/v/{slug}"
    if extra:
        rec.update(extra)
    rec.update(stream)          # raw passthrough wins over derived keys
    return rec


def playlist_meta(payload: dict) -> dict:
    """Feed-level context worth stamping on each video of that feed."""
    info = payload.get("channelInfo") or {}
    meta = {}
    if payload.get("channel"):
        meta["feedChannel"] = payload["channel"]
    if info.get("title"):
        meta["feedTitle"] = info["title"]
    if payload.get("playlistId") is not None:
        meta["playlistId"] = payload["playlistId"]
    return meta


def tag_group_records(payload: dict, input_value: str, source: str) -> list[dict]:
    """`tagGroups` -- the trending-topic histogram attached to a feed."""
    out = []
    for group in payload.get("tagGroups") or []:
        if not isinstance(group, dict):
            continue
        rec = envelope(input_value, source, "TAG_GROUP")
        rec.update(group)
        out.append(rec)
    return out


# -- catalogues ---------------------------------------------------------------


def channel_record(channel: dict, input_value: str, source: str) -> dict:
    rec = envelope(input_value, source, "CHANNEL")
    name = channel.get("slug") or channel.get("name")
    if name:
        rec["webUrl"] = f"{SITE_URL}/channel/{name}"
    rec.update(channel)
    return rec


def category_record(path: str, category: dict, input_value: str, source: str) -> dict:
    rec = envelope(input_value, source, "CATEGORY")
    rec["path"] = path
    rec["webUrl"] = f"{SITE_URL}{path}" if path.startswith("/") else f"{SITE_URL}/{path}"
    rec.update(category)
    return rec


def simple_record(payload: dict, input_value: str, source: str, record_type: str) -> dict:
    rec = envelope(input_value, source, record_type)
    rec.update(payload)
    return rec


def poll_record(poll: dict, input_value: str, source: str) -> dict:
    """Poll plus derived vote percentages (the site computes these client-side)."""
    rec = envelope(input_value, source, "POLL")
    poll_id = poll.get("_id") or poll.get("slug")
    if poll_id:
        rec["pollId"] = poll_id
        rec["webUrl"] = f"{SITE_URL}/poll/{poll_id}"

    choices = poll.get("choices")
    counts = poll.get("choiceVoteCount")
    total = poll.get("totalVoteCount")
    if isinstance(choices, list) and isinstance(counts, list) and len(choices) == len(counts):
        denom = total if isinstance(total, (int, float)) and total else sum(counts)
        rec["results"] = [
            {
                "choice": choice,
                "votes": votes,
                "pct": round(100.0 * votes / denom, 2) if denom else None,
            }
            for choice, votes in zip(choices, counts)
        ]
    rec.update(poll)
    return rec


def local_event_record(
    event: dict,
    input_value: str,
    source: str,
    location: dict | None,
    slice_tag: str,
) -> dict:
    rec = envelope(input_value, source, "LOCAL_EVENT")
    rec["_slice"] = slice_tag
    if location:
        rec["locationSlug"] = location.get("slug")
        rec["locationCity"] = location.get("city")
        rec["locationRegion"] = location.get("region")
    rec.update(event)
    return rec
