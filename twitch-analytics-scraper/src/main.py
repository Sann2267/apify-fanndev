import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import IntegrityCheckFailed, TwitchClient
from src.constants import MAX_FIRST_GAMES, MAX_FIRST_STREAMS
from src.extractor import (
    CHANNEL_LIVE_QUERY,
    GAME_STREAMS_QUERY,
    TOP_GAMES_QUERY,
    TOP_STREAMS_QUERY,
    extract_error,
    extract_game_streams,
    extract_top_games,
    extract_top_streams,
    utc_now_iso,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def run_top_games(limit: int, proxy_url: str | None) -> list[dict]:
    first = min(limit, MAX_FIRST_GAMES)
    client = TwitchClient(proxy_url=proxy_url)
    try:
        data = await client.graphql(TOP_GAMES_QUERY, {"first": first})
        return extract_top_games(data, first)
    except IntegrityCheckFailed as e:
        return [extract_error("top-games", "integrity_check_failed", repr(e))]
    finally:
        await client.close()


async def run_top_streams(limit: int, proxy_url: str | None) -> list[dict]:
    first = min(limit, MAX_FIRST_STREAMS)
    client = TwitchClient(proxy_url=proxy_url)
    try:
        data = await client.graphql(TOP_STREAMS_QUERY, {"first": first})
        return extract_top_streams(data, first)
    except IntegrityCheckFailed as e:
        return [extract_error("top-streams", "integrity_check_failed", repr(e))]
    finally:
        await client.close()


async def run_game_streams(game_name: str, limit: int, proxy_url: str | None) -> list[dict]:
    first = min(limit, MAX_FIRST_STREAMS)
    client = TwitchClient(proxy_url=proxy_url)
    try:
        data = await client.graphql(GAME_STREAMS_QUERY, {"name": game_name, "first": first})
        return extract_game_streams(data, game_name, first)
    except IntegrityCheckFailed as e:
        return [extract_error(game_name, "integrity_check_failed", repr(e))]
    finally:
        await client.close()


def _find_rank(edges: list[dict], login: str) -> int | None:
    login_lower = login.lower()
    for i, edge in enumerate(edges, start=1):
        broadcaster = (edge.get("node") or {}).get("broadcaster") or {}
        if (broadcaster.get("login") or "").lower() == login_lower:
            return i
    return None


async def run_channel_rank(login: str, proxy_url: str | None) -> dict:
    client = TwitchClient(proxy_url=proxy_url)
    try:
        data = await client.graphql(CHANNEL_LIVE_QUERY, {"login": login})
        user = data.get("user")
        if user is None:
            return extract_error(login, "channel_not_found")

        stream = user.get("stream")
        scraped_at = utc_now_iso()
        if stream is None:
            return {
                "_input": login,
                "_source": "S1-gql",
                "_scrapedAt": scraped_at,
                "login": user.get("login"),
                "displayName": user.get("displayName"),
                "isLive": False,
                "viewersCount": None,
                "gameName": None,
                "globalRankApprox": None,
                "categoryRankApprox": None,
                "note": "channel is not currently live -- ranking only applies to live streams",
            }

        game = stream.get("game") or {}
        game_name = game.get("name")

        global_data = await client.graphql(TOP_STREAMS_QUERY, {"first": MAX_FIRST_STREAMS})
        global_edges = (global_data.get("streams") or {}).get("edges") or []
        global_rank = _find_rank(global_edges, login)

        category_rank = None
        if game_name:
            game_data = await client.graphql(GAME_STREAMS_QUERY, {"name": game_name, "first": MAX_FIRST_STREAMS})
            cat_edges = ((game_data.get("game") or {}).get("streams") or {}).get("edges") or []
            category_rank = _find_rank(cat_edges, login)

        return {
            "_input": login,
            "_source": "S1-gql",
            "_scrapedAt": scraped_at,
            "login": user.get("login"),
            "displayName": user.get("displayName"),
            "isLive": True,
            "viewersCount": stream.get("viewersCount"),
            "streamStartedAt": stream.get("createdAt"),
            "gameName": game_name,
            "_approxSort": True,
            "globalRankApprox": global_rank,
            "globalRankNote": (
                f"position {global_rank} within the platform-wide top {MAX_FIRST_STREAMS} live streams"
                if global_rank
                else f"not found within the platform-wide top {MAX_FIRST_STREAMS} live streams"
            ),
            "categoryRankApprox": category_rank,
            "categoryRankNote": (
                None
                if not game_name
                else (
                    f"position {category_rank} within the top {MAX_FIRST_STREAMS} live streams in {game_name!r}"
                    if category_rank
                    else f"not found within the top {MAX_FIRST_STREAMS} live streams in {game_name!r}"
                )
            ),
        }
    except IntegrityCheckFailed as e:
        return extract_error(login, "integrity_check_failed", repr(e))
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(login, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "top-games")
        valid_modes = ("top-games", "top-streams", "game-streams", "channel-rank")
        if mode not in valid_modes:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {valid_modes}.")

        limit = int(input_data.get("limit", 30))
        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        if mode == "top-games":
            proxy_url = await proxy_config.new_url() if proxy_config else None
            records = await run_top_games(limit, proxy_url)
            Actor.log.info(f"mode=top-games: {len(records)} record(s)")
            await Actor.push_data(records)
            return

        if mode == "top-streams":
            proxy_url = await proxy_config.new_url() if proxy_config else None
            records = await run_top_streams(limit, proxy_url)
            Actor.log.info(f"mode=top-streams: {len(records)} record(s)")
            await Actor.push_data(records)
            return

        if mode == "game-streams":
            game_names = list(input_data.get("gameNames") or [])
            if input_data.get("gameName"):
                game_names.insert(0, input_data["gameName"])
            if not game_names:
                raise input_error("Provide 'gameName' or 'gameNames' when mode is 'game-streams'.")
            seen = set()
            game_names = [g for g in game_names if not (g in seen or seen.add(g))]

            max_concurrency = int(input_data.get("maxConcurrency", 4))
            sem = asyncio.Semaphore(max_concurrency)

            async def _bounded_game(game_name: str):
                async with sem:
                    proxy_url = await proxy_config.new_url() if proxy_config else None
                    records = await run_game_streams(game_name, limit, proxy_url)
                    await Actor.push_data(records)

            Actor.log.info(f"mode=game-streams: {len(game_names)} game(s), maxConcurrency={max_concurrency}")
            await asyncio.gather(*(_bounded_game(g) for g in game_names))
            return

        # mode == "channel-rank"
        logins = list(input_data.get("logins") or [])
        if input_data.get("login"):
            logins.insert(0, input_data["login"])
        if not logins:
            raise input_error("Provide 'login' or 'logins' when mode is 'channel-rank'.")
        seen = set()
        logins = [l for l in logins if not (l in seen or seen.add(l))]

        max_concurrency = int(input_data.get("maxConcurrency", 4))
        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_channel(login: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                record = await run_channel_rank(login, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(f"mode=channel-rank: {len(logins)} channel(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded_channel(l) for l in logins))
