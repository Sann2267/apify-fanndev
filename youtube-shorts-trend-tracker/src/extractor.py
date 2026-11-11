"""Parse the hashtag grid and the individual Short page.

The two parsers are deliberately asymmetric because the two surfaces carry
different data at different precision — see ``src/constants.py``. Everything
here reports which surface a number came from so a rounded grid figure is never
silently presented as an exact one.
"""

import re

from src.constants import SCALE_WORDS, SHORTS_MAX_SECONDS

# "Frog Eggs Time Challenge! ⏱️🐸🧪, 3.3 million views - play Short"
GRID_ENTRY = re.compile(
    r'"accessibilityText":"(?P<text>[^"]*?(?P<count>[\d.,]+)\s*'
    r'(?P<scale>thousand|million|billion|K|M|B)?\s*views[^"]*?)"'
)
VIDEO_ID = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')
# Two shapes, and which one you get depends on the URL you asked for:
#   /shorts/<id>   -> "like this video along with 36 thousand other people"
#   /watch?v=<id>  -> "like this video along with 36,212 other people"
# Both were measured on the same video on 2026-09-20. The Actor reports which
# it used via likeCountIsApprox rather than passing a rounded figure off as
# exact.
LIKES_TEXT = re.compile(
    r"like this video along with ([\d,.]+)\s*(thousand|million|billion|K|M|B)?\s*other people"
)
SHORT_DESCRIPTION = re.compile(r'"shortDescription":"((?:[^"\\]|\\.)*)"')
VIEW_COUNT = re.compile(r'"viewCount":"(\d+)"')
LENGTH = re.compile(r'"lengthSeconds":"(\d+)"')
TITLE = re.compile(r'"title":"((?:[^"\\]|\\.)*)","lengthSeconds"')
AUTHOR = re.compile(r'"author":"((?:[^"\\]|\\.)*)"')
CHANNEL_ID = re.compile(r'"channelId":"(UC[A-Za-z0-9_-]{20,})"')
SOUND = re.compile(r'soundAttributionTitle.{0,60}?content.{0,6}?([^\\"]{2,80}?)(?:\\x22|")')
HASHTAG = re.compile(r"#(\w{2,40})")
KEYWORDS = re.compile(r'"keywords":\[(.*?)\]')


def unescape_hex(body: str) -> str:
    r"""Turn ``\x22``/``\x7b`` escapes into real characters.

    On ``/shorts/<id>`` pages the payload lives inside a JavaScript string, so
    ``soundAttributionTitle`` appears as ``\x22soundAttributionTitle\x22``.
    A scan for the plain key finds nothing and would wrongly conclude the field
    does not exist.
    """
    if "\\x22" not in body:
        return body
    return re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), body)


def _data_region(body: str) -> str:
    """Everything from the ytInitialData assignment onward.

    Scanning the raw text rather than a re-parsed object is a measured choice:
    a structurally valid ``ytInitialData`` parse on a channel page held zero
    video IDs while the raw body held thirty. Anchoring at the assignment keeps
    IDs from earlier prefetch scripts out.
    """
    index = body.find("ytInitialData")
    return body[index:] if index >= 0 else body


def _to_int(count: str, scale: str | None) -> int | None:
    try:
        value = float(count.replace(",", ""))
    except ValueError:
        return None
    if scale:
        value *= SCALE_WORDS.get(scale.lower(), 1)
    return int(round(value))


def parse_hashtag_grid(body: str, limit: int) -> list[dict]:
    """Shorts listed for one hashtag, in the order YouTube ranked them.

    Order matters and is preserved: position in this grid *is* the trend
    signal, so ``gridPosition`` is part of every record.
    """
    region = _data_region(body)

    ids: list[str] = []
    for vid in VIDEO_ID.findall(region):
        if vid not in ids:
            ids.append(vid)

    entries: list[dict] = []
    for match in GRID_ENTRY.finditer(region):
        text = match.group("text")
        title = text.split(", ")[0] if ", " in text else text
        entries.append({
            "title": title.strip(),
            "viewsApprox": _to_int(match.group("count"), match.group("scale")),
            "viewsApproxText": text,
        })

    out: list[dict] = []
    for position, entry in enumerate(entries[:limit], start=1):
        video_id = ids[position - 1] if position - 1 < len(ids) else None
        out.append({
            "gridPosition": position,
            "videoId": video_id,
            "url": f"https://www.youtube.com/shorts/{video_id}" if video_id else None,
            **entry,
        })
    return out


def parse_short_detail(body: str) -> dict:
    """Figures from one Short's page.

    Scans the whole document, not the ``ytInitialData`` region. On
    ``/shorts/<id>`` the assignment sits at roughly byte 1,342,000 while the
    like button appears at 900,000 -- anchoring at the assignment, which is
    right for a channel grid, silently drops the engagement data here.
    """
    text = unescape_hex(body)

    views = VIEW_COUNT.search(text)
    length = LENGTH.search(text)
    title = TITLE.search(text)
    author = AUTHOR.search(text)
    channel = CHANNEL_ID.search(text)
    sound = SOUND.search(text)

    view_count = int(views.group(1)) if views else None

    # A Shorts page renders several like buttons (the neighbouring Shorts in
    # the carousel each have one). The smallest plausible figure is not a safe
    # pick and neither is the first, so match them all and take the one that
    # belongs to the video whose viewCount we just read: likes never exceed
    # views, and the carousel neighbours are unrelated videos.
    candidates: list[tuple[int, bool]] = []
    for match in LIKES_TEXT.finditer(text):
        raw, scale = match.group(1), match.group(2)
        value = _to_int(raw, scale)
        if value is not None:
            candidates.append((value, bool(scale)))

    like_count, like_approx = None, None
    if candidates:
        usable = [c for c in candidates if view_count is None or c[0] <= view_count]
        like_count, like_approx = (usable or candidates)[-1]

    seconds = int(length.group(1)) if length else None

    description_match = SHORT_DESCRIPTION.search(text)
    description = _unescape_json(description_match.group(1)) if description_match else ""
    hashtags = sorted(set(HASHTAG.findall(description)))

    ratio = None
    if view_count and like_count is not None and view_count > 0:
        ratio = round(like_count / view_count * 100, 4)

    return {
        "videoId": None,
        "title": _unescape_json(title.group(1)) if title else None,
        "channelName": _unescape_json(author.group(1)) if author else None,
        "channelId": channel.group(1) if channel else None,
        "viewCount": view_count,
        "likeCount": like_count,
        "likeCountIsApprox": like_approx,
        "likeToViewPercent": ratio,
        "lengthSeconds": seconds,
        "isShortFormat": (seconds is not None and seconds <= SHORTS_MAX_SECONDS),
        "soundAttribution": sound.group(1).strip() if sound else None,
        "description": description,
        "hashtags": hashtags,
    }


def _unescape_json(raw: str) -> str:
    """Decode the \\u and \\" escapes inside a raw JSON string fragment."""
    try:
        import json
        return json.loads('"' + raw + '"')
    except Exception:
        return raw
