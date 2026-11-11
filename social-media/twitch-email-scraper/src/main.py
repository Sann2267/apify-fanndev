import asyncio
import logging
import re
from urllib.parse import urlparse

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import IntegrityCheckFailed, TwitchClient
from src.constants import MAX_FIRST_STREAMS
from src.extractor import (
    CHANNEL_EMAIL_QUERY,
    GAME_STREAMS_DISCOVERY_QUERY,
    extract_channel_emails,
    extract_error,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)


async def run_channel_email(login: str, proxy_url: str | None) -> dict:
    client = TwitchClient(proxy_url=proxy_url)
    try:
        data = await client.graphql(CHANNEL_EMAIL_QUERY, {"login": login})
        return extract_channel_emails(data, login)
    except IntegrityCheckFailed as e:
        return extract_error(login, "integrity_check_failed", repr(e))
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(login, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def discover_game_channels(game_name: str, limit: int, proxy_url: str | None) -> list[str]:
    first = min(limit, MAX_FIRST_STREAMS)
    client = TwitchClient(proxy_url=proxy_url)
    try:
        data = await client.graphql(GAME_STREAMS_DISCOVERY_QUERY, {"name": game_name, "first": first})
        game = data.get("game")
        if game is None:
            return []
        edges = (game.get("streams") or {}).get("edges") or []
        return [
            (edge.get("node") or {}).get("broadcaster", {}).get("login")
            for edge in edges
            if (edge.get("node") or {}).get("broadcaster", {}).get("login")
        ]
    finally:
        await client.close()


_LOGIN_RE = re.compile(r"^[a-z0-9_]{1,25}$")


def normalize_login(raw) -> str | None:
    """Accept a bare login, `@login`, or any twitch.tv URL and return the login.

    Users paste channel URLs (`https://www.twitch.tv/Pokimane/videos`) and
    `@handles`; sent verbatim they come back `channel_not_found` and the error
    row is billed to the user.
    """
    value = str(raw or "").strip()
    if not value:
        return None
    if "twitch.tv" in value.lower():
        if "://" not in value:
            value = "https://" + value
        parts = [p for p in urlparse(value).path.split("/") if p]
        value = parts[0] if parts else ""
    value = value.lstrip("@").strip().lower()
    return value if _LOGIN_RE.match(value) else None


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "channel")
        valid_modes = ("channel", "by-game")
        if mode not in valid_modes:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {valid_modes}.")

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        if mode == "channel":
            logins = list(input_data.get("logins") or [])
            if input_data.get("login"):
                logins.insert(0, input_data["login"])
            normalized = []
            for raw in logins:
                login = normalize_login(raw)
                if login:
                    normalized.append(login)
                else:
                    Actor.log.warning(f"Skipping {raw!r}: not a Twitch login or channel URL.")
            logins = normalized
            if not logins:
                raise input_error("Provide 'login' or 'logins' (a Twitch login, @login or channel URL) when mode is 'channel'.")
        else:
            game_name = input_data.get("gameName")
            if not game_name:
                raise input_error("Provide 'gameName' when mode is 'by-game'.")
            limit = int(input_data.get("limit", 30))
            discovery_proxy = await proxy_config.new_url() if proxy_config else None
            logins = await discover_game_channels(game_name, limit, discovery_proxy)
            if not logins:
                Actor.log.info(f"mode=by-game: no live channels found for game {game_name!r}")
                await Actor.push_data(extract_error(game_name, "game_not_found_or_empty"))
                return

        seen = set()
        logins = [l for l in logins if not (l in seen or seen.add(l))]

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded(login: str):
            async with sem:
                proxy_url = await proxy_config.new_url() if proxy_config else None
                record = await run_channel_email(login, proxy_url)
                await Actor.push_data(record)

        Actor.log.info(f"mode={mode}: {len(logins)} channel(s), maxConcurrency={max_concurrency}")
        await asyncio.gather(*(_bounded(l) for l in logins))
