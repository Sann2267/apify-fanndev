"""Structural parser for Facebook group pages and their feed payloads.

Facebook does not hand back a group post as one tidy object. A single post is
scattered across the payload: the body text sits in one node, the permalink and
timestamp in another, the author in a third, the reaction and comment counts in a
fourth. Walking a path to stitch them back together breaks the first time
Facebook reshuffles its renderers, which it does often.

What is stable is that every one of those nodes carries a base64 `id` that
decodes to the post it belongs to:

    UzpfSTEwMDAwMTk3NjQyNTIyODpWSzozOTMyNDIyMzAwMzg5MDAx
        -> "S:_I100001976425228:VK:3932422300389001"
    ZmVlZGJhY2s6MzkzMjQyMjMwMDM4OTAwMQ==
        -> "feedback:3932422300389001"

Both end in the post id. So the parser makes one pass over every dict in the
payload, decodes whatever id it finds, and files each field under the post it
names. Nodes that name no post are ignored rather than guessed at.
"""

from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from src.fbcore import dedupe, find_nodes, iter_json_blocks, og_tag, text_of, walk

POST_ID_IN_ID = re.compile(r"(?:^|:)(\d{6,})$")
GROUP_URL = re.compile(r"facebook\.com/groups/([^/?#]+)", re.I)


def _decode(node_id: Any) -> str | None:
    if not isinstance(node_id, str) or len(node_id) < 8:
        return None
    try:
        decoded = base64.b64decode(node_id + "==", validate=False).decode("utf-8", "ignore")
    except (binascii.Error, ValueError):
        return None
    match = POST_ID_IN_ID.search(decoded)
    return match.group(1) if match else None


def _iso(stamp: Any) -> str | None:
    if not isinstance(stamp, (int, float)) or isinstance(stamp, bool):
        return None
    if not 946_684_800 < stamp < 4_102_444_800:
        return None
    return (
        datetime.fromtimestamp(int(stamp), tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _count(node: Any) -> int | None:
    """Facebook writes counts as a bare int, a string, or {count: n}."""
    if isinstance(node, bool):
        return None
    if isinstance(node, int):
        return node
    if isinstance(node, str):
        try:
            return int(node.replace(",", ""))
        except ValueError:
            return None
    if isinstance(node, dict):
        return _count(node.get("count"))
    return None


def group_ref(value: str) -> str | None:
    """Reduce a group URL, slug or numeric id to the path segment Facebook uses."""
    value = (value or "").strip()
    if not value:
        return None
    match = GROUP_URL.search(value)
    if match:
        value = match.group(1)
    value = value.strip("/").split("?")[0].split("#")[0]
    return value or None


def parse_group_meta(html: str) -> dict:
    """Name, id, vanity, privacy and member count from the group shell."""
    # og:title arrives as "React.JS developers -2023 | Facebook"; the suffix is
    # chrome, not part of the group's name.
    raw_name = og_tag(html, "og:title")
    name = re.sub(r"\s*\|\s*Facebook\s*$", "", raw_name).strip() if raw_name else None

    meta: dict[str, Any] = {
        "groupId": None,
        "groupName": name or None,
        "groupVanity": None,
        "privacy": None,
        "privacyDescription": None,
        "memberCountLabel": None,
        "memberCount": None,
        "groupDescription": og_tag(html, "og:description"),
    }

    for block in iter_json_blocks(html):
        for node in walk(block):
            if meta["groupVanity"] is None and isinstance(node.get("group_address"), str):
                meta["groupVanity"] = node["group_address"]
            if meta["groupId"] is None and isinstance(node.get("target_group"), dict):
                target = node["target_group"]
                if isinstance(target.get("id"), str):
                    meta["groupId"] = target["id"]
                if meta["privacy"] is None and isinstance(target.get("visibility"), str):
                    meta["privacy"] = target["visibility"]
            if meta["memberCountLabel"] is None:
                profiles = node.get("group_member_profiles")
                if isinstance(profiles, dict) and profiles.get("formatted_count_text"):
                    meta["memberCountLabel"] = profiles["formatted_count_text"]
            if meta["privacyDescription"] is None and isinstance(node.get("privacy_info"), dict):
                meta["privacyDescription"] = text_of(node["privacy_info"].get("description"))
            if meta["privacy"] is None and isinstance(node.get("visibility"), str):
                meta["privacy"] = node["visibility"]

    if meta["memberCountLabel"]:
        from src.fbcore import parse_count

        meta["memberCount"] = parse_count(meta["memberCountLabel"])
    return meta


def _blank_post() -> dict:
    return {
        "postId": None,
        "postUrl": None,
        "text": None,
        "createdAt": None,
        "createdAtIso": None,
        "authorName": None,
        "authorId": None,
        "authorUrl": None,
        "reactionCount": None,
        "commentCount": None,
        "shareCount": None,
        "attachmentUrls": [],
        "attachmentCount": 0,
        "commentsServed": 0,
        "comments": [],
    }


FEEDBACK_MARKERS = (
    "comet_ufi_summary_and_actions_renderer",
    "i18n_reaction_count",
    "owning_profile",
    "comments",
    "share_count",
)


def _is_feedback_container(node: dict) -> bool:
    return any(marker in node for marker in FEEDBACK_MARKERS)


def _absorb_engagement(entry: dict, node: dict) -> None:
    """Fill reaction/comment/share counts and the author from a feedback subtree."""
    for inner in walk(node):
        if entry["reactionCount"] is None and "i18n_reaction_count" in inner:
            entry["reactionCount"] = _count(inner.get("i18n_reaction_count"))
        if entry["reactionCount"] is None and isinstance(inner.get("reaction_count"), dict):
            entry["reactionCount"] = _count(inner["reaction_count"])
        if entry["commentCount"] is None and isinstance(inner.get("comments"), dict):
            entry["commentCount"] = _count(inner["comments"].get("total_count"))
        if entry["shareCount"] is None and "share_count" in inner:
            entry["shareCount"] = _count(inner.get("share_count"))
        profile = inner.get("owning_profile")
        if entry["authorName"] is None and isinstance(profile, dict) and profile.get("name"):
            entry["authorName"] = profile.get("name")
            entry["authorId"] = profile.get("id")
            if profile.get("id"):
                entry["authorUrl"] = f"https://www.facebook.com/{profile['id']}"


def collect_posts(payload: Any) -> dict[str, dict]:
    """One pass over the payload, filing every field under the post it names."""
    posts: dict[str, dict] = {}

    def slot(post_id: str) -> dict:
        entry = posts.setdefault(post_id, _blank_post())
        entry["postId"] = post_id
        return entry

    for node in walk(payload):
        node_id = node.get("id")
        post_id = _decode(node_id) if isinstance(node_id, str) else None

        # A post's own story node names itself outright.
        if isinstance(node.get("post_id"), str):
            post_id = node["post_id"]

        if not post_id:
            continue

        entry = slot(post_id)
        if entry["postUrl"] is None:
            url = node.get("permalink_url") or node.get("url")
            if isinstance(url, str) and "/groups/" in url:
                entry["postUrl"] = url
        message = node.get("message")
        if entry["text"] is None and isinstance(message, dict):
            text = message.get("text")
            if isinstance(text, str) and text.strip():
                entry["text"] = text
        if entry["createdAt"] is None and isinstance(node.get("creation_time"), int):
            entry["createdAt"] = node["creation_time"]

        # Engagement and author live *inside* the feedback node rather than on
        # it: the renderer wraps them in comet_ufi_summary_and_actions_renderer,
        # and the wrapper carries no id of its own. Reading only the top level
        # returns null comment counts for posts that plainly have comments, so
        # the feedback node's own subtree is scanned once.
        if _is_feedback_container(node):
            _absorb_engagement(entry, node)

    for entry in posts.values():
        entry["createdAtIso"] = _iso(entry["createdAt"])
    return posts


def attach_media(payload: Any, posts: dict[str, dict]) -> None:
    """Photo and video URLs, filed under whichever post the attachment names."""
    for node in walk(payload):
        post_id = _decode(node.get("id")) if isinstance(node.get("id"), str) else None
        if not post_id or post_id not in posts:
            continue
        urls: list[str] = []
        for candidate in walk(node):
            for key in ("uri", "image_url", "playable_url", "browser_native_hd_url"):
                value = candidate.get(key)
                if isinstance(value, str) and value.startswith("http") and (
                    "fbcdn" in value or "scontent" in value
                ):
                    urls.append(value)
        if urls:
            merged = dedupe(posts[post_id]["attachmentUrls"] + urls)
            posts[post_id]["attachmentUrls"] = merged
            posts[post_id]["attachmentCount"] = len(merged)


def parse_feed(payload: Any) -> tuple[list[dict], str | None, bool]:
    """A feed payload -> (posts, end_cursor, has_next_page).

    Posts with neither text nor a permalink are dropped: they are the feed's
    section headers and promo units, not somebody's post.
    """
    posts = collect_posts(payload)
    attach_media(payload, posts)

    cursor: str | None = None
    has_next = False
    for node in find_nodes(payload, "page_info"):
        info = node["page_info"]
        if isinstance(info, dict) and info.get("end_cursor") and info.get("has_next_page"):
            cursor = info["end_cursor"]
            has_next = True
            break
    if cursor is None:
        for node in find_nodes(payload, "page_info"):
            info = node["page_info"]
            if isinstance(info, dict) and info.get("end_cursor"):
                cursor = info["end_cursor"]
                has_next = bool(info.get("has_next_page"))
                break

    real = [p for p in posts.values() if p["text"] or p["postUrl"]]
    real.sort(key=lambda p: p["createdAt"] or 0, reverse=True)
    return real, cursor, has_next


def parse_comments(payload: Any) -> list[dict]:
    """Comment bodies, wherever Facebook served them.

    On a logged-out request Facebook publishes the *count* of comments on a group
    post but not the bodies -- `comments.edges` comes back empty while
    `comments.total_count` is populated, and the UFI renderer is the
    `Unauthenticated` variant. This function therefore returns an empty list for
    group posts today. It is not dead code: the same shape is served for other
    surfaces, and the actor reports what was actually returned rather than
    asserting there are no comments.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for node in walk(payload):
        body = node.get("body")
        if not isinstance(body, dict) or not isinstance(body.get("text"), str):
            continue
        author = node.get("author")
        author = author if isinstance(author, dict) else {}
        comment_id = node.get("id") if isinstance(node.get("id"), str) else None
        key = comment_id or body["text"][:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "commentId": comment_id,
                "commentText": body["text"],
                "commentAuthorName": author.get("name"),
                "commentAuthorId": author.get("id"),
                "commentCreatedAt": node.get("created_time"),
                "commentCreatedAtIso": _iso(node.get("created_time")),
                "commentUrl": node.get("url") if isinstance(node.get("url"), str) else None,
            }
        )
    return out


def matches_filters(post: dict, filters: dict) -> bool:
    if filters.get("onlyWithText") and not (post.get("text") or "").strip():
        return False
    needle = (filters.get("textContains") or "").strip().lower()
    if needle and needle not in (post.get("text") or "").lower():
        return False
    minimum = filters.get("minReactions")
    if isinstance(minimum, int):
        value = post.get("reactionCount")
        # A post whose reaction count Facebook withheld cannot be shown to clear
        # the bar, so it is dropped rather than admitted on a guess.
        if not isinstance(value, int) or value < minimum:
            return False
    minimum = filters.get("minComments")
    if isinstance(minimum, int):
        value = post.get("commentCount")
        if not isinstance(value, int) or value < minimum:
            return False
    since = filters.get("postedAfterEpoch")
    if isinstance(since, int):
        stamp = post.get("createdAt")
        if not isinstance(stamp, int) or stamp < since:
            return False
    return True


def summarise(posts: Iterable[dict]) -> dict:
    posts = list(posts)
    reactions = [p["reactionCount"] for p in posts if isinstance(p.get("reactionCount"), int)]
    comments = [p["commentCount"] for p in posts if isinstance(p.get("commentCount"), int)]
    authors = {p.get("authorName") for p in posts if p.get("authorName")}
    newest = max((p["createdAt"] for p in posts if p.get("createdAt")), default=None)
    oldest = min((p["createdAt"] for p in posts if p.get("createdAt")), default=None)
    return {
        "postsCollected": len(posts),
        "distinctAuthors": len(authors),
        "totalReactions": sum(reactions) if reactions else 0,
        "totalComments": sum(comments) if comments else 0,
        "commentBodiesCollected": sum(p.get("commentsServed") or 0 for p in posts),
        "newestPostIso": _iso(newest),
        "oldestPostIso": _iso(oldest),
    }
