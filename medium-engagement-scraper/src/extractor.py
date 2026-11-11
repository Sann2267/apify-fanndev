"""Apollo-cache and RSS parsers for medium.com.

The Apollo cache is **normalised**: a post points at its author and publication
with ``{"__ref": "User:14f8b20ac0d7"}`` instead of embedding them. Emitting
those refs verbatim would ship pointers into a dataset, so ``_resolve`` walks
them into the values they name -- bounded in depth, because the cache contains
cycles (a post refers to its author, whose entry refers back to posts).

The hollow-record guard here matters as much as the parsing. A Medium
publication page seeds its cache with 167 post references that carry only
``__typename`` and ``id``; counting keys would report 167 articles and emit 167
empty rows. ``parse_apollo_posts`` keeps only entries that actually carry a
title, and the caller is told how many were dropped.
"""

import json
import re
from datetime import datetime, timezone
from xml.etree import ElementTree

APOLLO_ASSIGN = re.compile(r"__APOLLO_STATE__\s*=\s*\{")

# The feed's namespaced elements. Without these, item.find("dc:creator")
# silently returns None and every article looks anonymous.
NAMESPACES = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "atom": "http://www.w3.org/2005/Atom",
}
HTML_TAG = re.compile(r"<[^>]+>")


class NoApolloState(Exception):
    """The page carried no Apollo cache."""


def extract_apollo(html: str) -> dict:
    """Pull ``window.__APOLLO_STATE__`` out of the page.

    A balanced-brace walk rather than a regex, because the cache is 160 KB of
    nested JSON containing every bracket character inside strings
    (`.ai/skills/balanced-brace-json.md`).
    """
    m = APOLLO_ASSIGN.search(html)
    if not m:
        raise NoApolloState(
            "no window.__APOLLO_STATE__ on the page -- Medium served a variant this "
            "parser has not seen, or the page is a redirect shell"
        )

    start = m.end() - 1
    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(html)):
        char = html[i]
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
                    return json.loads(html[start : i + 1])
                except json.JSONDecodeError as exc:
                    raise NoApolloState(f"Apollo cache found but unparseable: {exc}") from exc

    raise NoApolloState("Apollo cache assignment found but never closed")


def _resolve(value, cache: dict, depth: int = 0):
    """Replace ``{"__ref": "User:x"}`` pointers with the entries they name.

    Depth-bounded on purpose: the cache is cyclic, so an unbounded walk would
    not terminate.
    """
    if depth > 3:
        return None
    if isinstance(value, dict):
        ref = value.get("__ref")
        if isinstance(ref, str):
            return _resolve(cache.get(ref), cache, depth + 1)
        return {k: _resolve(v, cache, depth + 1) for k, v in value.items() if k != "__typename"}
    if isinstance(value, list):
        return [_resolve(v, cache, depth + 1) for v in value]
    return value


def _iso_ms(value) -> str | None:
    """Medium publishes epoch **milliseconds**."""
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (TypeError, ValueError, OSError):
        return None


def parse_apollo_posts(html: str, source_label: str, input_value: str) -> tuple[list[dict], int]:
    """Every usable post in the page's Apollo cache.

    Returns ``(records, hollow_count)``. A hollow entry is a post reference
    with no title -- see the module docstring.
    """
    cache = extract_apollo(html)
    records: list[dict] = []
    hollow = 0

    for key, entry in cache.items():
        if not key.startswith("Post:") or not isinstance(entry, dict):
            continue
        if not entry.get("title"):
            hollow += 1
            continue

        creator = _resolve(entry.get("creator"), cache) or {}
        collection = _resolve(entry.get("collection"), cache) or {}
        preview = entry.get("extendedPreviewContent") or {}
        image = entry.get("previewImage") or {}
        responses = entry.get("postResponses") or {}

        records.append(
            {
                "postId": entry.get("id"),
                "title": entry.get("title"),
                "subtitle": preview.get("subtitle"),
                "url": entry.get("mediumUrl"),
                "slug": entry.get("uniqueSlug"),
                "clapCount": entry.get("clapCount"),
                "responseCount": responses.get("count"),
                "isPaywalled": entry.get("isLocked"),
                "visibility": entry.get("visibility"),
                "isSeries": entry.get("isSeries"),
                "publishedAt": _iso_ms(entry.get("firstPublishedAt")),
                "updatedAt": _iso_ms(entry.get("latestPublishedAt")),
                "publishedAtEpochMs": entry.get("firstPublishedAt"),
                "authorName": creator.get("name"),
                "authorUsername": creator.get("username"),
                "authorId": creator.get("id"),
                "authorBio": creator.get("bio"),
                "authorFollowers": (creator.get("socialStats") or {}).get("followerCount")
                if isinstance(creator.get("socialStats"), dict)
                else None,
                "publicationName": collection.get("name"),
                "publicationSlug": collection.get("slug"),
                "publicationId": collection.get("id"),
                "tags": [t.get("id") for t in (_resolve(entry.get("tags"), cache) or []) if t],
                "previewImageAlt": image.get("alt"),
                "previewImageId": image.get("id"),
                "hasFullContent": bool(preview.get("isFullContent")),
                "_query": input_value,
                "_source": source_label,
            }
        )

    return records, hollow


def parse_post_detail(html: str, input_value: str) -> dict:
    """A single article: its metadata plus whatever body Medium served.

    Medium serves only the opening paragraphs for a paywalled article, so
    ``isTruncated`` is set from the source's own ``isFullContent`` flag rather
    than guessed from the body length.
    """
    cache = extract_apollo(html)

    post = None
    for key, entry in cache.items():
        if key.startswith("Post:") and isinstance(entry, dict) and entry.get("title"):
            post = entry
            break
    if post is None:
        # Fall back to the thin entry, which still carries url and author.
        for key, entry in cache.items():
            if key.startswith("Post:") and isinstance(entry, dict) and entry.get("mediumUrl"):
                post = entry
                break
    if post is None:
        raise NoApolloState("the page's Apollo cache carried no post entry")

    paragraphs = [
        {
            "type": entry.get("type"),
            "text": entry.get("text"),
            "href": entry.get("href"),
        }
        for key, entry in cache.items()
        if key.startswith("Paragraph:") and isinstance(entry, dict)
    ]
    creator = _resolve(post.get("creator"), cache) or {}
    collection = _resolve(post.get("collection"), cache) or {}
    preview = post.get("extendedPreviewContent") or {}

    body = "\n\n".join(p["text"] for p in paragraphs if p.get("text"))
    return {
        "postId": post.get("id"),
        "title": post.get("title") or (paragraphs[0]["text"] if paragraphs else None),
        "subtitle": preview.get("subtitle"),
        "url": post.get("mediumUrl"),
        "slug": post.get("uniqueSlug"),
        "clapCount": post.get("clapCount"),
        "responseCount": (post.get("postResponses") or {}).get("count"),
        "isPaywalled": post.get("isLocked"),
        "publishedAt": _iso_ms(post.get("firstPublishedAt")),
        "authorName": creator.get("name"),
        "authorUsername": creator.get("username"),
        "publicationName": collection.get("name"),
        "publicationSlug": collection.get("slug"),
        "paragraphCount": len(paragraphs),
        "bodyText": body or None,
        "paragraphs": paragraphs,
        # Medium truncates a **paywalled** article to its opening paragraphs
        # (8 paragraphs / 1.2k characters, against 77 / 14k for a free one).
        #
        # ``extendedPreviewContent.isFullContent`` is NOT the signal to use
        # here: it describes the preview *card*, so it reads False even on a
        # free article served complete, and using it marked 77-paragraph
        # articles as truncated. The paywall flag is what actually tracks
        # whether the body was cut.
        "isTruncated": bool(post.get("isLocked")),
        "_query": input_value,
        "_source": "medium-post-apollo",
    }


def parse_feed(xml: str, source_label: str, input_value: str) -> list[dict]:
    """Parse an RSS feed.

    Used where the Apollo cache cannot help: a publication's HTML page seeds
    167 hollow post references and carries no usable article at all, while its
    feed carries 10 complete ones including the body HTML.

    Parsed with a real **XML** parser, not the HTML one used elsewhere in this
    module. An HTML parser flattens this document: namespaced elements such as
    ``dc:creator`` never match, ``CDATA`` sections leak their ``<![CDATA[``
    wrapper into the title, and a per-item ``title`` lookup climbs out of the
    item and returns the channel's title instead -- which is exactly what the
    first version of this function did.
    """
    try:
        root = ElementTree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    except ElementTree.ParseError as exc:
        raise ValueError(f"the feed is not parseable XML: {exc}") from exc

    records: list[dict] = []

    for item in root.iter("item"):
        def text(tag: str) -> str | None:
            node = item.find(tag, NAMESPACES) if ":" in tag else item.find(tag)
            value = (node.text or "").strip() if node is not None and node.text else ""
            return value or None

        # Medium puts the full article in content:encoded, but not for every
        # post -- some carry only a short <description> preview (77 characters
        # against 7,536 for a full one in the same feed). Which one a row got
        # is recorded, so nobody mistakes a preview for the article.
        content_node = item.find("content:encoded", NAMESPACES)
        content_source = "content:encoded"
        if content_node is None or not (content_node.text or "").strip():
            content_node = item.find("description")
            content_source = "description"
        content_html = (
            (content_node.text or "").strip()
            if content_node is not None and content_node.text
            else None
        )
        if not content_html:
            content_source = None
        categories = [
            (c.text or "").strip() for c in item.findall("category") if (c.text or "").strip()
        ]
        link = text("link")

        records.append(
            {
                "postId": (text("guid") or "").split("/")[-1] or None,
                "title": text("title"),
                "url": link,
                "authorName": text("dc:creator"),
                "publishedAtRaw": text("pubDate"),
                "updatedAtRaw": text("atom:updated"),
                "tags": categories,
                "contentHtml": content_html,
                "contentSource": content_source,
                "isContentFull": content_source == "content:encoded",
                "contentText": (
                    HTML_TAG.sub(" ", content_html).replace("&nbsp;", " ").strip()
                    if content_html
                    else None
                ),
                # The feed publishes no engagement figures at all, so these are
                # explicitly null rather than absent -- a consumer joining feed
                # rows with tag rows must be able to see which is which.
                "clapCount": None,
                "responseCount": None,
                "_query": input_value,
                "_source": source_label,
            }
        )

    return records


def extract_error(identifier: str, reason: str, detail: str) -> dict:
    return {
        "_query": identifier,
        "error": reason,
        "errorDetail": detail,
        "_source": "error",
    }


def wrap_reference(url: str, available: bool, note: str, sample: dict | None = None, profile: str | None = None) -> dict:
    return {
        "probedUrl": url,
        "isAvailable": available,
        "note": note,
        "winningTlsProfile": profile,
        "sample": sample or {},
        "_source": "reference",
    }
