"""Fetching one group's feed: the rendered shell, then Facebook's own queries.

A logged-out group page renders as a ~330 KB shell with the feed marked
`"complete": false` -- Facebook streams the posts to the client afterwards. So
unlike a page, a group yields nothing useful from the HTML alone. What the HTML
does carry is the relay preloader block, which publishes the id *and the exact
variables* of the query the browser is about to run:

    {"queryID": "28192873003712398",
     "variables": {"groupID": ..., "regular_stories_count": 2, ...},
     "queryName": "CometGroupDiscussionRootSuccessQuery"}

Replaying that query with a larger `regular_stories_count` returns the first
batch of posts. Its `end_cursor` then feeds
`GroupsCometFeedRegularStoriesPaginationQuery`, whose id lives in the page's JS
bundle. Neither id is hard-coded; both are read at runtime, because a pinned id
fails silently and a silent failure here looks like "this group has no posts".
"""

from __future__ import annotations

from typing import Any

from src.fbcore import BlockedError, FacebookSession, harvest_preloaders, is_hollow
from src.parser import parse_feed, parse_group_meta

BASE = "https://www.facebook.com/groups/"
FEED_QUERY = "CometGroupDiscussionRootSuccessQuery"
PAGINATION_QUERY = "GroupsCometFeedRegularStoriesPaginationQuery"

# How many posts to ask for in one call. Facebook's own page asks for 2-3; the
# server honours a larger number, and a larger batch means fewer requests.
BATCH = 12

# Below this, the page is Facebook's REDUCED tier rather than a real group
# page. Measured 2026-09-23: a public group served to a residential address
# returned 1.16 MB, while the same group from an Apify datacentre address came
# back with no feed at all. 600 KB sits clear of both.
REDUCED_PAGE_BYTES = 600_000


class GroupUnavailable(RuntimeError):
    """The group does not exist, or is not readable without logging in."""


async def fetch_group(session: FacebookSession, ref: str) -> tuple[str, dict]:
    """Fetch the group shell and read its metadata.

    Facebook answers HTTP 200 for a group that does not exist, and the same 200
    for a private one -- both come back as the ~330 KB shell. Size is what tells
    them apart from a readable group, so it is checked before anything else.
    """
    url = BASE + ref
    html = await session.get_html(url)
    if is_hollow(html):
        raise GroupUnavailable(
            "Facebook served the empty shell (~330 KB). The group is private, "
            "does not exist, or is not readable without logging in."
        )
    meta = parse_group_meta(html)
    meta["groupUrl"] = url
    meta["groupRef"] = ref
    return html, meta


async def fetch_posts(
    session: FacebookSession,
    html: str,
    url: str,
    max_posts: int,
    log: Any = None,
) -> tuple[list[dict], dict]:
    """The group's posts, newest first, up to `max_posts`."""
    preloaders = harvest_preloaders(html)
    if FEED_QUERY not in preloaders:
        # Two very different causes land here and the page size tells them
        # apart. Facebook answers a datacentre address with a REDUCED page --
        # HTTP 200, roughly a third of a megabyte, no feed and no counts --
        # which is indistinguishable from a genuinely private feed unless you
        # look at the size. A real public group page is over a megabyte.
        reduced = len(html) < REDUCED_PAGE_BYTES
        cause = (
            "The page came back at only {size:,} bytes, which is Facebook's "
            "REDUCED tier -- it serves this to addresses it does not trust, "
            "typically a datacentre IP. Enable the Apify RESIDENTIAL proxy "
            "and run again; a public group normally returns over a megabyte."
            if reduced
            else "The page came back at a full {size:,} bytes but carried no "
            "feed, so this group's posts really are not public even though "
            "its landing page is."
        ).format(size=len(html))
        raise GroupUnavailable(
            "Facebook did not preload a discussion feed for this group, so "
            "there is no query to replay. " + cause
        )

    query_id, variables = preloaders[FEED_QUERY]
    variables = dict(variables)
    variables["regular_stories_count"] = min(BATCH, max_posts)
    variables["regular_stories_stream_initial_count"] = min(BATCH, max_posts)

    payload = await session.graphql(html, FEED_QUERY, query_id, variables, referer=url)
    posts, cursor, has_next = parse_feed(payload)
    meta = {"requestsMade": 1, "paginated": False}

    if len(posts) >= max_posts or not has_next or not cursor:
        return posts[:max_posts], meta

    doc_id = await session.bundle_doc_id(html, PAGINATION_QUERY)
    if not doc_id:
        # The first batch is still a complete, honest answer.
        meta["paginationUnavailable"] = True
        return posts[:max_posts], meta

    meta["paginated"] = True
    seen = {p["postId"] for p in posts}

    while len(posts) < max_posts and has_next and cursor:
        page_vars = dict(variables)
        page_vars["cursor"] = cursor
        page_vars["count"] = BATCH
        try:
            payload = await session.graphql(
                html, PAGINATION_QUERY, doc_id, page_vars, referer=url
            )
        except BlockedError as exc:
            meta["paginationStoppedBy"] = str(exc)
            break
        batch, cursor, has_next = parse_feed(payload)
        meta["requestsMade"] += 1
        fresh = [p for p in batch if p["postId"] not in seen]
        if not fresh:
            break
        for post in fresh:
            seen.add(post["postId"])
        posts.extend(fresh)
        if log:
            log.info(f"  +{len(fresh)} post(s) (running total {len(posts)})")

    posts.sort(key=lambda p: p["createdAt"] or 0, reverse=True)
    return posts[:max_posts], meta


async def fetch_comments(session: FacebookSession, post: dict) -> list[dict]:
    """Whatever comment bodies Facebook serves on the post's permalink.

    Measured 2026-09-20 on logged-out requests: a group post's permalink returns
    `comments.total_count` populated and `comments.edges` empty, with the
    `UnauthenticatedUCometUFISummaryAndActionsRenderer`. Meta does not publish
    group comment bodies to signed-out clients. The count is still reported on
    every post; this call returns what was actually served, which is why the
    output carries `commentsServed` next to `commentCount` instead of pretending
    the two agree.
    """
    from src.parser import parse_comments

    url = post.get("postUrl")
    if not url:
        return []
    try:
        html = await session.get_html(url)
    except BlockedError:
        return []
    from src.fbcore import iter_json_blocks

    found: list[dict] = []
    for block in iter_json_blocks(html):
        found.extend(parse_comments(block))
    return found
