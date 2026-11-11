"""Actor entry point: read the input, dispatch the mode, stream to the dataset."""

from __future__ import annotations

import logging

from apify import Actor

from src.client import (
    AlgoliaCredentialsBurned,
    NotFound,
    TechInAsiaClient,
    TransientError,
    UnexpectedShape,
)
from src.constants import ALGOLIA_MAX_WINDOW, WP_MAX_RECORDS_PER_ROUTE
from src.modes import (
    mode_companies,
    mode_company_detail,
    mode_jobs,
    mode_latest_posts,
    mode_post_detail,
    mode_search_posts,
    mode_taxonomies,
    mode_taxonomy_posts,
    mode_trending_questions,
    mode_video_posts,
)
from src.runtime import (
    clamp,
    dedupe,
    error_record,
    normalise_post_reference,
    normalise_slug,
    proxy_url_from,
    string_list,
)
from src.input_errors import input_error

log = logging.getLogger("techinasia")

MODES = {
    "latestPosts",
    "postDetail",
    "categoryPosts",
    "tagPosts",
    "videoPosts",
    "searchPosts",
    "taxonomies",
    "trendingQuestions",
    "companies",
    "companyDetail",
    "jobs",
}

# Modes whose reach is capped by the site rather than by the buyer's limit.
_CEILING_NOTES = {
    "latestPosts": WP_MAX_RECORDS_PER_ROUTE,
    "categoryPosts": WP_MAX_RECORDS_PER_ROUTE,
    "tagPosts": WP_MAX_RECORDS_PER_ROUTE,
    "videoPosts": WP_MAX_RECORDS_PER_ROUTE,
    "searchPosts": ALGOLIA_MAX_WINDOW,
}


def _epoch_or_none(value) -> int | None:
    """Accept a unix epoch or a YYYY-MM-DD date."""
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    from datetime import datetime, timezone

    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            return int(parsed.timestamp())
        except ValueError:
            continue
    log.warning(f"Could not read {value!r} as a date -- ignoring it.")
    return None


async def _run_mode(client: TechInAsiaClient, mode: str, actor_input: dict):
    """Return the async iterator for the selected mode."""
    max_items = clamp(actor_input.get("maxItems"), 1, 100000, 200)
    include_content = bool(actor_input.get("includeArticleContent"))

    if mode == "latestPosts":
        return mode_latest_posts(client, max_items=max_items, include_content=include_content)

    if mode == "videoPosts":
        return mode_video_posts(client, max_items=max_items, include_content=include_content)

    if mode == "postDetail":
        refs = dedupe(
            [normalise_post_reference(r) for r in string_list(actor_input.get("postUrls"))]
        )
        refs = [r for r in refs if r]
        if not refs:
            raise ValueError(
                "postDetail needs at least one entry in postUrls -- an article URL, a slug "
                "or a numeric post id."
            )
        return mode_post_detail(client, refs, include_content=include_content)

    if mode in ("categoryPosts", "tagPosts"):
        field = "categorySlugs" if mode == "categoryPosts" else "tagSlugs"
        taxonomy = "categories" if mode == "categoryPosts" else "tags"
        slugs = dedupe([normalise_slug(s) for s in string_list(actor_input.get(field))])
        slugs = [s for s in slugs if s]
        if not slugs:
            raise ValueError(f"{mode} needs at least one entry in {field}.")
        return mode_taxonomy_posts(
            client,
            slugs,
            taxonomy=taxonomy,
            max_items=max_items,
            include_content=include_content,
        )

    if mode == "searchPosts":
        queries = dedupe(string_list(actor_input.get("searchQueries"))) or [""]
        return mode_search_posts(
            client,
            queries,
            max_items=max_items,
            include_content=include_content,
            post_types=string_list(actor_input.get("postTypes")),
            categories=string_list(actor_input.get("filterCategories")),
            authors=string_list(actor_input.get("filterAuthors")),
            published_after=_epoch_or_none(actor_input.get("publishedAfter")),
            published_before=_epoch_or_none(actor_input.get("publishedBefore")),
        )

    if mode == "taxonomies":
        return mode_taxonomies(
            client,
            include_categories=actor_input.get("includeCategories", True),
            include_tags=bool(actor_input.get("includeTags")),
            max_tags=clamp(actor_input.get("maxItems"), 1, WP_MAX_RECORDS_PER_ROUTE, 900),
        )

    if mode == "trendingQuestions":
        return mode_trending_questions(client, max_items=max_items)

    if mode == "companies":
        return mode_companies(
            client,
            max_items=max_items,
            countries=string_list(actor_input.get("companyCountries")),
            funding_stages=string_list(actor_input.get("fundingStages")),
            industries=string_list(actor_input.get("companyIndustries")),
            investors_only=bool(actor_input.get("investorsOnly")),
            min_amount_raised=(
                clamp(actor_input.get("minAmountRaised"), 0, 10**12, 0) or None
            ),
            query=(actor_input.get("companyQuery") or "").strip(),
        )

    if mode == "companyDetail":
        slugs = dedupe(
            [normalise_slug(s) for s in string_list(actor_input.get("companySlugs"))]
        )
        slugs = [s for s in slugs if s]
        if not slugs:
            raise ValueError("companyDetail needs at least one entry in companySlugs.")
        return mode_company_detail(client, slugs)

    if mode == "jobs":
        return mode_jobs(
            client,
            max_items=max_items,
            remote_only=bool(actor_input.get("remoteJobsOnly")),
            query=(actor_input.get("jobQuery") or "").strip(),
        )

    raise ValueError(f"Unknown mode {mode!r}. Pick one of: {', '.join(sorted(MODES))}.")


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        mode = (actor_input.get("mode") or "latestPosts").strip()
        if mode not in MODES:
            raise input_error(
                f"Unknown mode {mode!r}. Pick one of: {', '.join(sorted(MODES))}."
            )

        proxy_url = await proxy_url_from(Actor, actor_input)
        client = TechInAsiaClient(proxy_url=proxy_url)

        Actor.log.info(f"Mode: {mode}")
        if actor_input.get("includeArticleContent"):
            Actor.log.info(
                "includeArticleContent is on -- records will carry the full article HTML. "
                "Tech in Asia is a subscription publication; check your licence before "
                "republishing or redistributing article bodies."
            )

        pushed = 0
        errors = 0

        try:
            iterator = await _run_mode(client, mode, actor_input)
            async for record in iterator:
                await Actor.push_data(record)
                pushed += 1
                if record.get("_error"):
                    errors += 1
                if pushed % 250 == 0:
                    Actor.log.info(f"{pushed} records pushed.")

        except (NotFound, TransientError) as exc:
            # The whole mode failed rather than one input inside it.
            Actor.log.error(f"{mode} failed: {exc}")
            await Actor.push_data(error_record(mode, "mode_failed", str(exc), mode=mode))
            pushed += 1
            errors += 1

        except AlgoliaCredentialsBurned as exc:
            # Circuit breaker: the harvested key died and re-harvesting failed.
            # Let this end the run non-zero so it is visible in the run list.
            Actor.log.error(f"Algolia credentials could not be recovered: {exc}")
            await Actor.push_data(
                error_record(mode, "algolia_credentials_burned", str(exc), mode=mode)
            )
            raise

        finally:
            await client.close()

        ceiling = _CEILING_NOTES.get(mode)
        if ceiling and pushed - errors >= ceiling:
            Actor.log.warning(
                f"This mode tops out at {ceiling} records per query -- that is Tech in Asia's "
                f"own ceiling, not a limit of this actor."
            )

        Actor.log.info(f"Done. {pushed} records pushed ({errors} error rows).")

        if pushed == 0:
            # Fail loud: an empty dataset is never a valid result here.
            raise UnexpectedShape(
                f"{mode} produced no records at all. The upstream shape may have changed."
            )
