"""Input normalisation + dataset envelope. No network here -- pure functions.

Users paste bsky.app web URLs; the XRPC API speaks `at://` URIs and
handles/DIDs. Everything that translates between those two worlds lives
in this module so the mode handlers in main.py stay thin.
"""

import re
from datetime import datetime, timezone

# https://bsky.app/profile/<actor>[/post|/feed|/lists/<rkey>]
_PROFILE_URL = re.compile(
    r"(?:https?://)?(?:www\.)?bsky\.app/profile/"
    r"(?P<actor>[^/?#\s]+)"
    r"(?:/(?P<kind>post|feed|lists)/(?P<rkey>[^/?#\s]+))?",
    re.I,
)
# https://bsky.app/starter-pack/<actor>/<rkey>
_STARTER_PACK_URL = re.compile(
    r"(?:https?://)?(?:www\.)?bsky\.app/starter-pack(?:-short)?/"
    r"(?P<actor>[^/?#\s]+)/(?P<rkey>[^/?#\s]+)",
    re.I,
)

_COLLECTION_FOR_KIND = {
    "post": "app.bsky.feed.post",
    "feed": "app.bsky.feed.generator",
    "lists": "app.bsky.graph.list",
}


class UnexpectedShape(Exception):
    """Upstream returned 200 but not the documented shape.

    Raised rather than returning a partial record -- a scraper that
    silently emits `{}` for a renamed field corrupts datasets quietly,
    which is worse than crashing loudly.
    """


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------- inputs
def parse_actor(value: str) -> str:
    """Accept a handle, a DID, or any bsky.app profile URL -> actor id.

    The XRPC `actor` param takes a handle or a DID interchangeably, so no
    network round-trip is needed to normalise one."""
    value = (value or "").strip()
    if not value:
        raise ValueError("empty actor input")
    if value.startswith("did:"):
        return value

    match = _PROFILE_URL.search(value)
    if match:
        return match.group("actor")

    # Bare handle, with or without a leading '@'.
    return value.lstrip("@")


def parse_at_uri(value: str, expect_kind: str = "post") -> str | None:
    """Accept an `at://` URI or a bsky.app URL -> `at://` URI.

    Returns None when `value` carries no record reference (e.g. a plain
    profile URL passed to a post-shaped mode) so the caller can emit a
    precise diagnostic row instead of guessing.

    The returned URI may still embed a *handle* rather than a DID --
    this function stays pure/offline. Callers MUST pass it through
    BlueskyClient.to_did_uri before hitting getLikes / getQuotes /
    getPosts / getRepostedBy, which mis-handle handle-based authorities
    (silent empty array, or a 500)."""
    value = (value or "").strip()
    if not value:
        return None
    if value.startswith("at://"):
        return value

    if expect_kind == "starterpack":
        match = _STARTER_PACK_URL.search(value)
        if match:
            return (
                f"at://{match.group('actor')}"
                f"/app.bsky.graph.starterpack/{match.group('rkey')}"
            )
        return None

    match = _PROFILE_URL.search(value)
    if not match or not match.group("kind"):
        return None
    collection = _COLLECTION_FOR_KIND[match.group("kind").lower()]
    return f"at://{match.group('actor')}/{collection}/{match.group('rkey')}"


def rkey_of(at_uri: str) -> str:
    return at_uri.rsplit("/", 1)[-1]


def web_url_for_post(post: dict) -> str | None:
    """Rebuild the human-facing bsky.app permalink for a post view.

    Convenience only -- added under a non-underscore key so it does not
    pollute the reserved `_*` envelope namespace."""
    try:
        handle = post["author"]["handle"]
        return f"https://bsky.app/profile/{handle}/post/{rkey_of(post['uri'])}"
    except (KeyError, TypeError):
        return None


# ------------------------------------------------------------- envelope
def envelope(raw: dict, source: str, input_value: str, record_type: str) -> dict:
    """Raw passthrough under the portfolio envelope.

    Upstream field names are preserved verbatim -- downstream consumers
    normalise. `recordType` discriminates the shapes a single run can
    emit (see .ai/conventions/dataset-envelope.md)."""
    if not isinstance(raw, dict):
        raise UnexpectedShape(f"{record_type}: expected dict, got {type(raw).__name__}")
    return {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "recordType": record_type,
        **raw,
    }


def error_record(input_value: str, error_kind: str, detail: str = "") -> dict:
    """Failures get a row too -- a missing row looks like a crash."""
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "recordType": "ERROR",
        "_error": error_kind,
        "_errorDetail": detail[:1000],
    }


# ------------------------------------------------------------- reshapes
def flatten_feed(feed: list[dict]) -> list[dict]:
    """`getAuthorFeed`/`getFeed`/`getListFeed` wrap each post in a
    feedViewPost: {post, reply?, reason?}. Lift `post` to the top level
    and keep the wrapper's context as sibling keys, so every POST record
    in the dataset has one consistent shape regardless of which feed
    method produced it."""
    out: list[dict] = []
    for item in feed:
        post = item.get("post")
        if not isinstance(post, dict):
            raise UnexpectedShape(
                f"feed item missing 'post' object, got keys {list(item.keys())}"
            )
        record = dict(post)
        if item.get("reason"):
            record["feedReason"] = item["reason"]
        if item.get("reply"):
            record["feedReplyContext"] = item["reply"]
        url = web_url_for_post(post)
        if url:
            record["webUrl"] = url
        out.append(record)
    return out


def flatten_thread(node: dict, max_nodes: int) -> tuple[dict | None, list[dict]]:
    """Walk a threadViewPost depth-first -> (root post, reply posts).

    Replies are returned flat with `replyDepth` so consumers can rebuild
    the tree without dealing with unbounded nesting in a dataset cell.
    Blocked/not-found nodes carry a `$type` other than threadViewPost;
    they are skipped rather than crashing the walk."""
    if node.get("$type") not in (None, "app.bsky.feed.defs#threadViewPost"):
        return None, []

    root_post = node.get("post")
    if not isinstance(root_post, dict):
        raise UnexpectedShape(f"thread root missing 'post', keys={list(node.keys())}")

    replies: list[dict] = []

    def walk(current: dict, depth: int):
        for child in current.get("replies") or []:
            if len(replies) >= max_nodes:
                return
            if child.get("$type") not in (None, "app.bsky.feed.defs#threadViewPost"):
                continue
            post = child.get("post")
            if not isinstance(post, dict):
                continue
            record = dict(post)
            record["replyDepth"] = depth
            url = web_url_for_post(post)
            if url:
                record["webUrl"] = url
            replies.append(record)
            walk(child, depth + 1)

    walk(node, 1)

    root = dict(root_post)
    url = web_url_for_post(root_post)
    if url:
        root["webUrl"] = url
    return root, replies
