"""The nine extraction modes, and the input resolution they share.

Inputs are deliberately forgiving. A buyer pasting things out of Discord has a
`discord.gg/python`, a `discord.com/servers/python-267624335836053506`, a bare
`267624335836053506` and a bare `python` in front of them, and cannot be
expected to know which of those the API wants. `resolve_target` accepts all of
them and works out what it is holding.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any, AsyncIterator, Callable

from .client import (
    DiscordBlocked,
    DiscordClient,
    DiscordForbidden,
    DiscordNotFound,
)
from .constants import (
    DISCOVERY_CATEGORIES,
    DISCOVERY_PAGE_SIZE,
    SITE_ROOT,
)
from .parsers import (
    error_record,
    now_iso,
    parse_bot_profile,
    parse_discovery_hit,
    parse_game_profile,
    parse_invite,
    parse_server_profile,
    parse_trending_game,
    parse_widget,
    record,
    snowflake_created_at,
)
from .serialized import SerializedParseError, find_loader

log = logging.getLogger("discord.modes")

SNOWFLAKE_ONLY = re.compile(r"^\d{15,22}$")
WEEK_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Budget:
    """A shared ceiling on dataset rows for the whole run."""

    def __init__(self, limit: int) -> None:
        self.limit = max(0, int(limit or 0))
        self.used = 0

    @property
    def exhausted(self) -> bool:
        return self.limit > 0 and self.used >= self.limit

    def take(self, n: int = 1) -> bool:
        if self.exhausted:
            return False
        self.used += n
        return True

    @property
    def remaining(self) -> int | None:
        return None if self.limit == 0 else max(0, self.limit - self.used)


# -- input resolution ------------------------------------------------------

class Target:
    """What a single user-supplied string turned out to be.

    Exactly one of `guild_id` and `invite_code` is guaranteed; both are set
    once an invite has been resolved.
    """

    __slots__ = ("raw", "guild_id", "invite_code", "slug")

    def __init__(
        self,
        raw: str,
        guild_id: str | None = None,
        invite_code: str | None = None,
        slug: str | None = None,
    ) -> None:
        self.raw = raw
        self.guild_id = guild_id
        self.invite_code = invite_code
        self.slug = slug

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Target({self.raw!r}, guild_id={self.guild_id}, invite={self.invite_code})"


def resolve_target(raw: str) -> Target:
    """Work out what a user-supplied server reference actually is.

    Accepted, in the order they are tested:

        https://discord.com/servers/python-267624335836053506   discovery page
        https://discord.com/servers/267624335836053506          bare id page
        https://discord.gg/python                               invite (vanity)
        https://discord.com/invite/B9qbPSzX                     invite (random)
        267624335836053506                                      guild snowflake
        python                                                  invite code

    A bare non-numeric string is read as an invite code rather than a vanity
    URL, because they are the same thing: Discord resolves a vanity through the
    very same /invites/{code} endpoint.
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty target")

    if "://" in text or text.startswith(("discord.com", "discord.gg", "www.discord")):
        url = text if "://" in text else "https://" + text
        parsed = urllib.parse.urlparse(url)
        host = (parsed.netloc or "").lower().removeprefix("www.")
        parts = [p for p in (parsed.path or "").split("/") if p]

        if host == "discord.gg" and parts:
            return Target(text, invite_code=parts[0])
        if host in ("discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"):
            if parts and parts[0] == "invite" and len(parts) > 1:
                return Target(text, invite_code=parts[1])
            if parts and parts[0] == "servers" and len(parts) > 1:
                slug = urllib.parse.unquote(parts[1])
                # The trailing snowflake is the only part Discord keys on; the
                # slug in front of it is decoration and may be wrong.
                tail = slug.rsplit("-", 1)[-1]
                if SNOWFLAKE_ONLY.match(tail):
                    return Target(text, guild_id=tail, slug=slug)
                if SNOWFLAKE_ONLY.match(slug):
                    return Target(text, guild_id=slug, slug=slug)
                raise ValueError(
                    f"{text!r} is a /servers/ URL with no guild id at the end. "
                    "Discord keys these on the trailing snowflake, e.g. "
                    "/servers/python-267624335836053506."
                )
            if parts and parts[0] == "channels" and len(parts) > 1 and SNOWFLAKE_ONLY.match(parts[1]):
                # An app deep link. The first id is the guild.
                return Target(text, guild_id=parts[1])
        raise ValueError(
            f"{text!r} is not a Discord server, invite or discovery URL."
        )

    if SNOWFLAKE_ONLY.match(text):
        return Target(text, guild_id=text)
    return Target(text, invite_code=text)


def as_strings(raw: Any) -> list[str]:
    """Accept both shapes Apify's array editors produce.

    The console's requestListSources editor emits `[{"url": "..."}]`; a run
    started from the API or another actor usually sends plain strings.
    """
    out: list[str] = []
    for entry in raw or []:
        if isinstance(entry, str):
            value = entry.strip()
        elif isinstance(entry, dict):
            value = str(entry.get("url") or entry.get("value") or "").strip()
        else:
            continue
        if value:
            out.append(value)
    return out


def _category_path(name: str) -> str:
    """Build a category path, rejecting the 45 categories with no page.

    Discord's Discovery has ~50 category ids but only five of them are
    browsable; `/servers/finance` is a 404 even though Finance is a real
    category id that appears on server records. Failing here with the list is
    far kinder than letting the run collect five 404 rows.
    """
    key = (name or "").strip().lower()
    aliases = {
        "science": "science & tech",
        "tech": "science & tech",
        "science and tech": "science & tech",
        "science & technology": "science & tech",
    }
    key = aliases.get(key, key)
    if key not in DISCOVERY_CATEGORIES:
        raise ValueError(
            f"{name!r} has no Discovery category page. Discord publishes only "
            f"{', '.join(repr(c) for c in DISCOVERY_CATEGORIES)}. Other "
            "categories (Cryptocurrency, Finance, Anime & Manga, Memes, "
            "Esports and the rest) exist as tags on server records but have no "
            "browsable page -- reach those with a keyword search instead."
        )
    # A literal space and ampersand is what the live path uses; quote() keeps
    # them as %20 and %26 rather than turning the space into a plus sign.
    return "/servers/" + urllib.parse.quote(key, safe="")


# -- discovery listing (shared by search and category) ---------------------

async def _walk_discovery(
    client: DiscordClient,
    path: str,
    query: str | None,
    *,
    mode: str,
    max_pages: int,
    budget: Budget,
    label: str,
) -> AsyncIterator[dict[str, Any]]:
    """Page through a Discovery listing 12 results at a time.

    `nbHits` is reported but never used as a loop bound: the index is live and
    the number drifts by hundreds between consecutive requests. The loop stops
    on an empty page, which is what the end of the index actually looks like.
    """
    offset = 0
    rank = 0
    pages = 0
    seen: set[str] = set()

    while pages < max_pages and not budget.exhausted:
        params: dict[str, Any] = {}
        if query:
            # `query`, never `q`: Discord accepts `q`, discards it, and answers
            # HTTP 200 with the unfiltered home listing.
            params["query"] = query
        if offset:
            params["offset"] = offset

        try:
            url, html = await client.get_page(path, params=params or None)
            loader = find_loader(html, "searchResults")
        except DiscordNotFound:
            yield error_record(label, "not_found", f"{path} does not exist", mode=mode)
            return
        except (DiscordBlocked, DiscordForbidden) as exc:
            yield error_record(label, "fetch_failed", str(exc), mode=mode, query=query)
            return
        except SerializedParseError as exc:
            yield error_record(label, "parse_failed", str(exc), mode=mode, query=query)
            return

        results = loader.get("searchResults") or {}
        hits = results.get("hits") or []
        if pages == 0:
            log.info(
                "%s: Discord reports about %s matching servers (an estimate -- "
                "the index is live). Walking %d per request.",
                label, results.get("nbHits"), DISCOVERY_PAGE_SIZE,
            )
        if not hits:
            log.info("%s: no more results at offset %d.", label, offset)
            return

        for hit in hits:
            if not isinstance(hit, dict):
                continue
            if budget.exhausted:
                return
            data = parse_discovery_hit(hit)
            guild_id = data.get("guildId") or ""
            if guild_id and guild_id in seen:
                # The index reorders live, so a server can land on two
                # consecutive pages. Emitting it twice would corrupt any count
                # the buyer runs over the dataset.
                continue
            if guild_id:
                seen.add(guild_id)
            rank += 1
            budget.take()
            yield record(
                "discovery_result", guild_id, data,
                mode=mode, source_url=url, query=query, rank=rank, offset=offset,
            )

        offset += DISCOVERY_PAGE_SIZE
        pages += 1


# -- modes -----------------------------------------------------------------

async def mode_discovery_search(
    client: DiscordClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    max_pages = int(opts.get("maxPagesPerTarget") or 5)
    for keyword in opts["searchKeywords"]:
        if budget.exhausted:
            return
        async for rec in _walk_discovery(
            client, "/servers", keyword,
            mode="discoverySearch", max_pages=max_pages, budget=budget,
            label=f"search:{keyword}",
        ):
            yield rec


async def mode_discovery_category(
    client: DiscordClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    max_pages = int(opts.get("maxPagesPerTarget") or 5)
    for name in opts["categories"]:
        if budget.exhausted:
            return
        try:
            path = _category_path(name)
        except ValueError as exc:
            yield error_record(name, "unsupported_category", str(exc), mode="discoveryCategory")
            continue
        async for rec in _walk_discovery(
            client, path, None,
            mode="discoveryCategory", max_pages=max_pages, budget=budget,
            label=f"category:{name}",
        ):
            yield rec


async def _fetch_invite(client: DiscordClient, code: str) -> dict[str, Any]:
    return await client.get_api(
        f"/invites/{urllib.parse.quote(code, safe='')}",
        params={"with_counts": "true", "with_expiration": "true"},
    )


async def _fetch_profile(client: DiscordClient, target: Target) -> tuple[str, dict[str, Any]]:
    """Fetch a discovery profile page. The slug is cosmetic; the id is not."""
    path = f"/servers/{target.slug}" if target.slug else f"/servers/{target.guild_id}"
    url, html = await client.get_page(path)
    return url, find_loader(html, "guild")


async def mode_server_profile(
    client: DiscordClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    for raw in opts["serverTargets"]:
        if budget.exhausted:
            return
        try:
            target = resolve_target(raw)
        except ValueError as exc:
            yield error_record(raw, "unsupported_input", str(exc), mode="serverProfile")
            continue

        # A vanity or invite code has no guild id yet, and the profile page
        # needs one. One extra API call turns any accepted input into a
        # profile lookup.
        if not target.guild_id and target.invite_code:
            try:
                invite = await _fetch_invite(client, target.invite_code)
                target.guild_id = str((invite.get("guild") or {}).get("id") or "")
            except DiscordNotFound:
                yield error_record(
                    raw, "not_found",
                    f"invite {target.invite_code!r} is unknown or expired",
                    mode="serverProfile",
                )
                continue
            except (DiscordBlocked, DiscordForbidden) as exc:
                yield error_record(raw, "fetch_failed", str(exc), mode="serverProfile")
                continue
        if not target.guild_id:
            yield error_record(
                raw, "unresolvable_target",
                "could not resolve this input to a guild id", mode="serverProfile",
            )
            continue

        try:
            url, loader = await _fetch_profile(client, target)
        except DiscordNotFound:
            yield error_record(
                raw, "not_in_discovery",
                f"guild {target.guild_id} has no Discovery page. Only servers "
                "that opted into Server Discovery have one; use the "
                "inviteLookup mode, which works for any server with an invite.",
                mode="serverProfile",
            )
            continue
        except (DiscordBlocked, DiscordForbidden) as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="serverProfile")
            continue
        except SerializedParseError as exc:
            yield error_record(raw, "parse_failed", str(exc), mode="serverProfile")
            continue

        budget.take()
        yield record(
            "server_profile", target.guild_id, parse_server_profile(loader),
            mode="serverProfile", source_url=url,
        )


async def mode_invite_lookup(
    client: DiscordClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    for raw in opts["inviteCodes"]:
        if budget.exhausted:
            return
        try:
            target = resolve_target(raw)
        except ValueError as exc:
            yield error_record(raw, "unsupported_input", str(exc), mode="inviteLookup")
            continue
        code = target.invite_code
        if not code:
            yield error_record(
                raw, "unsupported_input",
                "this is a guild id, and Discord has no id-to-invite lookup. "
                "Supply the invite code or discord.gg URL instead.",
                mode="inviteLookup",
            )
            continue
        try:
            payload = await _fetch_invite(client, code)
        except DiscordNotFound:
            yield error_record(
                raw, "not_found",
                f"invite {code!r} is unknown, expired, revoked or used up",
                mode="inviteLookup",
            )
            continue
        except (DiscordBlocked, DiscordForbidden) as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="inviteLookup")
            continue

        data = parse_invite(payload, code)
        budget.take()
        yield record(
            "invite", data.get("guildId"), data,
            mode="inviteLookup",
            source_url=f"{SITE_ROOT}/api/v10/invites/{code}",
        )


async def _resolve_guild_id(client: DiscordClient, target: Target) -> str | None:
    if target.guild_id:
        return target.guild_id
    if target.invite_code:
        invite = await _fetch_invite(client, target.invite_code)
        return str((invite.get("guild") or {}).get("id") or "") or None
    return None


async def mode_server_widget(
    client: DiscordClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    include_members = bool(opts.get("includeWidgetMembers", True))
    for raw in opts["serverTargets"]:
        if budget.exhausted:
            return
        try:
            target = resolve_target(raw)
            guild_id = await _resolve_guild_id(client, target)
        except ValueError as exc:
            yield error_record(raw, "unsupported_input", str(exc), mode="serverWidget")
            continue
        except DiscordNotFound:
            yield error_record(raw, "not_found", "invite is unknown or expired", mode="serverWidget")
            continue
        except (DiscordBlocked, DiscordForbidden) as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="serverWidget")
            continue
        if not guild_id:
            yield error_record(raw, "unresolvable_target", "no guild id", mode="serverWidget")
            continue

        try:
            payload = await client.get_api(f"/guilds/{guild_id}/widget.json")
        except DiscordForbidden:
            yield error_record(
                raw, "widget_disabled",
                f"guild {guild_id} has the server widget switched off. Most "
                "servers do -- it is opt-in under Server Settings > Widget. "
                "Use inviteLookup for member and online counts, which need no "
                "widget.",
                mode="serverWidget",
            )
            continue
        except DiscordNotFound:
            yield error_record(raw, "not_found", f"guild {guild_id} not found", mode="serverWidget")
            continue
        except DiscordBlocked as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="serverWidget")
            continue

        data = parse_widget(payload)
        if not include_members:
            data.pop("members", None)
        budget.take()
        yield record(
            "widget", guild_id, data,
            mode="serverWidget",
            source_url=f"{SITE_ROOT}/api/v10/guilds/{guild_id}/widget.json",
        )


async def mode_server_snapshot(
    client: DiscordClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """One row per server per run, built for appending to a time series.

    This is the growth-tracking mode. Run it on a schedule against the same
    list and every run appends one comparable row per server, so a dataset
    accumulates membership, online count and boost history without any
    diffing on the buyer's side. It combines the three open surfaces and says
    which of them answered, because widget and Discovery coverage vary per
    server while the invite never does.
    """
    for raw in opts["serverTargets"]:
        if budget.exhausted:
            return
        try:
            target = resolve_target(raw)
        except ValueError as exc:
            yield error_record(raw, "unsupported_input", str(exc), mode="serverSnapshot")
            continue

        sources: list[str] = []
        snapshot: dict[str, Any] = {
            "input": raw,
            "snapshotAt": now_iso(),
            "guildId": target.guild_id,
            "inviteCode": target.invite_code,
        }

        # 1. The invite, when there is one. It is the only surface that gives
        #    live counts for a server that never joined Discovery.
        if target.invite_code:
            try:
                invite = parse_invite(
                    await _fetch_invite(client, target.invite_code), target.invite_code
                )
                sources.append("invite")
                target.guild_id = target.guild_id or invite.get("guildId")
                snapshot.update({
                    "guildId": target.guild_id,
                    "name": invite.get("name"),
                    "description": invite.get("description"),
                    "memberCount": invite.get("memberCount"),
                    "onlineCount": invite.get("onlineCount"),
                    "engagementRatePct": invite.get("engagementRatePct"),
                    "boostCount": invite.get("boostCount"),
                    "boostTier": invite.get("boostTier"),
                    "verificationLevel": invite.get("verificationLevel"),
                    "isPartnered": invite.get("isPartnered"),
                    "isVerified": invite.get("isVerified"),
                    "isDiscoverable": invite.get("isDiscoverable"),
                    "features": invite.get("features"),
                    "inviteUrl": invite.get("inviteUrl"),
                    "inviteExpiresAt": invite.get("expiresAt"),
                    "iconUrl": invite.get("iconUrl"),
                })
            except DiscordNotFound:
                snapshot["inviteError"] = "unknown or expired invite"
            except (DiscordBlocked, DiscordForbidden) as exc:
                snapshot["inviteError"] = str(exc)

        if not target.guild_id:
            yield error_record(
                raw, "unresolvable_target",
                "could not resolve this input to a guild id "
                f"({snapshot.get('inviteError') or 'no invite code supplied'})",
                mode="serverSnapshot",
            )
            continue

        snapshot["createdAt"] = snowflake_created_at(target.guild_id)

        # 2. The Discovery profile, for servers that opted in. Adds the long
        #    description, the outbound social links and the real created_at.
        try:
            url, loader = await _fetch_profile(client, target)
            profile = parse_server_profile(loader)
            sources.append("discovery")
            snapshot.update({
                "name": snapshot.get("name") or profile.get("name"),
                "description": snapshot.get("description") or profile.get("description"),
                "about": profile.get("about"),
                "socialLinks": profile.get("socialLinks"),
                "website": profile.get("website"),
                "keywords": profile.get("keywords"),
                "primaryCategoryName": profile.get("primaryCategoryName"),
                "categories": profile.get("categories"),
                "discoveryUrl": profile.get("discoveryUrl"),
                "createdAt": profile.get("createdAt") or snapshot.get("createdAt"),
            })
            # Discovery counts are computed on a different schedule from the
            # invite's, so they are kept side by side rather than merged.
            snapshot["discoveryMemberCount"] = profile.get("memberCount")
            snapshot["discoveryOnlineCount"] = profile.get("onlineCount")
            if snapshot.get("memberCount") is None:
                snapshot["memberCount"] = profile.get("memberCount")
                snapshot["onlineCount"] = profile.get("onlineCount")
                snapshot["engagementRatePct"] = profile.get("engagementRatePct")
                snapshot["boostCount"] = profile.get("boostCount")
            _ = url
        except (DiscordNotFound, DiscordBlocked, DiscordForbidden, SerializedParseError):
            snapshot["inDiscovery"] = False
        else:
            snapshot["inDiscovery"] = True

        # 3. The widget, for the minority of servers that publish one. It is
        #    the only live-activity signal on the open surface.
        try:
            widget = parse_widget(await client.get_api(f"/guilds/{target.guild_id}/widget.json"))
            sources.append("widget")
            snapshot.update({
                "widgetEnabled": True,
                "widgetOnlineCount": widget.get("onlineCount"),
                "membersInVoice": widget.get("membersInVoice"),
                "voiceChannelCount": len(widget.get("voiceChannels") or []),
                "statusBreakdown": widget.get("statusBreakdown"),
                "widgetInstantInvite": widget.get("instantInvite"),
            })
            if snapshot.get("memberCount") is None:
                snapshot["onlineCount"] = widget.get("onlineCount")
        except (DiscordForbidden, DiscordNotFound, DiscordBlocked):
            snapshot["widgetEnabled"] = False

        if not sources:
            yield error_record(
                raw, "no_open_surface",
                f"guild {target.guild_id} answered on none of the three open "
                "surfaces (invite, Discovery profile, widget). A guild id on "
                "its own is only resolvable if the server is in Discovery or "
                "publishes a widget -- supply an invite code instead.",
                mode="serverSnapshot",
            )
            continue

        snapshot["sources"] = sources
        budget.take()
        yield record(
            "server_snapshot", target.guild_id, snapshot,
            mode="serverSnapshot",
            source_url=snapshot.get("discoveryUrl") or snapshot.get("inviteUrl"),
        )


async def mode_trending_games(
    client: DiscordClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    """The weekly chart, optionally walked backwards through history.

    Two traps shape this mode. `?week=` is a decoy Discord discards -- the
    historical week is a PATH segment, `/trending-games/2026-09-10`. And a date
    Discord has no chart for does NOT answer 404: `/trending-games/1999-01-01`
    returns HTTP 200 carrying the CURRENT week. So the chain follows
    `prev_week_date` out of each payload rather than stepping dates by seven,
    and every response is checked against the week that was asked for; without
    both, a history walk would quietly collect the same current chart over and
    over and look like it had worked.
    """
    weeks = max(1, int(opts.get("weeksOfHistory") or 1))
    category = (opts.get("gameCategory") or "").strip()
    start = (opts.get("startWeekDate") or "").strip()
    if start and not WEEK_DATE_RE.match(start):
        yield error_record(
            start, "unsupported_input",
            "startWeekDate must look like 2026-09-10 (the week_date Discord "
            "publishes on the chart), or be left empty for the current week.",
            mode="trendingGames",
        )
        return

    base = "/trending-games"
    if category:
        base += "/category/" + urllib.parse.quote(category.lower().replace(" ", "-"), safe="")

    next_date: str | None = start or None
    seen_weeks: set[str] = set()

    for _ in range(weeks):
        if budget.exhausted:
            return
        # The date is appended last either way: /trending-games/<date> and
        # /trending-games/category/<slug>/<date> both resolve.
        path = f"{base}/{next_date}" if next_date else base
        requested = next_date
        try:
            url, html = await client.get_page(path)
            loader = find_loader(html, "data")
        except DiscordNotFound:
            yield error_record(
                path, "not_found",
                f"Discord publishes no trending chart at {path}",
                mode="trendingGames",
            )
            return
        except (DiscordBlocked, DiscordForbidden) as exc:
            yield error_record(path, "fetch_failed", str(exc), mode="trendingGames")
            return
        except SerializedParseError as exc:
            yield error_record(path, "parse_failed", str(exc), mode="trendingGames")
            return

        data = loader.get("data") or {}
        week_date = data.get("week_date")

        if requested and week_date and week_date != requested:
            # Discord served a different week than the path asked for, which
            # is what it does for any date it has no chart for. Saying so is
            # the difference between "no data for that week" and a dataset
            # quietly full of duplicate current-week rows.
            yield error_record(
                path, "week_not_published",
                f"asked for the week of {requested} and Discord answered with "
                f"{week_date} instead. It serves the current chart for any "
                "date it has no chart for, rather than a 404.",
                mode="trendingGames",
            )
            return
        if week_date in seen_weeks:
            log.info("Chart for %s already collected; stopping.", week_date)
            return
        if week_date:
            seen_weeks.add(week_date)

        games = data.get("games") or []
        log.info("Trending chart for week %s: %d games.", week_date, len(games))
        for game in games:
            if not isinstance(game, dict) or budget.exhausted:
                break
            budget.take()
            yield record(
                "trending_game",
                f"{week_date}:{game.get('application_id')}",
                parse_trending_game(game, week_date),
                mode="trendingGames", source_url=url, rank=game.get("rank"),
                extra_meta={
                    "weekDate": week_date,
                    "publishedAt": data.get("published_at"),
                    "gameCategory": category or None,
                },
            )

        next_date = data.get("prev_week_date")
        if not next_date:
            log.info("No earlier week published; stopping.")
            return


async def mode_game_profile(
    client: DiscordClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    for raw in opts["gameTargets"]:
        if budget.exhausted:
            return
        text = raw.strip()
        if "://" in text:
            slug = urllib.parse.urlparse(text).path.rstrip("/").split("/")[-1]
        else:
            slug = text
        try:
            url, html = await client.get_page(f"/game/{urllib.parse.quote(slug, safe='')}")
            loader = find_loader(html, "data")
        except DiscordNotFound:
            yield error_record(
                raw, "not_found",
                f"no game page at /game/{slug}. These need the full "
                "slug-and-id form, e.g. valheim-1124358970618953818, which the "
                "trendingGames mode emits as gameUrl.",
                mode="gameProfile",
            )
            continue
        except (DiscordBlocked, DiscordForbidden) as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="gameProfile")
            continue
        except SerializedParseError as exc:
            yield error_record(raw, "parse_failed", str(exc), mode="gameProfile")
            continue

        data = parse_game_profile(loader.get("data") or {})
        budget.take()
        yield record(
            "game_profile", data.get("applicationId"), data,
            mode="gameProfile", source_url=url,
        )


async def mode_bot_profile(
    client: DiscordClient, opts: dict[str, Any], budget: Budget
) -> AsyncIterator[dict[str, Any]]:
    for raw in opts["applicationIds"]:
        if budget.exhausted:
            return
        text = raw.strip()
        # Accept an oauth2 authorize link or an app-directory URL as well as a
        # bare id; both carry the id and both are what a buyer has to hand.
        match = re.search(r"(\d{15,22})", text)
        if not match:
            yield error_record(
                raw, "unsupported_input",
                "no application id found. Supply the numeric id, or any URL "
                "containing it (an oauth2 authorize link works).",
                mode="botProfile",
            )
            continue
        app_id = match.group(1)
        try:
            payload = await client.get_api(f"/applications/{app_id}/rpc")
        except DiscordNotFound:
            yield error_record(raw, "not_found", f"no application {app_id}", mode="botProfile")
            continue
        except (DiscordBlocked, DiscordForbidden) as exc:
            yield error_record(raw, "fetch_failed", str(exc), mode="botProfile")
            continue

        budget.take()
        yield record(
            "bot_profile", app_id, parse_bot_profile(payload),
            mode="botProfile",
            source_url=f"{SITE_ROOT}/api/v10/applications/{app_id}/rpc",
        )


ModeFn = Callable[[DiscordClient, dict[str, Any], Budget], AsyncIterator[dict[str, Any]]]

MODES: dict[str, ModeFn] = {
    "discoverySearch": mode_discovery_search,
    "discoveryCategory": mode_discovery_category,
    "serverProfile": mode_server_profile,
    "inviteLookup": mode_invite_lookup,
    "serverWidget": mode_server_widget,
    "serverSnapshot": mode_server_snapshot,
    "trendingGames": mode_trending_games,
    "gameProfile": mode_game_profile,
    "botProfile": mode_bot_profile,
}

# Which input array each mode cannot run without. trendingGames is absent
# because it has a meaningful default: this week's chart.
MODE_REQUIRED_INPUT: dict[str, tuple[str, ...]] = {
    "discoverySearch": ("searchKeywords",),
    "discoveryCategory": ("categories",),
    "serverProfile": ("serverTargets",),
    "inviteLookup": ("inviteCodes",),
    "serverWidget": ("serverTargets",),
    "serverSnapshot": ("serverTargets",),
    "gameProfile": ("gameTargets",),
    "botProfile": ("applicationIds",),
}
