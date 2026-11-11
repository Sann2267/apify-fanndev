"""LinkedIn Post Engagers Scraper -- Apify actor entry point.

The people who commented on a post are published on the post's own public page,
so the commenter half of this actor needs no cookie at all. The people who only
reacted are not: the guest page publishes how many reacted and which reaction
types were used, but never who. That list lives behind Voyager, and Voyager
needs the buyer's ``li_at``.

Both halves are wired here, and the run tells the buyer which half it actually
delivered rather than quietly returning a short list.
"""

from __future__ import annotations

import asyncio

from apify import Actor

from src import exporters
from src.linkedin import AuthRequired, LinkedInClient, LinkedInError, proxy_url_from
from src.parse import (
    clean_url,
    parse_comments,
    parse_person,
    parse_post_page,
)
from src.runtime import (
    clamp,
    clamp_float,
    dedupe,
    envelope,
    error_record,
    notice_record,
    post_url,
    string_list,
)
from src.voyager import QueryIdResolver, person_from_voyager, walk
from src.input_errors import input_error

SOURCE_PUBLIC = "guest-post-page"
SOURCE_VOYAGER = "voyager-reactions"
SOURCE_PROFILE = "guest-profile-page"

COLUMNS = [
    "fullName", "firstName", "lastName", "headline", "profileUrl", "profileSlug",
    "engagementType", "reactionType", "commentText", "commentedAgo",
    "currentTitle", "currentCompany", "currentCompanyUrl", "locality", "country",
    "followers", "postUrl", "postAuthorName", "postReactions", "postComments",
    "recordType",
]


async def read_post(client: LinkedInClient, url: str, log) -> tuple[dict, str]:
    """Fetch a post page and summarise the post itself."""
    page = await client.fetch(url)
    post = parse_post_page(page)
    summary = {
        "postUrl": clean_url(url),
        "activityId": post.get("activityId"),
        "postText": post.get("postText"),
        "publishedAt": post.get("publishedAt"),
        "postAuthorName": post.get("postAuthorName"),
        "postAuthorUrl": post.get("postAuthorUrl"),
        "postAuthorFollowers": post.get("postAuthorFollowers"),
        "mediaType": post.get("mediaType"),
        "postReactions": post.get("reactions"),
        "postComments": post.get("comments"),
        "reactionTypes": post.get("reactionTypes") or [],
        "hashtags": post.get("hashtags") or [],
    }
    return summary, page


async def reactors_via_voyager(
    client: LinkedInClient,
    resolver: QueryIdResolver,
    activity_id: str,
    wanted: int,
    log,
) -> list[dict]:
    """Reactor identities, which only exist on the authenticated surface."""
    query_id = await resolver.get("reactions", "voyagerSocialDashReactions")
    collected: list[dict] = []
    start = 0
    page_size = 50
    while len(collected) < wanted:
        variables = (
            f"(threadUrn:urn%3Ali%3Aactivity%3A{activity_id},"
            f"start:{start},count:{min(page_size, wanted - len(collected))})"
        )
        payload = await client.graphql(query_id, variables)
        batch: list[dict] = []
        for group in walk(payload, "elements"):
            if not isinstance(group, list):
                continue
            for element in group:
                if not isinstance(element, dict):
                    continue
                actor_node = element.get("reactorLockup") or element.get("actor") or element
                person = person_from_voyager(actor_node)
                if not person:
                    continue
                person["reactionType"] = element.get("reactionType")
                batch.append(person)
        if not batch:
            break
        collected.extend(batch)
        start += page_size
        if len(batch) < page_size:
            break
    return collected[:wanted]


async def enrich(client: LinkedInClient, profile_url: str, log) -> dict:
    """Open an engager's public profile for their employer and location.

    One extra request per person, so it is off by default: a post with 200
    commenters turns into 200 more page loads, and every one of them is another
    chance to meet the rate gate.
    """
    page = await client.fetch(profile_url)
    person = parse_person(page)
    if not person:
        return {}
    return {
        "currentTitle": person.get("currentTitle"),
        "currentCompany": person.get("currentCompany"),
        "currentCompanyUrl": person.get("currentCompanyUrl"),
        "locality": person.get("locality"),
        "country": person.get("country"),
        "followers": person.get("followers"),
        "about": person.get("about"),
    }


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        log = Actor.log

        urls = dedupe(
            [
                normalised
                for raw in string_list(actor_input.get("postUrls"))
                + string_list(actor_input.get("startUrls"))
                if (normalised := post_url(raw))
            ]
        )
        raw_count = len(
            string_list(actor_input.get("postUrls"))
            + string_list(actor_input.get("startUrls"))
        )
        if not urls:
            raise input_error(
                "No usable post URLs. Give a post permalink "
                "(linkedin.com/posts/...-activity-123...), a /feed/update/ link, "
                "an urn:li:activity:123... or a bare activity id."
            )
        if raw_count > len(urls):
            log.warning(f"{raw_count - len(urls)} input(s) were not LinkedIn posts.")

        cookie = (actor_input.get("sessionCookie") or "").strip()
        if cookie.lower().startswith("li_at="):
            cookie = cookie.split("=", 1)[1].strip().strip('"')
        want_reactors = bool(actor_input.get("includeReactors", False))
        want_commenters = bool(actor_input.get("includeCommenters", True))
        enrich_profiles = bool(actor_input.get("enrichProfiles", False))
        max_per_post = clamp(actor_input.get("maxEngagersPerPost"), 1, 1000, 100)
        max_total = clamp(actor_input.get("maxEngagers"), 1, 5000, 500)
        emit_posts = bool(actor_input.get("emitPostRecords", True))

        proxy_reason = None
        if cookie:
            proxy_reason = (
                "You supplied a session cookie but no proxy. LinkedIn scores the "
                "exit IP against where your account normally signs in, and an "
                "Apify datacenter IP is exactly the mismatch that gets a session "
                "flagged. A RESIDENTIAL proxy in your own country is strongly "
                "advised whenever the cookie is in use."
            )
        proxy = await proxy_url_from(Actor, actor_input, required_reason=proxy_reason)

        client = LinkedInClient(
            log,
            li_at=cookie or None,
            proxy_url=proxy,
            min_delay=clamp_float(actor_input.get("minDelaySeconds"), 0.0, 60.0, 2.0),
            max_delay=clamp_float(actor_input.get("maxDelaySeconds"), 0.0, 120.0, 8.0),
        )
        resolver = QueryIdResolver(client, log)

        if want_reactors and not cookie:
            log.warning(
                "Reactors were requested but no li_at cookie was supplied. "
                "LinkedIn does not publish reactor identities to logged-out "
                "visitors, so this run returns commenters only."
            )

        records: list[dict] = []
        emitted = 0

        for url in urls:
            if emitted >= max_total:
                log.info(f"Reached the overall cap of {max_total} engagers.")
                break
            try:
                summary, page = await read_post(client, url, log)
            except LinkedInError as exc:
                code = (
                    "auth_required" if isinstance(exc, AuthRequired) else "fetch_failed"
                )
                records.append(error_record(url, code, str(exc)))
                log.warning(f"{url}: {exc}")
                continue

            log.info(
                f"{summary.get('postUrl')}: {summary.get('postReactions')} reactions, "
                f"{summary.get('postComments')} comments."
            )

            if emit_posts:
                records.append(
                    {**envelope(SOURCE_PUBLIC, url, "POST"), **summary}
                )

            people: list[dict] = []
            if want_commenters:
                people.extend(parse_comments(page))

            if want_reactors and cookie and summary.get("activityId"):
                try:
                    reactors = await reactors_via_voyager(
                        client, resolver, summary["activityId"], max_per_post, log
                    )
                    for person in reactors:
                        person["engagementType"] = "REACTION"
                    people.extend(reactors)
                except LinkedInError as exc:
                    records.append(
                        error_record(url, "reactors_failed", str(exc))
                    )
                    log.warning(f"{url}: reactor list unavailable -- {exc}")

            # One row per person per post; the same member commenting twice is
            # one lead, not two.
            seen: set[str] = set()
            unique = []
            for person in people:
                key = (person.get("profileUrl") or person.get("fullName") or "").lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                unique.append(person)

            for person in unique[:max_per_post]:
                if emitted >= max_total:
                    break
                if enrich_profiles and person.get("profileUrl"):
                    try:
                        person.update(await enrich(client, person["profileUrl"], log))
                    except LinkedInError as exc:
                        person["_enrichError"] = str(exc)[:200]
                records.append(
                    {
                        **envelope(
                            SOURCE_PROFILE if enrich_profiles else SOURCE_PUBLIC,
                            url,
                            "ENGAGER",
                        ),
                        **person,
                        "postUrl": summary.get("postUrl"),
                        "postAuthorName": summary.get("postAuthorName"),
                        "postReactions": summary.get("postReactions"),
                        "postComments": summary.get("postComments"),
                    }
                )
                emitted += 1

            if want_commenters and not unique:
                records.append(
                    notice_record(
                        url,
                        "no_public_engagers",
                        "LinkedIn published no commenters for this post to a "
                        "logged-out visitor. Posts with comments disabled, very "
                        "new posts and some company posts behave this way.",
                    )
                )

        log.info(
            f"{emitted} engagers from {len(urls)} post(s). "
            f"HTTP: {client.stats['requests']} requests, "
            f"{client.stats['rateGateHits']} rate-gate retries."
        )

        await Actor.push_data(records)
        exporters.configure(
            preferred=COLUMNS, sheet="Engagers", stem="post-engagers"
        )
        await exporters.write_exports(
            Actor, actor_input.get("exportFormats") or [], records
        )


if __name__ == "__main__":
    asyncio.run(main())
