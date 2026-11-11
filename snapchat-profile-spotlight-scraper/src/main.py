"""Mode dispatch for the Snapchat scraper.

Four of the eight modes (profile / spotlight / highlights / lenses) read the
SAME profile document, so each of them costs exactly one HTTP request per
username -- the page carries profile, lenses, highlights and spotlight stats
together. ``related`` reuses that document again to walk Snapchat's own
"related accounts" graph, which is the only public discovery surface the site
exposes without login.
"""

import asyncio
import logging
import re

from apify import Actor

from src.client import (
    BlockedUpstream,
    ProfileNotFound,
    SnapchatClient,
    UnexpectedShape,
)
from src.constants import (
    DEFAULT_LOCALE,
    MODES,
    URL_LENS_HUB,
    URL_PROFILE,
    URL_SPOTLIGHT_HUB,
)
from src.extractor import (
    extract_error,
    profile_info,
    wrap_highlight,
    wrap_lens,
    wrap_profile,
    wrap_reference,
    wrap_spotlight,
    wrap_trending,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (BlockedUpstream, UnexpectedShape, RuntimeError, ConnectionError)

_USERNAME_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")


def normalize_username(raw: str) -> str:
    """Accepts 'nasa', '@nasa', 'snapchat.com/add/nasa' or a full profile URL."""
    value = (raw or "").strip()
    if not value:
        return ""
    if "snapchat.com" in value:
        value = value.split("snapchat.com", 1)[1]
        value = value.split("?")[0].split("#")[0]
        for prefix in ("/add/", "/@", "/t/", "/"):
            if value.startswith(prefix):
                value = value[len(prefix):]
                break
    value = value.lstrip("@").strip("/")
    value = value.split("/")[0]
    m = _USERNAME_RE.fullmatch(value)
    return m.group(0) if m else ""


async def fetch_profile_props(client: SnapchatClient, username: str, locale: str) -> dict:
    return await client.get_page_props(URL_PROFILE.format(username=username, locale=locale))


def _emit_for_mode(mode: str, username: str, props: dict) -> list[dict]:
    """Turn one profile document into the records the chosen mode asks for."""
    if mode == "profile":
        return [wrap_profile(username, props)]

    if mode == "spotlight":
        metas = props.get("spotlightStoryMetadata") or []
        highlights = props.get("spotlightHighlights") or []
        return [
            wrap_spotlight(username, i, meta, highlights[i] if i < len(highlights) else None)
            for i, meta in enumerate(metas)
        ]

    if mode == "highlights":
        out = []
        for i, story in enumerate(props.get("curatedHighlights") or []):
            out.append(wrap_highlight(username, i, story, "curated"))
        for i, story in enumerate(props.get("spotlightHighlights") or []):
            out.append(wrap_highlight(username, i, story, "spotlight"))
        live = props.get("story")
        if isinstance(live, dict) and live:
            out.append(wrap_highlight(username, 0, live, "live-story"))
        return out

    if mode == "lenses":
        return [wrap_lens(username, lens) for lens in props.get("lenses") or []]

    raise ValueError(f"_emit_for_mode does not handle mode {mode!r}")


async def run_usernames(
    mode: str,
    usernames: list[str],
    locale: str,
    max_items: int,
    max_concurrency: int,
    proxy_url_factory,
    push,
) -> int:
    """Shared driver for the four profile-document modes.

    Records stream out per username instead of being collected, so a run that
    dies halfway still leaves everything it already scraped in the dataset.
    """
    sem = asyncio.Semaphore(max_concurrency)
    pushed = 0
    lock = asyncio.Lock()

    async def one(raw: str):
        nonlocal pushed
        username = normalize_username(raw)
        if not username:
            await push([extract_error(raw, "invalid_username", "could not parse a Snapchat username from this input")])
            return
        async with sem:
            client = SnapchatClient(proxy_url=await proxy_url_factory())
            try:
                props = await fetch_profile_props(client, username, locale)
                records = _emit_for_mode(mode, username, props)
                if not records:
                    # An account really can have zero lenses/spotlights. Say so
                    # explicitly instead of returning nothing for that input.
                    info = profile_info(props)
                    records = [
                        extract_error(
                            username,
                            "empty_section",
                            f"profile exists (displayName={info.get('title')!r}) but has no {mode} content",
                        )
                    ]
            except ProfileNotFound:
                records = [extract_error(username, "not_found", "Snapchat returned 404 for this username")]
            except TRANSIENT as e:
                records = [extract_error(username, "blocked_or_transient", repr(e))]
            finally:
                await client.close()

            async with lock:
                room = max_items - pushed
                if room <= 0:
                    return
                records = records[:room]
                pushed += len(records)
            await push(records)

    await asyncio.gather(*(one(u) for u in usernames))
    return pushed


async def run_related(
    seeds: list[str],
    locale: str,
    depth: int,
    max_items: int,
    max_concurrency: int,
    proxy_url_factory,
    push,
) -> int:
    """Breadth-first walk of Snapchat's relatedAccountsInfo graph.

    Each profile document lists a handful of accounts Snapchat itself considers
    related; expanding them level by level turns a single seed into a topical
    account list. Seeds count as level 0, so depth=1 returns the seed plus its
    direct neighbours.
    """
    seen: set[str] = set()
    frontier = [u for u in (normalize_username(s) for s in seeds) if u]
    for bad in [s for s in seeds if not normalize_username(s)]:
        await push([extract_error(bad, "invalid_username", "could not parse a Snapchat username from this input")])
    seen.update(frontier)
    pushed = 0
    sem = asyncio.Semaphore(max_concurrency)

    for level in range(depth + 1):
        if not frontier or pushed >= max_items:
            break
        next_frontier: list[str] = []

        async def one(username: str):
            nonlocal pushed
            async with sem:
                client = SnapchatClient(proxy_url=await proxy_url_factory())
                try:
                    props = await fetch_profile_props(client, username, locale)
                except ProfileNotFound:
                    await push([extract_error(username, "not_found", "Snapchat returned 404 for this username")])
                    return
                except TRANSIENT as e:
                    await push([extract_error(username, "blocked_or_transient", repr(e))])
                    return
                finally:
                    await client.close()

                record = wrap_profile(username, props)
                record["relatedDepth"] = level
                if pushed >= max_items:
                    return
                pushed += 1
                await push([record])
                for neighbour in record.get("relatedAccounts") or []:
                    name = neighbour.get("username")
                    if name and name not in seen:
                        seen.add(name)
                        next_frontier.append(name)

        await asyncio.gather(*(one(u) for u in frontier))
        frontier = next_frontier[: max(0, max_items - pushed)]
        log.info(f"related: level {level} done, {pushed} profile(s), next level {len(frontier)}")

    return pushed


async def run_trending(locale: str, max_items: int, proxy_url: str | None) -> list[dict]:
    client = SnapchatClient(proxy_url=proxy_url)
    try:
        props = await client.get_page_props(URL_SPOTLIGHT_HUB.format(locale=locale))
        stories = ((props.get("spotlightFeed") or {}).get("spotlightStories")) or []
        if not stories:
            return [extract_error("trending", "empty_section", "the Spotlight hub returned no stories")]
        return [wrap_trending(i, item) for i, item in enumerate(stories)][:max_items]
    except TRANSIENT as e:
        return [extract_error("trending", "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_top_lenses(locale: str, max_items: int, proxy_url: str | None) -> list[dict]:
    client = SnapchatClient(proxy_url=proxy_url)
    try:
        props = await client.get_page_props(URL_LENS_HUB.format(locale=locale))
        lenses = props.get("topLenses") or []
        if not lenses:
            return [extract_error("top-lenses", "empty_section", "the Lens hub returned no lenses")]
        selected = next(
            (c.get("displayName") or c.get("name") for c in props.get("categories") or [] if c.get("isSelected")),
            None,
        )
        return [wrap_lens("top-lenses", lens, selected) for lens in lenses][:max_items]
    except TRANSIENT as e:
        return [extract_error("top-lenses", "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_reference(locale: str, proxy_url: str | None) -> list[dict]:
    """Probe each public surface live rather than asserting it from a table --
    a surface that quietly closes should show up in the data, not in a support
    ticket."""
    client = SnapchatClient(proxy_url=proxy_url)
    records: list[dict] = []
    probes = [
        ("profile", URL_PROFILE.format(username="nasa", locale=locale)),
        ("spotlight-hub", URL_SPOTLIGHT_HUB.format(locale=locale)),
        ("lens-hub", URL_LENS_HUB.format(locale=locale)),
    ]
    try:
        for surface, url in probes:
            try:
                props = await client.get_page_props(url)
            except ProfileNotFound:
                records.append(wrap_reference(surface, url, False, "404 from upstream"))
                continue
            except TRANSIENT as e:
                records.append(wrap_reference(surface, url, False, repr(e)))
                continue

            if surface == "profile":
                info = profile_info(props)
                sample = {
                    "username": info.get("username"),
                    "subscriberCount": info.get("subscriberCount"),
                    "lenses": len(props.get("lenses") or []),
                    "curatedHighlights": len(props.get("curatedHighlights") or []),
                    "spotlightStories": len(props.get("spotlightStoryMetadata") or []),
                    "relatedAccounts": len(info.get("relatedAccountsInfo") or []),
                }
                ok = bool(info.get("username"))
            elif surface == "spotlight-hub":
                stories = ((props.get("spotlightFeed") or {}).get("spotlightStories")) or []
                sample = {"stories": len(stories)}
                ok = bool(stories)
            else:
                sample = {
                    "topLenses": len(props.get("topLenses") or []),
                    "categories": [c.get("name") for c in props.get("categories") or []],
                }
                ok = bool(props.get("topLenses"))

            sample["buildId"] = props.get("_buildId")
            records.append(wrap_reference(surface, url, ok, "payload parsed" if ok else "payload empty", sample))
        return records
    finally:
        await client.close()


def _clean_usernames(input_data: dict) -> list[str]:
    raw = list(input_data.get("usernames") or [])
    single = input_data.get("username")
    if single:
        raw.insert(0, single)
    out: list[str] = []
    for item in raw:
        if item and item not in out:
            out.append(item)
    return out


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "profile")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        locale = (input_data.get("locale") or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE
        max_items = int(input_data.get("maxItems", 200))
        max_concurrency = int(input_data.get("maxConcurrency", 4))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def new_proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        async def push(records: list[dict]):
            if records:
                await Actor.push_data(records)

        if mode == "reference":
            records = await run_reference(locale, await new_proxy_url())
            Actor.log.info(f"mode=reference: {len(records)} surface(s) probed")
            await push(records)
            return

        if mode == "trending":
            records = await run_trending(locale, max_items, await new_proxy_url())
            Actor.log.info(f"mode=trending -> {len(records)} record(s)")
            await push(records)
            return

        if mode == "top-lenses":
            records = await run_top_lenses(locale, max_items, await new_proxy_url())
            Actor.log.info(f"mode=top-lenses -> {len(records)} record(s)")
            await push(records)
            return

        usernames = _clean_usernames(input_data)
        if not usernames:
            raise input_error(
                f"Provide 'username' or 'usernames' when mode is '{mode}'. "
                f"Only 'trending', 'top-lenses' and 'reference' run without one."
            )

        if mode == "related":
            depth = max(0, min(int(input_data.get("relatedDepth", 1)), 3))
            count = await run_related(
                usernames, locale, depth, max_items, max_concurrency, new_proxy_url, push
            )
            Actor.log.info(f"mode=related seeds={len(usernames)} depth={depth} -> {count} profile(s)")
            return

        count = await run_usernames(
            mode, usernames, locale, max_items, max_concurrency, new_proxy_url, push
        )
        Actor.log.info(f"mode={mode} usernames={len(usernames)} -> {count} record(s)")
