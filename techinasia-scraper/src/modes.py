"""One coroutine per mode. Each yields dataset-ready records as it goes.

Everything here streams: records are yielded page by page so a long run fills
the dataset as it works rather than buffering to the end.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from src.client import NotFound, TechInAsiaClient, TransientError, UnexpectedShape
from src.constants import (
    ALGOLIA_INDEX_COMPANIES,
    ALGOLIA_INDEX_JOBS,
    ALGOLIA_INDEX_POSTS,
    ALGOLIA_INDEX_TRENDING,
    ALGOLIA_MAX_HITS_PER_PAGE,
    ALGOLIA_MAX_WINDOW,
    LARAVEL_API,
    LARAVEL_MAX_PER_PAGE,
    RECORD_CATEGORY,
    RECORD_COMPANY,
    RECORD_JOB,
    RECORD_POST,
    RECORD_TAG,
    RECORD_TOPIC,
    RECORD_TRENDING_QUESTION,
    WP_API,
    WP_MAX_PAGE,
    WP_MAX_PER_PAGE,
    WP_MAX_RECORDS_PER_ROUTE,
)
from src.runtime import envelope, error_record, is_safe_segment

log = logging.getLogger("techinasia")


# ---------------------------------------------------------------------------
# WordPress REST list routes
# ---------------------------------------------------------------------------


async def walk_wp_list(
    client: TechInAsiaClient,
    route: str,
    *,
    collection: str,
    input_value: str,
    source: str,
    record_type: str,
    max_items: int,
    include_content: bool = False,
    extra: dict | None = None,
) -> AsyncIterator[dict]:
    """Page a WordPress list route, respecting the 30x30 ceiling.

    The envelope's ``total_pages`` cannot be trusted as a stop condition -- it
    is computed from the unfiltered total and happily claims 2,650 pages on a
    route that 400s at page 31. We stop on whichever comes first: the caller's
    limit, the hard page cap, or a short/empty page.
    """
    emitted = 0
    per_page = min(WP_MAX_PER_PAGE, max_items) if max_items else WP_MAX_PER_PAGE
    per_page = max(1, per_page)
    reported_total: int | None = None

    for page in range(1, WP_MAX_PAGE + 1):
        if emitted >= max_items:
            break

        payload = await client.get_json(
            f"{WP_API}{route}", params={"page": page, "per_page": per_page}
        )
        if not isinstance(payload, dict):
            raise UnexpectedShape(f"{route} page {page} was not a JSON object.")

        items = payload.get(collection)
        if items is None:
            raise UnexpectedShape(
                f"{route} page {page} has no '{collection}' key; saw {sorted(payload)[:12]}."
            )
        if reported_total is None:
            reported_total = payload.get("total")

        if not items:
            break

        for item in items:
            if emitted >= max_items:
                break
            yield envelope(
                item,
                input_value=input_value,
                source=source,
                record_type=record_type,
                include_content=include_content,
                extra=extra,
            )
            emitted += 1

        if len(items) < per_page:
            break

    # Tell the buyer when the site's own ceiling -- not their limit -- stopped us.
    if (
        reported_total
        and emitted >= WP_MAX_RECORDS_PER_ROUTE
        and reported_total > WP_MAX_RECORDS_PER_ROUTE
        and emitted < max_items
    ):
        log.warning(
            f"{route}: reached the WordPress ceiling of {WP_MAX_RECORDS_PER_ROUTE} records "
            f"({reported_total} exist). Use searchPosts, or narrow by category or tag, to go deeper."
        )


async def mode_latest_posts(
    client: TechInAsiaClient, *, max_items: int, include_content: bool
) -> AsyncIterator[dict]:
    async for record in walk_wp_list(
        client,
        "/posts",
        collection="posts",
        input_value="latest",
        source="S1-wp-posts",
        record_type=RECORD_POST,
        max_items=max_items,
        include_content=include_content,
    ):
        yield record


async def mode_video_posts(
    client: TechInAsiaClient, *, max_items: int, include_content: bool
) -> AsyncIterator[dict]:
    async for record in walk_wp_list(
        client,
        "/videos/posts",
        collection="posts",
        input_value="videos",
        source="S1-wp-videos",
        record_type=RECORD_POST,
        max_items=max_items,
        include_content=include_content,
    ):
        yield record


async def mode_taxonomy_posts(
    client: TechInAsiaClient,
    slugs: list[str],
    *,
    taxonomy: str,
    max_items: int,
    include_content: bool,
) -> AsyncIterator[dict]:
    """Posts under each category or tag slug. ``taxonomy`` is 'categories' or 'tags'."""
    # Not taxonomy[:-1] -- that turns "categories" into "categorie".
    singular = {"categories": "category", "tags": "tag"}[taxonomy]
    source = f"S1-wp-{singular}-posts"
    for slug in slugs:
        if not is_safe_segment(slug):
            yield error_record(slug, "invalid_slug", f"{slug!r} is not a usable slug.")
            continue
        try:
            found = False
            async for record in walk_wp_list(
                client,
                f"/{taxonomy}/{slug}/posts",
                collection="posts",
                input_value=slug,
                source=source,
                record_type=RECORD_POST,
                max_items=max_items,
                include_content=include_content,
                extra={f"{singular}Slug": slug},
            ):
                found = True
                yield record
            if not found:
                yield error_record(slug, "no_posts", f"No posts under {taxonomy}/{slug}.")
        except NotFound:
            yield error_record(slug, "not_found", f"{taxonomy}/{slug} does not exist.")
        except TransientError as exc:
            yield error_record(slug, "fetch_failed", str(exc))


async def mode_post_detail(
    client: TechInAsiaClient, references: list[str], *, include_content: bool
) -> AsyncIterator[dict]:
    """Resolve posts by slug, numeric id or article URL.

    ``/posts/<x>`` accepts a slug and a numeric id interchangeably and returns
    the same list envelope in both cases. A slug that does not exist returns a
    real 404, so there is no hollow-200 to guard against here.
    """
    for reference in references:
        if not is_safe_segment(reference):
            yield error_record(reference, "invalid_reference", f"{reference!r} is not usable.")
            continue
        try:
            payload = await client.get_json(f"{WP_API}/posts/{reference}")
            posts = (payload or {}).get("posts") or []
            if not posts:
                yield error_record(reference, "not_found", "Resolved but carried no post.")
                continue
            for post in posts:
                yield envelope(
                    post,
                    input_value=reference,
                    source="S1-wp-post-detail",
                    record_type=RECORD_POST,
                    include_content=include_content,
                )
        except NotFound:
            yield error_record(reference, "not_found", f"No post at /posts/{reference}.")
        except TransientError as exc:
            yield error_record(reference, "fetch_failed", str(exc))


async def mode_taxonomies(
    client: TechInAsiaClient, *, include_categories: bool, include_tags: bool, max_tags: int
) -> AsyncIterator[dict]:
    """The site's own taxonomy lists, plus the curated topic map."""
    if include_categories:
        async for record in walk_wp_list(
            client,
            "/categories",
            collection="categories",
            input_value="categories",
            source="S1-wp-categories",
            record_type=RECORD_CATEGORY,
            max_items=WP_MAX_RECORDS_PER_ROUTE,
        ):
            yield record

        # /topics is a small hand-curated map of the site's headline sections,
        # each carrying the exact API route behind it.
        try:
            topics = await client.get_json(f"{WP_API}/topics")
            for topic in topics or []:
                yield envelope(
                    topic,
                    input_value="topics",
                    source="S1-wp-topics",
                    record_type=RECORD_TOPIC,
                )
        except (NotFound, TransientError) as exc:
            yield error_record("topics", "fetch_failed", str(exc))

    if include_tags:
        async for record in walk_wp_list(
            client,
            "/tags",
            collection="tags",
            input_value="tags",
            source="S1-wp-tags",
            record_type=RECORD_TAG,
            max_items=max_tags,
        ):
            yield record


# ---------------------------------------------------------------------------
# Algolia -- the real search
# ---------------------------------------------------------------------------
#
# The WordPress /search route is a decoy: it answers 200 with
# {"total":0,...,"items":[]} for every query, including ones that plainly match
# thousands of articles. All site search actually runs through Algolia.


async def walk_algolia(
    client: TechInAsiaClient,
    index: str,
    base_payload: dict,
    *,
    input_value: str,
    source: str,
    record_type: str,
    max_items: int,
    include_content: bool = False,
    trending: bool = False,
    extra: dict | None = None,
) -> AsyncIterator[dict]:
    """Page an Algolia index within its 1,000-record window."""
    emitted = 0
    budget = min(max_items, ALGOLIA_MAX_WINDOW)
    hits_per_page = min(ALGOLIA_MAX_HITS_PER_PAGE, max(1, budget))
    page = 0
    total_available: int | None = None

    while emitted < budget:
        payload = dict(base_payload)
        payload["hitsPerPage"] = min(hits_per_page, budget - emitted)
        payload["page"] = page

        result = await client.algolia_query(index, payload, trending=trending)
        hits = result.get("hits") or []
        if total_available is None:
            total_available = result.get("nbHits")

        if not hits:
            break

        for hit in hits:
            if emitted >= budget:
                break
            yield envelope(
                hit,
                input_value=input_value,
                source=source,
                record_type=record_type,
                include_content=include_content,
                extra=extra,
            )
            emitted += 1

        page += 1
        if page >= (result.get("nbPages") or 0):
            break

    if total_available and total_available > ALGOLIA_MAX_WINDOW and emitted >= ALGOLIA_MAX_WINDOW:
        log.warning(
            f"'{input_value}' matched {total_available} records but Algolia serves only the "
            f"first {ALGOLIA_MAX_WINDOW}. Split the query -- by category, country or funding "
            f"stage -- to reach the rest."
        )


def _build_post_search_payload(
    query: str,
    *,
    post_types: list[str],
    categories: list[str],
    authors: list[str],
    published_after: int | None,
    published_before: int | None,
) -> dict:
    payload: dict = {"query": query}

    facet_filters: list[list[str]] = []
    if post_types:
        facet_filters.append([f"type:{t}" for t in post_types])
    if categories:
        facet_filters.append([f"categories.name:{c}" for c in categories])
    if authors:
        facet_filters.append([f"author.name:{a}" for a in authors])
    if facet_filters:
        payload["facetFilters"] = facet_filters

    numeric: list[str] = []
    if published_after:
        numeric.append(f"epoch_time>={published_after}")
    if published_before:
        numeric.append(f"epoch_time<={published_before}")
    if numeric:
        payload["numericFilters"] = numeric

    return payload


async def mode_search_posts(
    client: TechInAsiaClient,
    queries: list[str],
    *,
    max_items: int,
    include_content: bool,
    post_types: list[str],
    categories: list[str],
    authors: list[str],
    published_after: int | None,
    published_before: int | None,
) -> AsyncIterator[dict]:
    for query in queries:
        payload = _build_post_search_payload(
            query,
            post_types=post_types,
            categories=categories,
            authors=authors,
            published_after=published_after,
            published_before=published_before,
        )
        found = False
        async for record in walk_algolia(
            client,
            ALGOLIA_INDEX_POSTS,
            payload,
            input_value=query or "(all posts)",
            source="S2-algolia-posts",
            record_type=RECORD_POST,
            max_items=max_items,
            include_content=include_content,
            extra={"searchQuery": query},
        ):
            found = True
            yield record
        if not found:
            yield error_record(query or "(all posts)", "no_results", "Search matched nothing.")


async def mode_trending_questions(
    client: TechInAsiaClient, *, max_items: int
) -> AsyncIterator[dict]:
    """The Ask Tech in Asia leaderboard, with the pageview counts behind it."""
    async for record in walk_algolia(
        client,
        ALGOLIA_INDEX_TRENDING,
        {"query": ""},
        input_value="trending-questions",
        source="S2-algolia-trending",
        record_type=RECORD_TRENDING_QUESTION,
        max_items=max_items,
        trending=True,
    ):
        yield record


# ---------------------------------------------------------------------------
# Laravel -- company database and job board
# ---------------------------------------------------------------------------


async def walk_laravel(
    client: TechInAsiaClient,
    route: str,
    *,
    input_value: str,
    source: str,
    record_type: str,
    max_items: int,
    params: dict | None = None,
    include_content: bool = False,
) -> AsyncIterator[dict]:
    """Page a Laravel paginator route.

    Unlike the WordPress side, ``last_page`` here is honest and there is no page
    ceiling -- /companies walks all 4,826 pages of its 120,649 records.
    """
    emitted = 0
    per_page = min(LARAVEL_MAX_PER_PAGE, max_items) if max_items else LARAVEL_MAX_PER_PAGE
    per_page = max(1, per_page)
    page = 1

    while emitted < max_items:
        query = dict(params or {})
        query.update({"page": page, "per_page": per_page})

        payload = await client.get_json(f"{LARAVEL_API}{route}", params=query)
        if not isinstance(payload, dict) or "data" not in payload:
            raise UnexpectedShape(
                f"{route} page {page} has no 'data' key; saw {sorted(payload)[:12] if isinstance(payload, dict) else type(payload)}."
            )

        rows = payload.get("data") or []
        if not rows:
            break

        for row in rows:
            if emitted >= max_items:
                break
            yield envelope(
                row,
                input_value=input_value,
                source=source,
                record_type=record_type,
                include_content=include_content,
            )
            emitted += 1

        last_page = payload.get("last_page")
        if last_page and page >= last_page:
            break
        if len(rows) < per_page:
            break
        page += 1


async def mode_companies(
    client: TechInAsiaClient,
    *,
    max_items: int,
    countries: list[str],
    funding_stages: list[str],
    industries: list[str],
    investors_only: bool,
    min_amount_raised: int | None,
    query: str,
) -> AsyncIterator[dict]:
    """The company database, via whichever backend can answer the question.

    The Laravel /companies route reaches all 120,649 records but silently
    ignores every filter parameter we tried -- query, industries and
    with_investor_tags all returned the unfiltered total. Algolia honours real
    facet filters but only ever serves 1,000 records per query. So: filtered
    requests go to Algolia, unfiltered sweeps go to Laravel.
    """
    wants_filter = bool(
        countries or funding_stages or industries or investors_only or min_amount_raised or query
    )

    if not wants_filter:
        async for record in walk_laravel(
            client,
            "/companies",
            input_value="all-companies",
            source="S3-laravel-companies",
            record_type=RECORD_COMPANY,
            max_items=max_items,
        ):
            yield record
        return

    payload: dict = {"query": query}
    facet_filters: list[list[str]] = []
    if countries:
        facet_filters.append([f"entity_locations.country_name:{c}" for c in countries])
    if funding_stages:
        facet_filters.append([f"last_funding_stage:{s}" for s in funding_stages])
    if industries:
        facet_filters.append([f"entity_industries.name:{i}" for i in industries])
    if investors_only:
        facet_filters.append(["is_investor:true"])
    if facet_filters:
        payload["facetFilters"] = facet_filters
    if min_amount_raised:
        payload["numericFilters"] = [f"total_amount_raised>={min_amount_raised}"]

    label = query or "filtered-companies"
    found = False
    async for record in walk_algolia(
        client,
        ALGOLIA_INDEX_COMPANIES,
        payload,
        input_value=label,
        source="S2-algolia-companies",
        record_type=RECORD_COMPANY,
        max_items=max_items,
    ):
        found = True
        yield record
    if not found:
        yield error_record(
            label,
            "no_results",
            "No company matched. Facet values are case- and spelling-exact -- "
            "'Indonesia', 'Series A', 'Venture Capital'.",
        )


async def mode_company_detail(
    client: TechInAsiaClient, slugs: list[str]
) -> AsyncIterator[dict]:
    """Full company profiles by slug.

    The slug must be the database's own ``entity_slug``: 'gojek' resolves,
    'grab' and 'sea-group' 404. Run the companies mode first if you need to
    look one up.
    """
    for slug in slugs:
        if not is_safe_segment(slug):
            yield error_record(slug, "invalid_slug", f"{slug!r} is not a usable slug.")
            continue
        try:
            payload = await client.get_json(f"{LARAVEL_API}/companies/{slug}")
            rows = (payload or {}).get("data") or []
            if not rows:
                yield error_record(slug, "not_found", "Resolved but carried no company.")
                continue
            for row in rows:
                yield envelope(
                    row,
                    input_value=slug,
                    source="S3-laravel-company-detail",
                    record_type=RECORD_COMPANY,
                )
        except NotFound:
            yield error_record(
                slug,
                "not_found",
                f"No company at /companies/{slug}. The slug must match the database's "
                f"entity_slug exactly.",
            )
        except TransientError as exc:
            yield error_record(slug, "fetch_failed", str(exc))


async def mode_jobs(
    client: TechInAsiaClient, *, max_items: int, remote_only: bool, query: str
) -> AsyncIterator[dict]:
    """The Tech in Asia job board.

    ``is_remote`` is the one query parameter the Laravel route actually honours
    (294 postings drop to 13). Free-text search is ignored there, so a query
    goes to the Algolia job_postings index instead.
    """
    if query:
        found = False
        async for record in walk_algolia(
            client,
            ALGOLIA_INDEX_JOBS,
            {"query": query},
            input_value=query,
            source="S2-algolia-jobs",
            record_type=RECORD_JOB,
            max_items=max_items,
            extra={"searchQuery": query},
        ):
            found = True
            yield record
        if not found:
            yield error_record(query, "no_results", "No job posting matched.")
        return

    params = {"is_remote": 1} if remote_only else None
    async for record in walk_laravel(
        client,
        "/job-postings",
        input_value="remote-jobs" if remote_only else "all-jobs",
        source="S3-laravel-jobs",
        record_type=RECORD_JOB,
        max_items=max_items,
        params=params,
    ):
        yield record
