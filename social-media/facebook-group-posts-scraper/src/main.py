"""Facebook Group Posts & Comments Scraper -- Apify actor entry point."""

from __future__ import annotations

from datetime import datetime, timezone

from apify import Actor

from src.exporters import BUILDERS
from src.fbcore import BlockedError, FacebookSession
from src.groups import GroupUnavailable, fetch_comments, fetch_group, fetch_posts
from src.parser import group_ref, matches_filters, summarise
from src.runtime import envelope, error_record, resolve_proxy, write_exports
from src.input_errors import input_error

SOURCE = "group-feed"


def read_groups(actor_input: dict) -> list[str]:
    refs: list[str] = []
    for item in actor_input.get("groups") or []:
        value = item.get("url") if isinstance(item, dict) else item
        ref = group_ref(str(value or ""))
        if ref:
            refs.append(ref)
    for item in actor_input.get("startUrls") or []:
        value = item.get("url") if isinstance(item, dict) else item
        ref = group_ref(str(value or ""))
        if ref:
            refs.append(ref)
    return list(dict.fromkeys(refs))


def epoch_from_date(value: str | None) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(f"postedAfter must be YYYY-MM-DD, got {value!r}")
    return int(parsed.timestamp())


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        refs = read_groups(actor_input)
        if not refs:
            raise input_error(
                "Nothing to scrape. Supply groups as URLs "
                "(https://www.facebook.com/groups/<slug-or-id>), slugs or numeric ids."
            )

        max_posts = max(1, min(int(actor_input.get("maxPostsPerGroup", 40)), 1000))
        scrape_comments = bool(actor_input.get("scrapeComments"))
        max_comment_posts = max(1, min(int(actor_input.get("maxPostsForComments", 20)), 500))
        filters = {
            "onlyWithText": bool(actor_input.get("onlyWithText")),
            "textContains": actor_input.get("textContains"),
            "minReactions": actor_input.get("minReactions"),
            "minComments": actor_input.get("minComments"),
            "postedAfterEpoch": epoch_from_date(actor_input.get("postedAfter")),
        }
        export_formats = actor_input.get("exportFormats") or []
        emit_summary = bool(actor_input.get("emitSummary", True))
        proxy_url = await resolve_proxy(actor_input)

        Actor.log.info(f"{len(refs)} group(s), up to {max_posts} post(s) each.")
        if scrape_comments:
            Actor.log.warning(
                "Comment bodies are requested. Facebook publishes the comment "
                "COUNT on a group post to logged-out clients but not the comment "
                "text -- measured 2026-09-20. Each post will still be fetched and "
                "whatever is served will be emitted, with commentsServed saying "
                "how much that was."
            )

        records: list[dict] = []
        kept_posts: list[dict] = []
        failures = 0

        async with FacebookSession(proxy_url=proxy_url, log=Actor.log) as session:
            for ref in refs:
                try:
                    html, meta = await fetch_group(session, ref)
                except (GroupUnavailable, BlockedError) as exc:
                    failures += 1
                    record = error_record(SOURCE, ref, "group_unavailable", str(exc))
                    records.append(record)
                    await Actor.push_data(record)
                    continue
                except Exception as exc:
                    failures += 1
                    record = error_record(
                        SOURCE, ref, "unexpected_error", f"{type(exc).__name__}: {exc}"
                    )
                    records.append(record)
                    await Actor.push_data(record)
                    continue

                Actor.log.info(
                    f"{ref}: {meta.get('groupName') or 'group'} "
                    f"({meta.get('memberCountLabel') or 'member count unknown'}, "
                    f"{meta.get('privacy') or 'privacy unknown'})"
                )

                try:
                    posts, fetch_meta = await fetch_posts(
                        session, html, meta["groupUrl"], max_posts, log=Actor.log
                    )
                except (GroupUnavailable, BlockedError) as exc:
                    failures += 1
                    record = error_record(SOURCE, ref, "feed_unavailable", str(exc))
                    records.append(record)
                    await Actor.push_data(record)
                    continue

                if fetch_meta.get("paginationUnavailable"):
                    Actor.log.warning(
                        f"{ref}: kept the first batch of {len(posts)} post(s); "
                        "Facebook's pagination query id could not be read from the "
                        "page bundles this run."
                    )

                selected = [p for p in posts if matches_filters(p, filters)]
                Actor.log.info(
                    f"{ref}: {len(selected)} post(s) kept out of {len(posts)} fetched "
                    f"in {fetch_meta['requestsMade']} request(s)"
                )

                if scrape_comments:
                    for post in selected[:max_comment_posts]:
                        comments = await fetch_comments(session, post)
                        post["comments"] = comments
                        post["commentsServed"] = len(comments)

                for post in selected:
                    record = {
                        **envelope(SOURCE, ref, "POST"),
                        "groupId": meta.get("groupId"),
                        "groupName": meta.get("groupName"),
                        "groupUrl": meta.get("groupUrl"),
                        "groupVanity": meta.get("groupVanity"),
                        "groupPrivacy": meta.get("privacy"),
                        "groupMemberCount": meta.get("memberCount"),
                        "groupMemberCountLabel": meta.get("memberCountLabel"),
                        **{k: v for k, v in post.items() if k != "comments"},
                    }
                    records.append(record)
                    kept_posts.append(post)
                    await Actor.push_data(record)

                    for index, comment in enumerate(post.get("comments") or [], start=1):
                        comment_record = {
                            **envelope(SOURCE, ref, "COMMENT"),
                            "groupId": meta.get("groupId"),
                            "groupName": meta.get("groupName"),
                            "postId": post.get("postId"),
                            "postUrl": post.get("postUrl"),
                            "commentIndex": index,
                            **comment,
                        }
                        records.append(comment_record)
                        await Actor.push_data(comment_record)

        if emit_summary and kept_posts:
            summary = {
                **envelope(SOURCE, f"{len(refs)} group(s)", "RUN_SUMMARY"),
                **summarise(kept_posts),
                "groupsRequested": len(refs),
                "groupsFailed": failures,
            }
            records.append(summary)
            await Actor.push_data(summary)
            Actor.log.info(
                f"Summary: {summary['postsCollected']} post(s), "
                f"{summary['distinctAuthors']} author(s), "
                f"{summary['totalComments']} comment(s) counted, "
                f"{summary['commentBodiesCollected']} comment body/bodies served"
            )

        await write_exports(records, export_formats, BUILDERS)

        Actor.log.info(f"Finished: {len(kept_posts)} post(s) | {failures} group(s) failed")
        if failures and not kept_posts:
            raise RuntimeError(
                "No group could be read and nothing was collected -- see the ERROR records."
            )
