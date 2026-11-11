"""Bluesky (AT Protocol) scraper -- 15 modes over one public XRPC client.

One actor, many modes, because every mode here shares the same host, the
same (absent) auth model, the same `cursor` pagination idiom and the same
output envelope. Splitting them into 15 actors would duplicate ~90% of
this file 15 times for no functional gain.
"""

import asyncio
import logging

from apify import Actor

from src.client import (
    AuthRequired,
    BlueskyClient,
    InvalidRequest,
    NotFound,
    RateLimited,
)
from src.constants import (
    MAX_BATCH,
    MAX_THREAD_DEPTH,
    PUBLIC_HOST,
    SEARCH_HOST,
    SEARCH_METHOD,
)
from src.extractor import (
    UnexpectedShape,
    envelope,
    error_record,
    flatten_feed,
    flatten_thread,
    parse_actor,
    parse_at_uri,
    web_url_for_post,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

# Which input field feeds each mode. Modes mapped to None take no
# per-item input and run exactly once per actor run.
MODE_INPUT_FIELD = {
    "profile": "actors",
    "posts": "actors",
    "followers": "actors",
    "follows": "actors",
    "lists": "actors",
    "starter-packs": "actors",
    "post-detail": "postUrls",
    "post-likes": "postUrls",
    "post-reposts": "postUrls",
    "post-quotes": "postUrls",
    "search-posts": "searchQueries",
    "search-users": "searchQueries",
    "feed": "feedUrls",
    "trends": None,
    "popular-feeds": None,
}

# searchPosts params that are pass-through filters rather than actor config.
SEARCH_FILTER_KEYS = ("sort", "since", "until", "lang", "author", "domain", "url", "mentions")


# --------------------------------------------------------- actor modes
async def run_posts(client, item, cfg, max_items):
    actor = parse_actor(item)
    params = {"actor": actor}
    if cfg.get("postFilter"):
        params["filter"] = cfg["postFilter"]
    if cfg.get("includePins"):
        params["includePins"] = True
    feed = await client.paginate(
        PUBLIC_HOST, "app.bsky.feed.getAuthorFeed", params, "feed", max_items
    )
    return [envelope(p, "S1-xrpc", item, "POST") for p in flatten_feed(feed)]


async def run_followers(client, item, cfg, max_items):
    actors = await client.paginate(
        PUBLIC_HOST, "app.bsky.graph.getFollowers",
        {"actor": parse_actor(item)}, "followers", max_items,
    )
    return [envelope(a, "S1-xrpc", item, "FOLLOWER") for a in actors]


async def run_follows(client, item, cfg, max_items):
    actors = await client.paginate(
        PUBLIC_HOST, "app.bsky.graph.getFollows",
        {"actor": parse_actor(item)}, "follows", max_items,
    )
    return [envelope(a, "S1-xrpc", item, "FOLLOWING") for a in actors]


async def run_lists(client, item, cfg, max_items):
    lists = await client.paginate(
        PUBLIC_HOST, "app.bsky.graph.getLists",
        {"actor": parse_actor(item)}, "lists", max_items,
    )
    return [envelope(x, "S1-xrpc", item, "LIST") for x in lists]


async def run_starter_packs(client, item, cfg, max_items):
    packs = await client.paginate(
        PUBLIC_HOST, "app.bsky.graph.getActorStarterPacks",
        {"actor": parse_actor(item)}, "starterPacks", max_items,
    )
    return [envelope(x, "S1-xrpc", item, "STARTER_PACK") for x in packs]


# ---------------------------------------------------------- post modes
async def _require_post_uri(client, item):
    """Parse, then force the authority to a DID.

    getLikes / getQuotes / getPosts answer 200-with-empty-array and
    getRepostedBy answers 500 when the at:// authority is a handle, so
    resolving here is what stops this actor emitting silent empties.
    See BlueskyClient.resolve_did."""
    uri = parse_at_uri(item, "post")
    if not uri:
        raise ValueError(
            "not a post URL or at:// URI: {!r} "
            "(expected https://bsky.app/profile/<handle>/post/<rkey>)".format(item)
        )
    return await client.to_did_uri(uri)


async def run_post_detail(client, item, cfg, max_items):
    uri = await _require_post_uri(client, item)
    depth = min(int(cfg.get("threadDepth", 6)), MAX_THREAD_DEPTH)
    data = await client.get_json(
        PUBLIC_HOST, "app.bsky.feed.getPostThread",
        {"uri": uri, "depth": depth, "parentHeight": int(cfg.get("parentHeight", 0))},
    )
    thread = data.get("thread")
    if not isinstance(thread, dict):
        raise UnexpectedShape("getPostThread returned no 'thread' object for " + uri)
    root, replies = flatten_thread(thread, max_items)
    if root is None:
        # Blocked / not-found / detached thread node.
        raise NotFound("thread node is " + str(thread.get("$type", "unknown")))
    records = [envelope(root, "S1-xrpc", item, "POST")]
    records += [envelope(r, "S1-xrpc", item, "REPLY") for r in replies[:max_items]]
    return records


async def run_post_likes(client, item, cfg, max_items):
    likes = await client.paginate(
        PUBLIC_HOST, "app.bsky.feed.getLikes",
        {"uri": await _require_post_uri(client, item)}, "likes", max_items,
    )
    return [envelope(x, "S1-xrpc", item, "LIKE") for x in likes]


async def run_post_reposts(client, item, cfg, max_items):
    actors = await client.paginate(
        PUBLIC_HOST, "app.bsky.feed.getRepostedBy",
        {"uri": await _require_post_uri(client, item)}, "repostedBy", max_items,
    )
    return [envelope(a, "S1-xrpc", item, "REPOSTED_BY") for a in actors]


async def run_post_quotes(client, item, cfg, max_items):
    posts = await client.paginate(
        PUBLIC_HOST, "app.bsky.feed.getQuotes",
        {"uri": await _require_post_uri(client, item)}, "posts", max_items,
    )
    out = []
    for p in posts:
        record = dict(p)
        url = web_url_for_post(p)
        if url:
            record["webUrl"] = url
        out.append(envelope(record, "S1-xrpc", item, "QUOTE"))
    return out


# -------------------------------------------------------- search modes
async def run_search_posts(client, item, cfg, max_items):
    """The only mode that leaves `public.api.bsky.app`. `api.bsky.app`
    throttles this method per-IP, so the client rotates proxies on 403."""
    params = {"q": item}
    for key in SEARCH_FILTER_KEYS:
        if cfg.get(key):
            params[key] = cfg[key]
    if cfg.get("tag"):
        params["tag"] = cfg["tag"]
    posts = await client.paginate(SEARCH_HOST, SEARCH_METHOD, params, "posts", max_items)
    out = []
    for p in posts:
        record = dict(p)
        url = web_url_for_post(p)
        if url:
            record["webUrl"] = url
        out.append(envelope(record, "S2-xrpc-search", item, "POST"))
    return out


async def run_search_users(client, item, cfg, max_items):
    actors = await client.paginate(
        PUBLIC_HOST, "app.bsky.actor.searchActors", {"q": item}, "actors", max_items
    )
    return [envelope(a, "S1-xrpc", item, "PROFILE") for a in actors]


# ----------------------------------------------------- discovery modes
async def run_feed(client, item, cfg, max_items):
    """Accepts both a feed-generator URI and a list URI -- they are the
    two things a bsky.app '/feed/' or '/lists/' URL can denote, and they
    need different XRPC methods."""
    uri = parse_at_uri(item, "post")
    if not uri:
        raise ValueError("not a feed/list URL or at:// URI: {!r}".format(item))
    uri = await client.to_did_uri(uri)
    if "app.bsky.graph.list" in uri:
        method, key = "app.bsky.feed.getListFeed", "list"
    else:
        method, key = "app.bsky.feed.getFeed", "feed"
    feed = await client.paginate(PUBLIC_HOST, method, {key: uri}, "feed", max_items)
    return [envelope(p, "S1-xrpc", item, "POST") for p in flatten_feed(feed)]


async def run_trends(client, item, cfg, max_items):
    data = await client.get_json(
        PUBLIC_HOST, "app.bsky.unspecced.getTrends", {"limit": min(max_items, 25)}
    )
    trends = data.get("trends")
    if trends is None:
        raise UnexpectedShape("getTrends returned no 'trends' key")
    return [envelope(t, "S1-xrpc", "trends", "TREND") for t in trends[:max_items]]


async def run_popular_feeds(client, item, cfg, max_items):
    feeds = await client.paginate(
        PUBLIC_HOST, "app.bsky.unspecced.getPopularFeedGenerators",
        {}, "feeds", max_items,
    )
    return [envelope(f, "S1-xrpc", "popular-feeds", "FEED_GENERATOR") for f in feeds]


MODE_HANDLERS = {
    "posts": run_posts,
    "followers": run_followers,
    "follows": run_follows,
    "lists": run_lists,
    "starter-packs": run_starter_packs,
    "post-detail": run_post_detail,
    "post-likes": run_post_likes,
    "post-reposts": run_post_reposts,
    "post-quotes": run_post_quotes,
    "search-posts": run_search_posts,
    "search-users": run_search_users,
    "feed": run_feed,
    "trends": run_trends,
    "popular-feeds": run_popular_feeds,
}


async def run_profile_batch(client, items, cfg, max_items):
    """`profile` mode does not fit the one-item-per-task shape: it is
    batched 25 actors per request, so N handles cost ceil(N/25) requests
    instead of N."""
    records = []
    for start in range(0, len(items), MAX_BATCH):
        chunk = items[start:start + MAX_BATCH]
        try:
            actors = [parse_actor(x) for x in chunk]
        except ValueError as exc:
            records.extend(error_record(x, "bad_input_or_shape", str(exc)) for x in chunk)
            continue

        try:
            data = await client.get_json(
                PUBLIC_HOST, "app.bsky.actor.getProfiles", {"actors": actors}
            )
        except (NotFound, InvalidRequest) as exc:
            # One bad handle fails the whole batch -- fall back to
            # per-actor calls so the good ones still produce rows.
            log.info("Batch of %d failed (%s); retrying individually", len(chunk), exc)
            for raw_item, actor in zip(chunk, actors):
                try:
                    single = await client.get_json(
                        PUBLIC_HOST, "app.bsky.actor.getProfile", {"actor": actor}
                    )
                    records.append(envelope(single, "S1-xrpc", raw_item, "PROFILE"))
                except NotFound:
                    records.append(error_record(raw_item, "not_found", "actor " + actor))
                except InvalidRequest as inner:
                    records.append(error_record(raw_item, "invalid_request", str(inner)))
            continue

        profiles = data.get("profiles")
        if profiles is None:
            raise UnexpectedShape("getProfiles returned no 'profiles' key")
        by_did = {p.get("did"): p for p in profiles}
        by_handle = {str(p.get("handle", "")).lower(): p for p in profiles}
        for raw_item, actor in zip(chunk, actors):
            profile = by_did.get(actor) or by_handle.get(actor.lower())
            if profile is None:
                # getProfiles silently drops actors it cannot resolve.
                records.append(error_record(raw_item, "not_found", "actor " + actor))
            else:
                records.append(envelope(profile, "S1-xrpc", raw_item, "PROFILE"))
    return records


# ---------------------------------------------------------------- main
def resolve_items(mode: str, cfg: dict) -> list[str]:
    field = MODE_INPUT_FIELD[mode]
    if field is None:
        return ["__singleton__"]
    values = [str(v).strip() for v in (cfg.get(field) or []) if str(v).strip()]
    if not values:
        raise ValueError(
            "mode {!r} requires a non-empty {!r} input".format(mode, field)
        )
    return values


async def run_one(client, handler, item, cfg, max_items) -> list[dict]:
    """Never let one bad input kill the run -- every failure mode maps to
    a diagnostic row so downstream always sees the input was processed."""
    try:
        records = await handler(client, item, cfg, max_items)
        if not records:
            # Every input gets a row. A genuinely empty result (a post
            # with no likes, an account with no lists) and a silently
            # broken query look identical downstream otherwise.
            return [error_record(item, "empty_result", "upstream returned no items")]
        return records
    except NotFound as exc:
        return [error_record(item, "not_found", str(exc))]
    except AuthRequired as exc:
        return [error_record(item, "auth_required", str(exc))]
    except RateLimited as exc:
        return [error_record(item, "rate_limited", str(exc))]
    except InvalidRequest as exc:
        return [error_record(item, "invalid_request", str(exc))]
    except (ValueError, UnexpectedShape) as exc:
        return [error_record(item, "bad_input_or_shape", str(exc))]
    except Exception as exc:  # noqa: BLE001 -- last resort, still emits a row
        log.exception("Unhandled error for %r", item)
        return [error_record(item, "exception", repr(exc))]


async def main():
    async with Actor:
        cfg = await Actor.get_input() or {}

        mode = cfg.get("mode", "posts")
        if mode not in MODE_INPUT_FIELD:
            raise input_error(
                "unknown mode {!r}; expected one of {}".format(
                    mode, sorted(MODE_INPUT_FIELD)
                )
            )

        max_items = int(cfg.get("maxItems", 100))
        if max_items < 1:
            raise input_error("maxItems must be >= 1")
        max_concurrency = max(1, int(cfg.get("maxConcurrency", 4)))

        items = resolve_items(mode, cfg)

        # Only `search-posts` actually benefits from a proxy (it is the
        # one IP-throttled endpoint). Everywhere else the public AppView
        # is unthrottled, so an unavailable proxy must degrade to a
        # direct connection rather than kill the run -- which is also
        # what makes local runs work without credentials.
        try:
            proxy_cfg = await Actor.create_proxy_configuration(
                actor_proxy_input=cfg.get("proxyConfiguration"),
            )
        except Exception as exc:  # noqa: BLE001 -- proxy is optional here
            proxy_cfg = None
            level = Actor.log.warning if mode == "search-posts" else Actor.log.info
            level(
                "Proxy unavailable (%s) -- continuing without one.%s",
                exc,
                " search-posts is IP-rate-limited; without a proxy to rotate"
                " to, it paces itself and may give up with a rate_limited row."
                if mode == "search-posts" else "",
            )

        async def next_proxy():
            return await proxy_cfg.new_url() if proxy_cfg else None

        start_proxy = await next_proxy()
        Actor.log.info(
            "mode=%s items=%d maxItems=%d concurrency=%d proxy=%s",
            mode, len(items), max_items, max_concurrency, bool(start_proxy),
        )

        client = BlueskyClient(
            proxy_url=start_proxy,
            proxy_provider=next_proxy if proxy_cfg else None,
        )
        pushed = 0
        try:
            if mode == "profile":
                records = await run_profile_batch(client, items, cfg, max_items)
                if records:
                    await Actor.push_data(records)
                pushed = len(records)
            else:
                handler = MODE_HANDLERS[mode]
                # searchPosts shares one IP bucket across tasks, so
                # parallelising it only burns the bucket faster.
                effective_concurrency = 1 if mode == "search-posts" else max_concurrency
                semaphore = asyncio.Semaphore(effective_concurrency)
                counter = {"n": 0}

                async def worker(item):
                    async with semaphore:
                        records = await run_one(client, handler, item, cfg, max_items)
                        if records:
                            await Actor.push_data(records)
                        counter["n"] += len(records)
                        Actor.log.info("%s: %s -> %d record(s)", mode, item, len(records))

                await asyncio.gather(*(worker(i) for i in items))
                pushed = counter["n"]
        finally:
            await client.close()

        Actor.log.info("Done. %d record(s) pushed.", pushed)
