"""Mode dispatch for the YouTube community post Actor.

* ``channel``   -- every community post on the channel's posts page.
* ``reference`` -- probe the surface and report what it yielded, including the
  two things it cannot give you (exact like counts, poll splits).

A channel with no posts, a channel whose community tab is switched off, and a
page YouTube declined to fill are three different outcomes and get three
different ``recordType`` values. Collapsing them into "0 results" is how a
scraper quietly lies.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

from apify import Actor

from src.client import Blocked, NotFound, Reduced, YouTubeClient
from src.constants import MARKER_POST, MODES, URL_POSTS
from src.extractor import CommunityUnavailable, parse_posts
from src.input_errors import input_error

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _handle(raw: str) -> str:
    raw = (raw or "").strip().rstrip("/")
    if raw.startswith("http"):
        raw = re.sub(r"^https?://(www\.)?youtube\.com/", "", raw)
        raw = raw.split("/")[0]
    if raw and not raw.startswith(("@", "channel/", "c/", "user/")):
        raw = "@" + raw.lstrip("@")
    return raw


def _envelope(payload: dict, *, source: str, query: str, record_type: str,
              attempts: int | None = None) -> dict:
    return {
        "_input": query,
        "_query": query,
        "_source": source,
        "_scrapedAt": _now(),
        "_attempts": attempts,
        "recordType": record_type,
        **payload,
    }


async def _run_channel(client: YouTubeClient, handles: list[str], limit: int,
                       concurrency: int) -> int:
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch(raw: str) -> list[dict]:
        handle = _handle(raw)
        if not handle:
            return [_envelope({"error": "unparseable-input"},
                              source="none", query=raw, record_type="ERROR")]
        async with semaphore:
            try:
                body, profile, attempts = await client.get(
                    URL_POSTS.format(handle=handle), marker=MARKER_POST)
            except Reduced as exc:
                # The page loaded but never listed posts. Could be a gated
                # response, could be a channel with none -- check the words.
                return [_envelope(
                    {"channelHandle": handle, "error": "reduced-or-empty",
                     "message": str(exc),
                     "hint": "The posts page never listed a post. Either the channel "
                             "has never posted, or YouTube declined to fill the page. "
                             "Run mode=reference or retry with a proxy to tell them apart."},
                    source="youtube-posts", query=handle,
                    record_type="REDUCED", attempts=client.attempts_used)]
            except NotFound:
                return [_envelope({"channelHandle": handle, "error": "not-found"},
                                  source="youtube-posts", query=handle, record_type="ERROR")]
            except Blocked as exc:
                return [_envelope({"channelHandle": handle, "error": "blocked",
                                   "message": str(exc)},
                                  source="youtube-posts", query=handle, record_type="ERROR")]

        try:
            posts = parse_posts(body)
        except CommunityUnavailable as exc:
            return [_envelope(
                {"channelHandle": handle, "error": "community-unavailable",
                 "message": str(exc),
                 "hint": "YouTube says this channel's community tab is not available. "
                         "That is a channel setting, not a scraping failure."},
                source="youtube-posts", query=handle, record_type="ERROR",
                attempts=attempts)]

        log.info("%s -> %d post(s) in %d attempt(s), %s",
                 handle, len(posts), attempts, profile)

        records = []
        for position, post in enumerate(posts[:limit], start=1):
            post["channelHandle"] = handle
            post["feedPosition"] = position
            post["_tlsProfile"] = profile
            records.append(_envelope(post, source="youtube-posts", query=handle,
                                     record_type="POST", attempts=attempts))
        if not records:
            records.append(_envelope(
                {"channelHandle": handle, "error": "no-posts",
                 "hint": "The page rendered normally and listed nothing. This channel "
                         "appears not to have posted."},
                source="youtube-posts", query=handle, record_type="EMPTY",
                attempts=attempts))
        return records

    pushed = 0
    for coro in asyncio.as_completed([fetch(h) for h in handles]):
        for record in await coro:
            await Actor.push_data(record)
            pushed += 1
    return pushed


async def _run_reference(client: YouTubeClient) -> int:
    probes = []
    for handle in ("@MrBeast", "@veritasium"):
        try:
            body, profile, attempts = await client.get(
                URL_POSTS.format(handle=handle), marker=MARKER_POST)
            posts = parse_posts(body)
            polls = [p for p in posts if p.get("attachmentType") == "poll"]
            probes.append({
                "handle": handle, "ok": True, "attempts": attempts,
                "tlsProfile": profile, "pageBytes": len(body),
                "posts": len(posts), "polls": len(polls),
                "attachmentTypes": sorted({p.get("attachmentType") for p in posts}),
            })
        except Exception as exc:
            probes.append({"handle": handle, "ok": False,
                           "error": f"{type(exc).__name__}: {exc}"})

    await Actor.push_data(_envelope(
        {
            "surface": "youtube.com/@handle/posts",
            "probes": probes,
            "known": {
                "wrongPath": "/@handle/community answers 200 with 'This Community "
                             "isn't available' and zero posts. /@handle/posts is the "
                             "working path.",
                "postsPerPage": 10,
                "likeCountsAreExact": False,
                "likeCountNote": "voteCount is abbreviated text ('1.9M'); no exact "
                                 "figure exists in the logged-out payload.",
                "pollSplitAvailable": False,
                "pollNote": "Choices and total votes are public. The per-choice split "
                            "is shown only to a signed-in account that voted.",
                "commentBodies": False,
                "commentNote": "Post comment threads need a separate InnerTube "
                               "continuation fetch and are not part of this Actor.",
            },
        },
        source="reference", query="reference", record_type="SURFACE"))
    return 1


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        mode = (actor_input.get("mode") or "channel").strip()
        if mode not in MODES:
            raise input_error(f"mode must be one of {MODES}, got {mode!r}")

        limit = max(1, min(int(actor_input.get("postsPerChannel") or 10), 10))
        concurrency = max(1, min(int(actor_input.get("concurrency") or 3), 10))

        proxy_url = None
        proxy_config = actor_input.get("proxyConfiguration")
        if proxy_config:
            configuration = await Actor.create_proxy_configuration(actor_proxy_input=proxy_config)
            if configuration:
                proxy_url = await configuration.new_url()

        client = YouTubeClient(proxy_url=proxy_url, profile=actor_input.get("tlsProfile"))

        if mode == "reference":
            pushed = await _run_reference(client)
        else:
            handles = actor_input.get("channels") or []
            if not handles:
                raise input_error("channel mode needs at least one entry in `channels`.")
            pushed = await _run_channel(client, handles, limit, concurrency)

        log.info("pushed %d record(s) in mode=%s", pushed, mode)
