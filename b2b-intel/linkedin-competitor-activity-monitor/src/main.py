"""LinkedIn Top Voice & Competitor Activity Monitor -- Apify actor entry point.

LinkedIn embeds a member's or company's most recent posts, with full text,
timestamp and reaction count, in the page it serves to logged-out visitors. That
is the whole data source here: no cookie, no feed pagination, no Voyager.

What it buys you is a content-strategy read on any account you can name -- how
often they publish, what they publish (video, image, article, plain text), which
hashtags they lean on, how long their posts run, and which of those choices
actually correlate with engagement on their audience.

The honest ceiling: LinkedIn embeds roughly the last **6-10 posts** per account.
That is enough to characterise a posting style and to track it over time by
running this on a schedule, but it is not a full archive and this actor does not
pretend otherwise -- every ACCOUNT row carries ``postsAnalysed`` and the date
span they cover.
"""

from __future__ import annotations

import asyncio
import statistics
from collections import Counter
from datetime import datetime

from apify import Actor

from src import exporters
from src.linkedin import AuthRequired, LinkedInClient, LinkedInError, proxy_url_from
from src.parse import (
    parse_organization,
    parse_person,
    parse_post_engagement,
    parse_posts,
)
from src.runtime import (
    clamp,
    clamp_float,
    company_url,
    dedupe,
    envelope,
    error_record,
    notice_record,
    profile_url,
    string_list,
)
from src.input_errors import input_error

SOURCE_PROFILE = "guest-profile-page"
SOURCE_COMPANY = "guest-company-page"

COLUMNS = [
    "accountName", "accountType", "accountUrl", "followers", "postsAnalysed",
    "postsPerWeek", "daysCovered", "avgReactions", "medianReactions",
    "maxReactions", "engagementRatePct", "topHashtags", "mediaMix",
    "avgTextLength", "articleShare", "bestPostUrl", "bestPostReactions",
    "firstPostAt", "lastPostAt", "recordType",
]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def summarise(account: dict, posts: list[dict], source: str) -> dict:
    """Turn an account's recent posts into a content-strategy profile.

    Engagement rate is reactions per post divided by followers. It is the only
    number here that compares accounts of different sizes fairly: a 500-reaction
    post from an account with 12 million followers is a weaker result than a
    50-reaction post from an account with 2,000.
    """
    dated = [(p, _parse_date(p.get("publishedAt"))) for p in posts]
    timestamps = sorted(d for _, d in dated if d)
    # Company pages embed their posts WITHOUT any engagement data, while member
    # profiles embed it. Counting a missing reaction count as zero would report
    # every company as having no engagement at all, so absent stays absent and
    # the metrics simply go null.
    reactions = [p["reactions"] for p in posts if isinstance(p.get("reactions"), int)]

    days = None
    posts_per_week = None
    if len(timestamps) >= 2:
        days = (timestamps[-1] - timestamps[0]).days or 1
        posts_per_week = round(len(posts) / days * 7, 2)

    hashtags = Counter(tag for post in posts for tag in post.get("hashtags") or [])
    media = Counter(post.get("mediaType") or "TEXT" for post in posts)

    followers = account.get("followers")
    engagement_rate = None
    if followers and reactions:
        engagement_rate = round(
            statistics.mean(reactions) / followers * 100, 4
        )

    rated = [p for p in posts if isinstance(p.get("reactions"), int)]
    best = max(rated, key=lambda p: p["reactions"]) if rated else {}
    lengths = [p.get("textLength") or 0 for p in posts]
    articles = sum(1 for p in posts if p.get("isArticle"))

    return {
        **envelope(source, account.get("accountUrl") or "", "ACCOUNT"),
        "accountName": account.get("accountName"),
        "accountType": account.get("accountType"),
        "accountUrl": account.get("accountUrl"),
        "headline": account.get("headline"),
        "followers": followers,
        "postsAnalysed": len(posts),
        "daysCovered": days,
        "postsPerWeek": posts_per_week,
        "firstPostAt": timestamps[0].isoformat() if timestamps else None,
        "lastPostAt": timestamps[-1].isoformat() if timestamps else None,
        "avgReactions": round(statistics.mean(reactions), 1) if reactions else None,
        "medianReactions": statistics.median(reactions) if reactions else None,
        "maxReactions": max(reactions) if reactions else None,
        "engagementRatePct": engagement_rate,
        "engagementDataAvailable": bool(reactions),
        "topHashtags": [tag for tag, _ in hashtags.most_common(10)],
        "hashtagUsagePct": round(
            sum(1 for p in posts if p.get("hashtags")) / len(posts) * 100, 1
        )
        if posts
        else None,
        "mediaMix": dict(media),
        "avgTextLength": round(statistics.mean(lengths)) if lengths else None,
        "articleShare": round(articles / len(posts) * 100, 1) if posts else None,
        "bestPostUrl": best.get("postUrl"),
        "bestPostReactions": best.get("reactions"),
        "bestPostText": (best.get("postText") or "")[:400] or None,
    }


async def fill_engagement(
    client: LinkedInClient, posts: list[dict], log
) -> list[dict]:
    """Open each post's permalink to read its real reaction and comment counts.

    Only worth doing for company pages, whose embedded posts carry no
    engagement data at all. It costs one request per post, so it is opt-in.
    """
    for post in posts:
        if isinstance(post.get("reactions"), int) or not post.get("postUrl"):
            continue
        try:
            page = await client.fetch(post["postUrl"])
        except LinkedInError as exc:
            log.warning(f"{post['postUrl']}: engagement unavailable -- {exc}")
            continue
        counts = parse_post_engagement(page)
        post["reactions"] = counts.get("reactions")
        post["comments"] = counts.get("comments")
        post["reactionTypes"] = counts.get("reactionTypes") or []
    return posts


async def read_account(client: LinkedInClient, url: str, log) -> tuple[dict, list[dict]]:
    """Fetch one profile or company page and pull its identity plus its posts."""
    page = await client.fetch(url)
    is_company = "/company/" in url or "/school/" in url or "/showcase/" in url
    if is_company:
        organisation = parse_organization(page)
        if not organisation:
            raise LinkedInError("No company data on the page.")
        account = {
            "accountName": organisation.get("companyName"),
            "accountType": "COMPANY",
            "accountUrl": organisation.get("companyUrl") or url,
            "headline": organisation.get("tagline"),
            "followers": organisation.get("followers"),
            "employeeCount": organisation.get("employeeCount"),
            "website": organisation.get("website"),
        }
        source = SOURCE_COMPANY
    else:
        person = parse_person(page)
        if not person:
            raise LinkedInError("No profile data on the page.")
        account = {
            "accountName": person.get("fullName"),
            "accountType": "PERSON",
            "accountUrl": person.get("profileUrl") or url,
            "headline": person.get("headline"),
            "followers": person.get("followers"),
            "currentCompany": person.get("currentCompany"),
            "locality": person.get("locality"),
        }
        source = SOURCE_PROFILE

    posts = parse_posts(page)
    # Posts carried on a profile page do not name their own media type, so it
    # is inferred from what the post links to: an article headline means an
    # article, an external link means a link post, otherwise plain text.
    for post in posts:
        if post.get("isArticle"):
            post["mediaType"] = "ARTICLE"
        elif post.get("externalLinks"):
            post["mediaType"] = "LINK"
        else:
            post["mediaType"] = "TEXT"
    return {**account, "_source": source}, posts


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        log = Actor.log

        profiles = [
            normalised
            for raw in string_list(actor_input.get("profileUrls"))
            if (normalised := profile_url(raw))
        ]
        companies = [
            normalised
            for raw in string_list(actor_input.get("companyUrls"))
            + string_list(actor_input.get("startUrls"))
            if (normalised := company_url(raw))
        ]
        targets = dedupe(profiles + companies)
        if not targets:
            raise input_error(
                "No usable accounts. Give member profiles in profileUrls "
                "(a /in/ URL or a bare handle) or company pages in companyUrls "
                "(a /company/ URL or a bare slug)."
            )

        max_posts = clamp(actor_input.get("maxPostsPerAccount"), 1, 50, 25)
        fetch_engagement = bool(actor_input.get("fetchPostEngagement", False))
        emit_posts = bool(actor_input.get("emitPostRecords", True))
        min_reactions = clamp(actor_input.get("minReactions"), 0, 1_000_000, 0)

        proxy = await proxy_url_from(Actor, actor_input)
        client = LinkedInClient(
            log,
            proxy_url=proxy,
            min_delay=clamp_float(actor_input.get("minDelaySeconds"), 0.0, 60.0, 3.0),
            max_delay=clamp_float(actor_input.get("maxDelaySeconds"), 0.0, 120.0, 8.0),
        )

        records: list[dict] = []
        for url in targets:
            try:
                account, posts = await read_account(client, url, log)
            except LinkedInError as exc:
                code = (
                    "auth_required"
                    if isinstance(exc, AuthRequired)
                    else "fetch_failed"
                )
                records.append(error_record(url, code, str(exc)))
                log.warning(f"{url}: {exc}")
                continue

            posts = [p for p in posts if (p.get("reactions") or 0) >= min_reactions]
            posts = posts[:max_posts]
            source = account.pop("_source")

            if not posts:
                records.append(
                    notice_record(
                        url,
                        "no_public_posts",
                        "LinkedIn embedded no posts for this account on the "
                        "logged-out page. Accounts that have not posted "
                        "recently, and some company pages, behave this way.",
                    )
                )
                # The account itself is still worth a row.
                records.append(
                    {
                        **envelope(source, url, "ACCOUNT"),
                        **account,
                        "postsAnalysed": 0,
                    }
                )
                continue

            if fetch_engagement:
                posts = await fill_engagement(client, posts, log)

            records.append(summarise(account, posts, source))
            log.info(
                f"{account.get('accountName')}: {len(posts)} posts, "
                f"{account.get('followers')} followers."
            )

            if emit_posts:
                for post in posts:
                    records.append(
                        {
                            **envelope(source, url, "POST"),
                            "accountName": account.get("accountName"),
                            "accountUrl": account.get("accountUrl"),
                            **post,
                        }
                    )

        log.info(
            f"{len(targets)} account(s). HTTP: {client.stats['requests']} requests, "
            f"{client.stats['rateGateHits']} rate-gate retries."
        )

        await Actor.push_data(records)
        exporters.configure(
            preferred=COLUMNS, sheet="Accounts", stem="competitor-activity"
        )
        await exporters.write_exports(
            Actor, actor_input.get("exportFormats") or [], records
        )


if __name__ == "__main__":
    asyncio.run(main())
