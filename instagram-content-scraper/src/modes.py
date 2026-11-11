"""Per-surface scrape logic: one coroutine per mode.

Each mode follows the same arc -- warm the entity page, read page 1 straight out
of the SSR payload, then replay the harvested persisted query for pages 2..n.
Where a surface cannot paginate anonymously the mode says so in the row's
`_warning` rather than looping pointlessly or pretending the first page is all
there is.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from src.client import BlockedError, InstagramClient, NotFoundError
from src.constants import (
    CONN_COMMENTS,
    CONN_HIGHLIGHTS,
    CONN_POSTS,
    CONN_REELS,
    ERR_EMPTY,
    ERR_GATED,
    ERR_PRIVATE,
    ERR_SHAPE,
    MODE_LOCATION,
    MODE_POST_DETAIL,
    MODE_POSTS,
    MODE_PROFILE,
    MODE_REELS,
    ORIGIN,
    PAGE_SIZE,
    ROOT_LOCATION_INFO,
    ROOT_LOCATION_TAB,
    ROOT_MEDIA,
    ROOT_USER,
    SOURCE_GRAPHQL,
    SOURCE_SSR,
)
from src.extract import (
    normalise_comment,
    normalise_highlight,
    normalise_location,
    normalise_media,
    normalise_profile,
    now_iso,
)
from src.relay import (
    RelayShapeError,
    connection_nodes,
    find_connection,
    find_preload,
    harvest_lsd,
    next_cursor,
    pick_root,
    ssr_roots,
)

logger = logging.getLogger(__name__)


def envelope(mode: str, target: str, source: str, **extra) -> dict:
    """The fields every row carries, whatever the mode."""
    row = {
        "_mode": mode,
        "_input": target,
        "_source": source,
        "_scrapedAt": now_iso(),
        "_page": None,
        "_warning": None,
        "_error": None,
        "_errorDetail": None,
    }
    row.update(extra)
    return row


async def _paginate(
    client: InstagramClient,
    html: str,
    referer: str,
    query_substring: str,
    root_key: str,
    connection_key: str,
    max_items: int,
    page_size: int = PAGE_SIZE,
) -> tuple[list[tuple[dict, int, str]], str | None]:
    """Walk a Relay connection from the SSR page onwards.

    Returns `(nodes_with_page_and_source, warning)`. The SSR page counts as page
    1, so a run capped at 12 items issues no GraphQL request at all.
    """
    roots = ssr_roots(html)
    payload = pick_root(roots, root_key, must_have=connection_key)
    if payload is None:
        raise RelayShapeError(
            f"no {root_key} payload carrying {connection_key} in the page; "
            "Instagram's logged-out SSR shape has probably changed"
        )
    connection = payload.get(connection_key)
    collected: list[tuple[dict, int, str]] = []
    seen: set[str] = set()

    def absorb(nodes: list[dict], page: int, source: str) -> bool:
        """Append nodes up to the cap. Returns True when the cap is reached."""
        for node in nodes:
            key = str(node.get("pk") or node.get("id") or id(node))
            if key in seen:
                continue
            seen.add(key)
            collected.append((node, page, source))
            if len(collected) >= max_items:
                return True
        return False

    if absorb(connection_nodes(connection), 1, SOURCE_SSR):
        return collected, None

    preload = find_preload(html, query_substring)
    lsd = harvest_lsd(html)
    if preload is None or lsd is None:
        return collected, (
            "pagination_unavailable: the page did not carry the query id or lsd "
            "token needed to request further pages, so only the server-rendered "
            "first page was collected"
        )

    cursor = next_cursor(connection)
    page = 1
    warning = None
    while cursor and len(collected) < max_items:
        page += 1
        variables = {**preload["variables"], "after": cursor, "first": page_size}
        try:
            data = await client.graphql(
                doc_id=preload["doc_id"],
                variables=variables,
                lsd=lsd,
                referer=referer,
                root_key=root_key,
            )
        except BlockedError as exc:
            warning = f"pagination_stopped_at_page_{page}: {exc}"
            logger.warning("Stopping pagination for %s: %s", referer, exc)
            break
        connection = find_connection(data.get(root_key))
        nodes = connection_nodes(connection)
        if not nodes:
            break
        before = len(collected)
        capped = absorb(nodes, page, SOURCE_GRAPHQL)
        if len(collected) == before:
            # The cursor advanced but every node repeated -- the surface is
            # looping. Stop rather than spin the retry budget away.
            warning = f"pagination_stopped_at_page_{page}: upstream repeated the previous page"
            break
        if capped:
            break
        cursor = next_cursor(connection)
    return collected, warning


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------
async def scrape_profile(client: InstagramClient, username: str, options: dict) -> list[dict]:
    url = f"{ORIGIN}/{username}/"
    html = await client.warm(url)
    roots = ssr_roots(html)
    payload = pick_root(roots, ROOT_USER, must_have="biography")
    if payload is None:
        raise RelayShapeError(
            "profile page carried no xig_user_by_username payload with a biography"
        )
    row = envelope(MODE_PROFILE, username, SOURCE_SSR, **normalise_profile(payload))
    row["_page"] = 1

    highlights_payload = pick_root(roots, ROOT_USER, must_have=CONN_HIGHLIGHTS)
    highlights = connection_nodes((highlights_payload or {}).get(CONN_HIGHLIGHTS))
    row["highlights"] = [normalise_highlight(node) for node in highlights]

    if row.get("isPrivate"):
        row["_warning"] = (
            "private_account: profile metadata is public but this account's media "
            "is not visible to a logged-out viewer"
        )
    return [row]


# ---------------------------------------------------------------------------
# posts / reels
# ---------------------------------------------------------------------------
async def _scrape_user_media(
    client: InstagramClient,
    username: str,
    options: dict,
    mode: str,
    path: str,
    query_substring: str,
    connection_key: str,
) -> list[dict]:
    url = f"{ORIGIN}/{path}"
    html = await client.warm(url)
    roots = ssr_roots(html)
    profile = pick_root(roots, ROOT_USER, must_have="biography")

    if profile is not None and profile.get("is_private"):
        return [envelope(
            mode, username, SOURCE_SSR,
            _error=ERR_PRIVATE,
            _errorDetail=f"@{username} is private; a logged-out viewer sees no media",
            username=username,
        )]

    max_items = int(options.get("maxItems") or 60)
    nodes, warning = await _paginate(
        client, html, url, query_substring, ROOT_USER, connection_key, max_items
    )
    if not nodes:
        detail = (
            f"@{username} published no {'reels' if mode == MODE_REELS else 'posts'} "
            "on this tab, or Instagram served an empty logged-out grid"
        )
        return [envelope(
            mode, username, SOURCE_SSR, _error=ERR_EMPTY, _errorDetail=detail,
            username=username,
        )]

    rows = []
    for node, page, source in nodes:
        row = envelope(mode, username, source, **normalise_media(node))
        row["_page"] = page
        row["_warning"] = warning
        if row.get("ownerUsername") is None:
            row["ownerUsername"] = username
        # Each tab withholds something the other publishes, and a consumer that
        # does not know which is which will read a null as a zero. Say so on the
        # row rather than only in the README.
        if mode == MODE_POSTS and row.get("likeCount") is None:
            row["_warning"] = "; ".join(filter(None, [
                warning,
                "engagement_not_published_on_this_surface: Instagram's logged-out "
                "profile grid omits like and comment counts. Use mode 'post_detail' "
                "on the shortcode, or mode 'reels', for engagement figures",
            ]))
        elif mode == MODE_REELS and row.get("caption") is None:
            row["_warning"] = "; ".join(filter(None, [
                warning,
                "caption_and_timestamp_not_published_on_this_surface: the reels tab "
                "carries engagement but no caption or publish date. Use mode "
                "'post_detail' on the shortcode for those",
            ]))
        rows.append(row)
    return rows


async def scrape_posts(client: InstagramClient, username: str, options: dict) -> list[dict]:
    return await _scrape_user_media(
        client, username, options, MODE_POSTS, f"{username}/",
        "ProfilePostsTabContent", CONN_POSTS,
    )


async def scrape_reels(client: InstagramClient, username: str, options: dict) -> list[dict]:
    return await _scrape_user_media(
        client, username, options, MODE_REELS, f"{username}/reels/",
        "ProfileReelsTabContent", CONN_REELS,
    )


# ---------------------------------------------------------------------------
# post_detail
# ---------------------------------------------------------------------------
async def scrape_post_detail(client: InstagramClient, shortcode: str, options: dict) -> list[dict]:
    url = f"{ORIGIN}/p/{shortcode}/"
    html = await client.warm(url)
    roots = ssr_roots(html)
    wrapper = pick_root(roots, ROOT_MEDIA, must_have="code")
    if wrapper is None:
        raise RelayShapeError(f"post page for {shortcode} carried no xig_polaris_media payload")

    # Instagram wraps the real media behind a gate. `gating_ruling` non-null and
    # an absent inner payload mean this post is withheld from logged-out viewers
    # (age-restricted or sensitive), which is a documented outcome, not a bug.
    media = wrapper.get("if_not_gated_logged_out")
    if not isinstance(media, dict):
        return [envelope(
            MODE_POST_DETAIL, shortcode, SOURCE_SSR,
            _error=ERR_GATED,
            _errorDetail=(
                f"{shortcode} is gated for logged-out viewers "
                f"(gating_ruling={wrapper.get('gating_ruling')!r})"
            ),
            shortcode=shortcode, url=url,
        )]

    row = envelope(MODE_POST_DETAIL, shortcode, SOURCE_SSR, **normalise_media(media))
    row["_page"] = 1
    row["url"] = url

    if options.get("includeComments", True):
        comments = connection_nodes(wrapper.get(CONN_COMMENTS))
        row["comments"] = [normalise_comment(node) for node in comments]
        row["commentsScraped"] = len(comments)
        declared = row.get("commentCount")
        if isinstance(declared, int) and declared > len(comments):
            # Verified during recon: the logged-out post query accepts an
            # `after` cursor, reports has_next_page=true, and then returns the
            # same first page forever. Real paging lives on
            # /api/v1/media/<id>/comments/, which is 401 for anonymous callers.
            row["_warning"] = (
                f"comments_truncated: Instagram ships only the first "
                f"{len(comments)} of {declared} comments to a logged-out viewer, "
                "and its comment pagination endpoint requires a login"
            )
    else:
        row["comments"] = []
        row["commentsScraped"] = None
    return [row]


# ---------------------------------------------------------------------------
# location
# ---------------------------------------------------------------------------
async def scrape_location(client: InstagramClient, location_id: str, options: dict) -> list[dict]:
    url = f"{ORIGIN}/explore/locations/{location_id}/"
    html = await client.warm(url)
    roots = ssr_roots(html)

    info_payload = pick_root(roots, ROOT_LOCATION_INFO, must_have="native_location_data")
    location = (
        normalise_location(info_payload["native_location_data"])
        if isinstance(info_payload, dict)
        and isinstance(info_payload.get("native_location_data"), dict)
        else {"locationId": location_id}
    )

    max_items = int(options.get("maxItems") or 60)
    tab = (options.get("locationTab") or "recent").lower()
    if tab not in ("recent", "ranked"):
        tab = "recent"

    source = SOURCE_SSR
    tab_payload = pick_root(roots, ROOT_LOCATION_TAB, must_have="edges")
    nodes = connection_nodes(tab_payload)

    # One replay of the query the page already handed us gets a much bigger
    # page than the SSR render, because the preloaded variables carry
    # `page_size_override: 6` -- dropping it took the same request from 6 media
    # to 60. `recent` is also larger than the server-rendered `ranked` tab and
    # is the better default for monitoring a place.
    preload = find_preload(html, "LocationPageTabContent")
    lsd = harvest_lsd(html)
    if preload is not None and lsd is not None:
        variables = {
            key: value
            for key, value in preload["variables"].items()
            if key != "page_size_override"
        }
        variables["tab"] = tab
        try:
            data = await client.graphql(
                doc_id=preload["doc_id"],
                variables=variables,
                lsd=lsd,
                referer=url,
                root_key=ROOT_LOCATION_TAB,
            )
        except BlockedError as exc:
            logger.warning(
                "Location replay failed for %s, keeping the server-rendered page: %s",
                location_id, exc,
            )
        else:
            replayed = connection_nodes(find_connection(data.get(ROOT_LOCATION_TAB)))
            if replayed:
                nodes, source = replayed, SOURCE_GRAPHQL

    # The location tab accepts `after` and answers 200 with zero edges -- the
    # logged-out cursor is simply not honoured. So this surface is single-shot
    # and the row says so rather than implying the cap is the whole place.
    warning = (
        f"single_page_surface: Instagram does not honour a pagination cursor on the "
        f"logged-out location tab, so this '{tab}' tab response ({len(nodes)} media) "
        "is the one page it serves for this place"
    )
    if not nodes:
        return [envelope(
            MODE_LOCATION, location_id, SOURCE_SSR,
            _error=ERR_EMPTY,
            _errorDetail=f"location {location_id} served no media to a logged-out viewer",
            **location,
        )]

    rows = []
    for node in nodes[:max_items]:
        media = normalise_media(node)
        # The place being browsed wins over the per-media location stub.
        media.pop("locationId", None)
        media.pop("locationName", None)
        row = envelope(MODE_LOCATION, location_id, source, **media, **location)
        row["_page"] = 1
        row["_warning"] = warning
        rows.append(row)
    return rows


SCRAPERS: dict[str, Callable[..., Any]] = {
    MODE_PROFILE: scrape_profile,
    MODE_POSTS: scrape_posts,
    MODE_REELS: scrape_reels,
    MODE_POST_DETAIL: scrape_post_detail,
    MODE_LOCATION: scrape_location,
}
