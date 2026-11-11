"""LinkedIn Newsletter & Article Scraper -- Apify actor entry point.

LinkedIn's long-form articles live at ``/pulse/{slug}`` and those pages are
open: full body text, author, publish and edit timestamps, reaction count and
comment count, all without a cookie.

The newsletter *series* page at ``/newsletters/{id}`` is not. Every request to
one -- including plausibly real ids -- comes back HTTP 500 with the same
256 KB error body, so subscriber counts have no logged-out surface at all. This
actor therefore does articles properly rather than promising a subscriber number
it cannot get, and says so in the output when you ask for one.

Articles can be given directly or discovered from an author's public profile,
which links the articles they have published.
"""

from __future__ import annotations

import asyncio
import re
import statistics
from collections import Counter

from apify import Actor

from src import exporters
from src.linkedin import AuthRequired, LinkedInClient, LinkedInError, proxy_url_from
from src.parse import clean_url, parse_article, parse_comments, parse_person
from src.runtime import (
    article_url,
    clamp,
    clamp_float,
    dedupe,
    envelope,
    error_record,
    notice_record,
    profile_url,
    string_list,
)
from src.input_errors import input_error

SOURCE_ARTICLE = "guest-pulse-article"
SOURCE_PROFILE = "guest-profile-page"

COLUMNS = [
    "articleTitle", "authorName", "authorUrl", "publishedAt", "wordCount",
    "readingTimeMinutes", "reactions", "comments", "engagementPerThousand",
    "hashtags", "articleUrl", "excerpt", "recordType",
]

_PULSE_LINK = re.compile(r'https://www\.linkedin\.com/pulse/[a-zA-Z0-9\-%_]+')


async def discover_articles(
    client: LinkedInClient, profile: str, wanted: int, log
) -> tuple[list[str], dict]:
    """Articles linked from an author's public profile page."""
    page = await client.fetch(profile)
    person = parse_person(page) or {}
    links = dedupe(
        [clean_url(link) for link in _PULSE_LINK.findall(page) if clean_url(link)]
    )
    log.info(f"{profile}: {len(links)} article link(s) on the profile.")
    return links[:wanted], person


def with_metrics(article: dict) -> dict:
    """Add the one derived number that makes articles comparable.

    Reactions alone favour whoever has the larger following. Reactions per
    thousand followers is what tells you whether a piece actually landed with
    the audience it reached.
    """
    followers = article.get("authorFollowers")
    reactions = article.get("reactions")
    article["engagementPerThousand"] = (
        round(reactions / followers * 1000, 2)
        if followers and isinstance(reactions, int)
        else None
    )
    return article


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        log = Actor.log

        direct = [
            normalised
            for raw in string_list(actor_input.get("articleUrls"))
            + string_list(actor_input.get("startUrls"))
            if (normalised := article_url(raw))
        ]
        authors = [
            normalised
            for raw in string_list(actor_input.get("authorProfiles"))
            if (normalised := profile_url(raw))
        ]
        if not direct and not authors:
            raise input_error(
                "Give at least one article URL (articleUrls, a "
                "linkedin.com/pulse/... link) or one author profile "
                "(authorProfiles) to discover articles from."
            )

        max_articles = clamp(actor_input.get("maxArticles"), 1, 500, 50)
        per_author = clamp(actor_input.get("maxArticlesPerAuthor"), 1, 200, 20)
        include_text = bool(actor_input.get("includeFullText", True))
        include_comments = bool(actor_input.get("includeComments", False))
        min_reactions = clamp(actor_input.get("minReactions"), 0, 1_000_000, 0)

        proxy = await proxy_url_from(Actor, actor_input)
        client = LinkedInClient(
            log,
            proxy_url=proxy,
            min_delay=clamp_float(actor_input.get("minDelaySeconds"), 0.0, 60.0, 3.0),
            max_delay=clamp_float(actor_input.get("maxDelaySeconds"), 0.0, 120.0, 8.0),
        )

        records: list[dict] = []

        if string_list(actor_input.get("newsletterUrls")):
            records.append(
                notice_record(
                    ", ".join(string_list(actor_input.get("newsletterUrls")))[:200],
                    "newsletter_series_closed",
                    "LinkedIn serves HTTP 500 to logged-out visitors on every "
                    "/newsletters/ series page, so subscriber counts have no "
                    "public surface. Pass the individual /pulse/ issue links "
                    "in articleUrls instead - those are fully readable.",
                )
            )
            log.warning(
                "Newsletter series pages are closed to logged-out visitors; "
                "subscriber counts cannot be read. Pass the individual issue "
                "links in articleUrls instead."
            )

        targets: list[tuple[str, str]] = [(url, url) for url in direct]
        for author in authors:
            try:
                found, _person = await discover_articles(
                    client, author, per_author, log
                )
                targets.extend((url, author) for url in found)
            except LinkedInError as exc:
                records.append(error_record(author, "discovery_failed", str(exc)))
                log.warning(f"{author}: {exc}")

        seen: set[str] = set()
        unique_targets = []
        for url, origin in targets:
            if url.lower() in seen:
                continue
            seen.add(url.lower())
            unique_targets.append((url, origin))
        unique_targets = unique_targets[:max_articles]

        log.info(f"{len(unique_targets)} article(s) to read.")

        kept: list[dict] = []
        for url, origin in unique_targets:
            try:
                page = await client.fetch(url)
            except LinkedInError as exc:
                code = (
                    "auth_required" if isinstance(exc, AuthRequired) else "fetch_failed"
                )
                records.append(error_record(origin, code, str(exc)))
                continue

            article = parse_article(page)
            if not article:
                records.append(
                    notice_record(
                        origin,
                        "not_an_article",
                        f"{url} did not carry LinkedIn's Article data. Deleted "
                        "articles redirect to LinkedIn's top-content hub, which "
                        "answers 200 with no article on it.",
                    )
                )
                continue

            if (article.get("reactions") or 0) < min_reactions:
                continue

            article = with_metrics(article)
            if not include_text:
                article.pop("articleText", None)

            record = {**envelope(SOURCE_ARTICLE, origin, "ARTICLE"), **article}

            if include_comments:
                commenters = parse_comments(page)
                record["commentSample"] = [
                    {
                        "fullName": c.get("fullName"),
                        "profileUrl": c.get("profileUrl"),
                        "commentText": c.get("commentText"),
                    }
                    for c in commenters
                ]
                record["commentSampleSize"] = len(commenters)

            records.append(record)
            kept.append(article)

        if kept:
            reactions = [
                a["reactions"] for a in kept if isinstance(a.get("reactions"), int)
            ]
            words = [a.get("wordCount") or 0 for a in kept]
            tags = Counter(tag for a in kept for tag in a.get("hashtags") or [])
            log.info(
                f"{len(kept)} article(s). Median reactions "
                f"{statistics.median(reactions) if reactions else 'n/a'}, "
                f"median length {statistics.median(words) if words else 'n/a'} words."
            )
            if bool(actor_input.get("emitSummary", True)):
                records.append(
                    {
                        **envelope(SOURCE_ARTICLE, "run summary", "SUMMARY"),
                        "articlesAnalysed": len(kept),
                        "medianReactions": statistics.median(reactions)
                        if reactions
                        else None,
                        "avgReactions": round(statistics.mean(reactions), 1)
                        if reactions
                        else None,
                        "medianWordCount": statistics.median(words) if words else None,
                        "topHashtags": [tag for tag, _ in tags.most_common(15)],
                        "authors": sorted(
                            {a.get("authorName") for a in kept if a.get("authorName")}
                        ),
                    }
                )

        log.info(
            f"HTTP: {client.stats['requests']} requests, "
            f"{client.stats['rateGateHits']} rate-gate retries."
        )

        await Actor.push_data(records)
        exporters.configure(
            preferred=COLUMNS,
            skip={"articleText"} if len(records) > 200 else set(),
            sheet="Articles",
            stem="linkedin-articles",
        )
        await exporters.write_exports(
            Actor, actor_input.get("exportFormats") or [], records
        )


if __name__ == "__main__":
    asyncio.run(main())
