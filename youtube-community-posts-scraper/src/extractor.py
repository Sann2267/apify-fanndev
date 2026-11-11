"""Parse community posts out of ``/@handle/posts``.

Structural, not regex: every field is read from the ``backstagePostRenderer``
object by key. That matters here because posts are heterogeneous — one is text
only, the next carries four images, the next a poll, the next a video — and a
text-scanning parser produces plausible rows with the wrong attachment stuck to
the wrong post.
"""

import json
import re
from urllib.parse import parse_qs, unquote, urlparse

from src.constants import SCALE_SUFFIXES, UNAVAILABLE_MARKER

ABBREVIATED = re.compile(r"^([\d.,]+)\s*([KMB])?$", re.IGNORECASE)
COUNT_IN_TEXT = re.compile(r"([\d.,]+)\s*([KMB])?\s*(?:likes?|votes?|comments?|replies)",
                           re.IGNORECASE)


class CommunityUnavailable(Exception):
    """The channel's community tab is switched off, or the handle is wrong."""


def extract_json_blob(body: str, marker: str) -> dict | None:
    """First complete JSON object assigned after ``marker``, brace-counted."""
    start = body.find(marker)
    if start < 0:
        return None
    start = body.find("{", start)
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(body)):
        char = body[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(body[start:index + 1])
                except json.JSONDecodeError:
                    return None
    return None


def walk(node, key: str, out: list | None = None) -> list:
    """Every value stored under ``key`` anywhere in the tree."""
    out = [] if out is None else out
    if isinstance(node, dict):
        for name, value in node.items():
            if name == key:
                out.append(value)
            walk(value, key, out)
    elif isinstance(node, list):
        for value in node:
            walk(value, key, out)
    return out


def _text(node) -> str:
    """Flatten a YouTube text node (``simpleText`` or ``runs``)."""
    if not isinstance(node, dict):
        return ""
    if "simpleText" in node:
        return node["simpleText"]
    runs = node.get("runs")
    if isinstance(runs, list):
        return "".join(run.get("text", "") for run in runs if isinstance(run, dict))
    return ""


def _approx_int(raw: str) -> int | None:
    """"1.9M" -> 1900000. Returns None when the text is not a count."""
    if not raw:
        return None
    match = ABBREVIATED.match(raw.strip())
    if not match:
        match = COUNT_IN_TEXT.search(raw)
        if not match:
            return None
    number, suffix = match.group(1), match.group(2)
    try:
        value = float(number.replace(",", ""))
    except ValueError:
        return None
    if suffix:
        value *= SCALE_SUFFIXES.get(suffix.upper(), 1)
    return int(round(value))


def _unwrap(url: str) -> str:
    """Turn a youtube.com/redirect wrapper back into the real destination."""
    if not url:
        return url
    if "youtube.com/redirect" not in url:
        return url
    try:
        target = parse_qs(urlparse(url).query).get("q")
        return unquote(target[0]) if target else url
    except ValueError:
        return url


def _links_from_runs(node) -> list[str]:
    links: list[str] = []
    runs = (node or {}).get("runs") or []
    for run in runs:
        if not isinstance(run, dict):
            continue
        endpoint = ((run.get("navigationEndpoint") or {}).get("urlEndpoint") or {})
        url = _unwrap(endpoint.get("url", ""))
        if url and url not in links:
            links.append(url)
    return links


def _best_thumbnail(node) -> str | None:
    thumbs = ((node or {}).get("thumbnails") or [])
    if not thumbs:
        return None
    best = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))
    url = best.get("url") or ""
    return ("https:" + url) if url.startswith("//") else (url or None)


def _parse_poll(poll: dict) -> dict:
    """Choices and the total. The split is not available logged out."""
    choices = []
    for choice in poll.get("choices") or []:
        choices.append(_text(choice.get("text")))
    total_text = _text(poll.get("totalVotes"))
    return {
        "type": poll.get("type"),
        "choices": choices,
        "choiceCount": len(choices),
        "totalVotesText": total_text,
        "totalVotesApprox": _approx_int(total_text),
        "votesPerChoice": None,
        "votesPerChoiceNote": "YouTube reveals the per-choice split only to a "
                              "signed-in account that has voted. Logged out, the "
                              "payload carries a sign-in prompt where the "
                              "percentage would be.",
    }


def _parse_attachment(attachment: dict) -> dict:
    """Whatever is bolted onto a post: images, a video, a poll, or nothing."""
    if not attachment:
        return {"attachmentType": "none", "images": [], "video": None, "poll": None}

    if "pollRenderer" in attachment:
        return {"attachmentType": "poll", "images": [], "video": None,
                "poll": _parse_poll(attachment["pollRenderer"])}

    if "backstageImageRenderer" in attachment:
        image = _best_thumbnail((attachment["backstageImageRenderer"] or {}).get("image"))
        return {"attachmentType": "image", "images": [image] if image else [],
                "video": None, "poll": None}

    if "postMultiImageRenderer" in attachment:
        images = []
        for item in (attachment["postMultiImageRenderer"] or {}).get("images") or []:
            url = _best_thumbnail((item.get("backstageImageRenderer") or {}).get("image"))
            if url:
                images.append(url)
        return {"attachmentType": "multi-image", "images": images,
                "video": None, "poll": None}

    if "videoRenderer" in attachment:
        video = attachment["videoRenderer"] or {}
        return {
            "attachmentType": "video",
            "images": [],
            "video": {
                "videoId": video.get("videoId"),
                "title": _text(video.get("title")),
                "url": f"https://www.youtube.com/watch?v={video.get('videoId')}"
                       if video.get("videoId") else None,
                "viewCountText": _text(video.get("viewCountText")),
                "publishedTimeText": _text(video.get("publishedTimeText")),
            },
            "poll": None,
        }

    return {"attachmentType": next(iter(attachment), "unknown"),
            "images": [], "video": None, "poll": None}


def parse_posts(body: str) -> list[dict]:
    """Every community post on one page, in the order the channel posted them."""
    if UNAVAILABLE_MARKER in body:
        raise CommunityUnavailable(UNAVAILABLE_MARKER)

    data = extract_json_blob(body, "ytInitialData")
    if data is None:
        return []

    posts: list[dict] = []
    for raw in walk(data, "backstagePostRenderer"):
        if not isinstance(raw, dict):
            continue

        content = raw.get("contentText") or {}
        vote_text = _text(raw.get("voteCount"))
        vote_label = (((raw.get("voteCount") or {}).get("accessibility") or {})
                      .get("accessibilityData") or {}).get("label", "")
        author_endpoint = ((raw.get("authorEndpoint") or {}).get("browseEndpoint") or {})
        attachment = _parse_attachment(raw.get("backstageAttachment") or {})
        published = _text(raw.get("publishedTimeText"))

        posts.append({
            "postId": raw.get("postId"),
            "postUrl": f"https://www.youtube.com/post/{raw.get('postId')}"
                       if raw.get("postId") else None,
            "authorName": _text(raw.get("authorText")),
            "channelId": author_endpoint.get("browseId"),
            "channelUrl": ("https://www.youtube.com" + author_endpoint["canonicalBaseUrl"])
                          if author_endpoint.get("canonicalBaseUrl") else None,
            "text": _text(content),
            "textLength": len(_text(content)),
            "links": _links_from_runs(content),
            "publishedTimeText": published,
            "isEdited": "(edited)" in published,
            "likeCountText": vote_text,
            "likeCountApprox": _approx_int(vote_text or vote_label),
            "likeCountIsApprox": True,
            **attachment,
        })
    return posts


def parse_continuation(body: str) -> str | None:
    """The token for the next page of posts, if the page offered one."""
    data = extract_json_blob(body, "ytInitialData")
    if data is None:
        return None
    for item in walk(data, "continuationItemRenderer"):
        token = (((item or {}).get("continuationEndpoint") or {})
                 .get("continuationCommand") or {}).get("token")
        if token:
            return token
    return None
