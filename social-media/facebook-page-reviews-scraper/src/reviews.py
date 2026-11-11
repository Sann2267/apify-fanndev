"""Fetching one page's reviews tab and paging through its feed.

The tab renders its first slice server-side and streams the rest. Two queries do
the work and both are read from the page at runtime:

- `ProfileCometReviewsFeedQuery` -- id and variables published in the page's
  relay preloader block. Replaying it returns the first reviews and a cursor.
- `ProfileCometReviewsFeedRefetchQuery` -- the pagination query. Its id is not in
  the HTML; it is read from the page's JS bundle, and its argument list is read
  from the same module, so the variables are built from what the query actually
  declares rather than from a guess.

Facebook returns a partial-error envelope on these calls (`field_exception` on
the save-flow field, which a logged-out client cannot have). The reviews come
back alongside it, so the error is ignored rather than treated as a failure --
treating it as one would throw away every review on the page.
"""

from __future__ import annotations

import re
from typing import Any

from src.fbcore import BlockedError, FacebookSession, harvest_preloaders, is_hollow
from src.parser import next_cursor, parse_reviews, parse_reviews_html, parse_summary

BASE = "https://www.facebook.com/"
FEED_QUERY = "ProfileCometReviewsFeedQuery"
PAGINATION_QUERY = "ProfileCometReviewsFeedRefetchQuery"

ARG_NAMES = re.compile(r'kind:"LocalArgument",name:"([A-Za-z_0-9]+)"')


class PageUnavailable(RuntimeError):
    """The page does not exist, or does not expose a reviews tab."""


async def fetch_reviews_tab(session: FacebookSession, slug: str) -> tuple[str, dict]:
    url = f"{BASE}{slug}/reviews"
    html = await session.get_html(url)
    if is_hollow(html):
        raise PageUnavailable(
            "Facebook served the empty shell (~330 KB). The page does not exist "
            "under this slug."
        )
    summary = parse_summary(html)
    summary["slug"] = slug
    summary["pageUrl"] = f"{BASE}{slug}"
    summary["reviewsUrl"] = url
    return html, summary


async def _pagination_args(session: FacebookSession, html: str) -> list[str] | None:
    """Read the refetch query's declared argument names out of the bundle."""
    from src.fbcore import BUNDLE_SRC

    marker = f'__d("{PAGINATION_QUERY}.graphql"'
    for src in dict.fromkeys(BUNDLE_SRC.findall(html)):
        url = src.replace("&amp;", "&")
        try:
            response = await session._session.get(url, headers={"accept": "*/*"})
        except Exception:
            continue
        if response.status_code != 200:
            continue
        index = response.text.find(marker)
        if index < 0:
            continue
        return ARG_NAMES.findall(response.text[index:index + 8000])
    return None


async def fetch_reviews(
    session: FacebookSession,
    html: str,
    url: str,
    max_reviews: int,
    log: Any = None,
) -> tuple[list[dict], dict]:
    """The page's reviews, newest first, up to `max_reviews`."""
    reviews = parse_reviews_html(html)
    seen = {r["reviewId"] for r in reviews}
    meta = {"requestsMade": 0, "paginated": False}

    preloaders = harvest_preloaders(html)
    if FEED_QUERY not in preloaders:
        # Reviews are switched off on this page, or Facebook did not render the
        # tab. Whatever the HTML carried is still returned.
        meta["feedQueryMissing"] = True
        return reviews[:max_reviews], meta

    query_id, base_vars = preloaders[FEED_QUERY]
    try:
        payload = await session.graphql(html, FEED_QUERY, query_id, base_vars, referer=url)
    except BlockedError as exc:
        meta["feedStoppedBy"] = str(exc)
        return reviews[:max_reviews], meta
    meta["requestsMade"] += 1

    for review in parse_reviews(payload):
        if review["reviewId"] not in seen:
            seen.add(review["reviewId"])
            reviews.append(review)

    cursor = next_cursor(payload)
    if len(reviews) >= max_reviews or not cursor:
        return reviews[:max_reviews], meta

    doc_id = await session.bundle_doc_id(html, PAGINATION_QUERY)
    args = await _pagination_args(session, html) if doc_id else None
    if not doc_id or not args:
        meta["paginationUnavailable"] = True
        return reviews[:max_reviews], meta

    meta["paginated"] = True
    while len(reviews) < max_reviews and cursor:
        variables: dict[str, Any] = {name: base_vars.get(name) for name in args}
        variables.update(
            {k: v for k, v in base_vars.items() if k.startswith("__relay_internal__pv__")}
        )
        variables["cursor"] = cursor
        variables["count"] = 10
        if variables.get("id") is None:
            variables["id"] = base_vars.get("userID")

        try:
            payload = await session.graphql(
                html, PAGINATION_QUERY, doc_id, variables, referer=url
            )
        except BlockedError as exc:
            meta["paginationStoppedBy"] = str(exc)
            break
        meta["requestsMade"] += 1

        fresh = [r for r in parse_reviews(payload) if r["reviewId"] not in seen]
        if not fresh:
            break
        for review in fresh:
            seen.add(review["reviewId"])
        reviews.extend(fresh)
        if log:
            log.info(f"  +{len(fresh)} review(s) (running total {len(reviews)})")
        cursor = next_cursor(payload)

    reviews.sort(key=lambda r: r["createdAt"] or 0, reverse=True)
    return reviews[:max_reviews], meta
