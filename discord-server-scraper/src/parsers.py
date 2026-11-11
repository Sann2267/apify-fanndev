"""Turn Discord's raw payloads into the flat records this actor publishes.

Every record leaves here in one envelope -- item_type, id, data, metadata -- so
a single dataset can hold discovery hits, server profiles, invites, widgets,
trending games and diagnostics and still be joined on `id`.

Two normalisations are applied everywhere and are worth stating once:

* CDN hashes become URLs. Discord publishes `icon:"95a695..."` on API payloads
  and a ready-made URL on SSR payloads, for the same field. Buyers should not
  have to know which surface a row came from, so hashes are expanded here,
  including the `a_` prefix that means the asset is animated and must be
  requested as .gif rather than .png.
* `name_localizations` is dropped. Discord ships all 30 locales of every
  category name on every category of every hit -- roughly 1.8 KB per category,
  five categories per server, which is 90% of the payload and none of the
  information. The English name is kept.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from .constants import (
    CATEGORY_NAMES,
    CDN_ROOT,
    FEATURE_FLAGS,
    NSFW_LEVELS,
    SITE_ROOT,
    VERIFICATION_LEVELS,
)

# Discord snowflakes are 17-20 digits today; the range is widened a little so
# the actor does not start rejecting ids when the epoch rolls further on.
SNOWFLAKE_RE = re.compile(r"\b(\d{15,22})\b")
_DISCORD_EPOCH_MS = 1420070400000


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def snowflake_created_at(snowflake: str | int | None) -> str | None:
    """Every Discord id encodes its own creation time in its top 42 bits.

    This is how a server's age is reported for surfaces that do not publish
    `created_at` -- invites and widgets both omit it, while the discovery
    profile includes it. Deriving it means every record carries the field.
    """
    try:
        value = int(snowflake)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    millis = (value >> 22) + _DISCORD_EPOCH_MS
    try:
        return _dt.datetime.fromtimestamp(
            millis / 1000, _dt.timezone.utc
        ).isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError):
        return None


def _asset_url(kind: str, owner_id: str | None, value: Any, size: int = 256) -> str | None:
    """Expand a CDN hash into a URL, or pass an existing URL through.

    SSR payloads already hold URLs while API payloads hold bare hashes, and
    both reach this function from different modes for the same field.
    """
    if not value or not owner_id:
        return None
    text = str(value)
    if text.startswith(("http://", "https://")):
        return text
    # `a_` marks an animated asset; requesting it as .png returns a still
    # frame, which is usually not what the buyer wanted.
    ext = "gif" if text.startswith("a_") else "png"
    return f"{CDN_ROOT}/{kind}/{owner_id}/{text}.{ext}?size={size}"


def _clean_categories(raw: Any) -> list[dict[str, Any]]:
    """Keep id / name / is_primary, drop the 30-locale name table."""
    out: list[dict[str, Any]] = []
    for cat in raw or []:
        if isinstance(cat, dict):
            cid = cat.get("id")
            out.append({
                "id": cid,
                "name": cat.get("name") or CATEGORY_NAMES.get(cid),
                "isPrimary": bool(cat.get("is_primary")),
            })
        elif isinstance(cat, int):
            # `category_ids` on a profile payload is a plain list of numbers.
            out.append({
                "id": cat,
                "name": CATEGORY_NAMES.get(cat),
                "isPrimary": None,
            })
    return out


def _feature_flags(features: Any) -> dict[str, bool]:
    have = set(features or [])
    return {
        name: any(token in have for token in tokens)
        for name, tokens in FEATURE_FLAGS.items()
    }


def _engagement(members: Any, online: Any) -> float | None:
    """Online as a percentage of members, rounded to two decimals.

    This is the single most useful derived number on the whole surface: a
    150,000-member server with 400 people online is a dead shell bought or
    botted into existence, and a 9,000-member server with 2,000 online is worth
    a sponsorship email. Buyers otherwise compute it themselves on every row.
    """
    try:
        m, o = int(members), int(online)
    except (TypeError, ValueError):
        return None
    if m <= 0:
        return None
    return round(o * 100.0 / m, 2)


def record(
    item_type: str,
    record_id: Any,
    data: dict[str, Any],
    *,
    mode: str,
    source_url: str | None = None,
    query: str | None = None,
    rank: int | None = None,
    offset: int | None = None,
    parent_id: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "scrapedAt": now_iso(),
        "sourceUrl": source_url,
        "mode": mode,
    }
    if query is not None:
        meta["query"] = query
    if rank is not None:
        meta["rank"] = rank
    if offset is not None:
        meta["offset"] = offset
    if parent_id is not None:
        meta["parentId"] = parent_id
    if extra_meta:
        meta.update(extra_meta)
    return {
        "item_type": item_type,
        "id": None if record_id is None else str(record_id),
        "data": data,
        "metadata": meta,
    }


def error_record(
    subject: str, kind: str, detail: str = "", *, mode: str = "", **meta: Any
) -> dict[str, Any]:
    """A diagnostic row.

    The run never finishes with an empty dataset: a buyer joining on this
    output reads "no rows" as a crash, while an error row says exactly which
    input failed and why.
    """
    return record(
        "error",
        None,
        {"_error": kind, "_errorDetail": detail, "_input": subject},
        mode=mode,
        **meta,
    )


# -- discovery ------------------------------------------------------------

def parse_discovery_hit(hit: dict[str, Any]) -> dict[str, Any]:
    """One server from the Discovery index (search or category listing)."""
    guild_id = str(hit.get("id") or hit.get("objectID") or "")
    members = hit.get("approximate_member_count")
    online = hit.get("approximate_presence_count")
    vanity = hit.get("vanity_url_code")
    primary = hit.get("primary_category") or {}
    return {
        "guildId": guild_id,
        "name": hit.get("name"),
        "description": hit.get("description"),
        "memberCount": members,
        "onlineCount": online,
        "engagementRatePct": _engagement(members, online),
        "boostCount": hit.get("premium_subscription_count"),
        "vanityUrlCode": vanity,
        "inviteUrl": f"https://discord.gg/{vanity}" if vanity else None,
        "discoveryUrl": discovery_url(guild_id, hit.get("name")),
        "primaryCategoryId": hit.get("primary_category_id"),
        "primaryCategoryName": (
            primary.get("name")
            if isinstance(primary, dict)
            else CATEGORY_NAMES.get(hit.get("primary_category_id"))
        ),
        "categories": _clean_categories(hit.get("categories")),
        "keywords": hit.get("keywords") or [],
        "preferredLocale": hit.get("preferred_locale"),
        "isNsfw": bool(hit.get("nsfw_properties")),
        "nsfwProperties": hit.get("nsfw_properties"),
        "features": hit.get("features") or [],
        **_feature_flags(hit.get("features")),
        "iconUrl": _asset_url("icons", guild_id, hit.get("icon")),
        "splashUrl": _asset_url("discovery-splashes", guild_id, hit.get("discovery_splash"), 2048),
        "bannerUrl": _asset_url("banners", guild_id, hit.get("banner"), 1024),
        "createdAt": snowflake_created_at(guild_id),
        "isPublished": hit.get("is_published"),
        "autoRemoved": hit.get("auto_removed"),
    }


def parse_server_profile(loader: dict[str, Any]) -> dict[str, Any]:
    """A discoverable server's full public profile page.

    Carries four fields the search index does not: `about`, `social_links`,
    `created_at` and `reasons_to_join`. The social links are the reason this
    mode exists -- they are the community's own outbound contact points.
    """
    guild = loader.get("guild") or {}
    guild_id = str(guild.get("id") or "")
    members = guild.get("approximate_member_count")
    online = guild.get("approximate_presence_count")
    vanity = guild.get("vanity_url_code")
    reasons = [
        {"reason": r.get("reason"), "emoji": r.get("emoji_name")}
        for r in (guild.get("reasons_to_join") or [])
        if isinstance(r, dict)
    ]
    return {
        "guildId": guild_id,
        "name": guild.get("name"),
        "description": guild.get("description"),
        "about": guild.get("about"),
        "memberCount": members,
        "onlineCount": online,
        "engagementRatePct": _engagement(members, online),
        "boostCount": guild.get("premium_subscription_count"),
        "vanityUrlCode": vanity,
        "inviteUrl": f"https://discord.gg/{vanity}" if vanity else None,
        "discoveryUrl": discovery_url(guild_id, guild.get("name"), loader.get("slug")),
        "socialLinks": guild.get("social_links") or [],
        "website": guild.get("website"),
        "reasonsToJoin": reasons,
        "keywords": guild.get("keywords") or [],
        "primaryCategoryId": guild.get("primary_category_id"),
        "primaryCategoryName": CATEGORY_NAMES.get(guild.get("primary_category_id")),
        "categories": _clean_categories(guild.get("category_ids")),
        "preferredLocale": guild.get("preferred_locale"),
        "isNsfw": bool(guild.get("nsfw_properties")),
        "features": guild.get("features") or [],
        **_feature_flags(guild.get("features")),
        "iconUrl": _asset_url("icons", guild_id, guild.get("icon")),
        "splashUrl": _asset_url("discovery-splashes", guild_id, guild.get("discovery_splash"), 2048),
        "bannerUrl": _asset_url("banners", guild_id, guild.get("banner"), 1024),
        # The profile page publishes created_at outright; every other surface
        # has to derive it from the snowflake.
        "createdAt": guild.get("created_at") or snowflake_created_at(guild_id),
        "announcementChannels": loader.get("announcementChannels") or [],
        "isPublished": guild.get("is_published"),
    }


def discovery_url(guild_id: str, name: Any = None, slug: Any = None) -> str | None:
    """Build the canonical /servers/ URL.

    The slug is cosmetic -- Discord resolves a bare id and ignores a wrong
    slug, keying only on the trailing snowflake -- but a readable URL is what
    a human pastes into a browser, so the name is slugified when available.
    """
    if not guild_id:
        return None
    if slug:
        return f"{SITE_ROOT}/servers/{slug}"
    if name:
        text = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
        if text:
            return f"{SITE_ROOT}/servers/{text}-{guild_id}"
    return f"{SITE_ROOT}/servers/{guild_id}"


# -- invites ---------------------------------------------------------------

def parse_invite(payload: dict[str, Any], code: str) -> dict[str, Any]:
    """The universal resolver's output.

    Unlike every other mode this works for servers that were never listed in
    Discovery, which is the overwhelming majority of Discord. `profile` is a
    newer sibling of `guild` carrying the server tag and badge; it is not
    always present, so both are read and `guild` wins where they overlap.
    """
    guild = payload.get("guild") or {}
    profile = payload.get("profile") or {}
    guild_id = str(guild.get("id") or profile.get("id") or "")
    members = payload.get("approximate_member_count") or profile.get("member_count")
    online = payload.get("approximate_presence_count") or profile.get("online_count")
    channel = payload.get("channel") or {}
    inviter = payload.get("inviter") or {}
    vanity = guild.get("vanity_url_code")
    event = payload.get("guild_scheduled_event") or {}
    return {
        "inviteCode": code,
        "inviteUrl": f"https://discord.gg/{code}",
        "isVanityInvite": bool(vanity) and vanity == code,
        # null means the invite never expires, which is what a vanity URL and
        # most published invites are. It is not a missing value.
        "expiresAt": payload.get("expires_at"),
        "guildId": guild_id,
        "name": guild.get("name") or profile.get("name"),
        "description": guild.get("description") or profile.get("description"),
        "memberCount": members,
        "onlineCount": online,
        "engagementRatePct": _engagement(members, online),
        "boostCount": guild.get("premium_subscription_count"),
        "boostTier": guild.get("premium_tier"),
        "vanityUrlCode": vanity,
        "discoveryUrl": (
            discovery_url(guild_id, guild.get("name"))
            if "DISCOVERABLE" in (guild.get("features") or [])
            else None
        ),
        "verificationLevel": VERIFICATION_LEVELS.get(
            guild.get("verification_level"), guild.get("verification_level")
        ),
        "nsfwLevel": NSFW_LEVELS.get(guild.get("nsfw_level"), guild.get("nsfw_level")),
        "isNsfw": guild.get("nsfw"),
        "serverTag": profile.get("tag"),
        "serverTagBadgeUrl": (
            f"{CDN_ROOT}/guild-tag-badges/{guild_id}/{profile['badge_hash']}.png?size=64"
            if profile.get("badge_hash") and guild_id else None
        ),
        "features": guild.get("features") or [],
        **_feature_flags(guild.get("features")),
        "iconUrl": _asset_url("icons", guild_id, guild.get("icon")),
        "splashUrl": _asset_url("splashes", guild_id, guild.get("splash"), 2048),
        "bannerUrl": _asset_url("banners", guild_id, guild.get("banner"), 1024),
        "createdAt": snowflake_created_at(guild_id),
        "landingChannelId": channel.get("id"),
        "landingChannelName": channel.get("name"),
        "inviterId": inviter.get("id"),
        "inviterUsername": inviter.get("username"),
        "scheduledEventId": event.get("id"),
        "scheduledEventName": event.get("name"),
        "scheduledEventStartsAt": event.get("scheduled_start_time"),
    }


# -- widget ----------------------------------------------------------------

def parse_widget(payload: dict[str, Any]) -> dict[str, Any]:
    """Live activity for a server whose owner switched the widget on.

    The member entries are anonymised BY DISCORD: `id` is the member's index in
    this response ("0", "1", "2"...), never a user snowflake, and the avatar is
    a signed one-off URL. Treat it as a live sample of who is online and in
    which voice channel, never as an identity that survives between runs.
    """
    guild_id = str(payload.get("id") or "")
    members = payload.get("members") or []
    statuses: dict[str, int] = {}
    in_voice = 0
    parsed_members: list[dict[str, Any]] = []
    for idx, m in enumerate(members):
        if not isinstance(m, dict):
            continue
        status = m.get("status")
        statuses[status] = statuses.get(status, 0) + 1
        channel_id = m.get("channel_id")
        if channel_id:
            in_voice += 1
        parsed_members.append({
            "positionInResponse": idx,
            "displayName": m.get("username"),
            "status": status,
            "isInVoice": bool(channel_id),
            "voiceChannelId": channel_id,
            "isDeafened": m.get("deaf") or m.get("self_deaf"),
            "isMuted": m.get("mute") or m.get("self_mute"),
            "activityName": (m.get("game") or {}).get("name"),
            "avatarUrl": m.get("avatar_url"),
        })
    return {
        "guildId": guild_id,
        "name": payload.get("name"),
        "onlineCount": payload.get("presence_count"),
        # Discord caps the member array at 100 no matter how many are online,
        # so this is a sample and the flag says when it is one.
        "membersReturned": len(parsed_members),
        "memberListTruncated": len(parsed_members) >= 100,
        "membersInVoice": in_voice,
        "statusBreakdown": statuses,
        "instantInvite": payload.get("instant_invite"),
        "voiceChannels": [
            {"id": c.get("id"), "name": c.get("name"), "position": c.get("position")}
            for c in (payload.get("channels") or []) if isinstance(c, dict)
        ],
        "createdAt": snowflake_created_at(guild_id),
        "members": parsed_members,
    }


# -- games -----------------------------------------------------------------

def parse_trending_game(game: dict[str, Any], week_date: str | None) -> dict[str, Any]:
    guild = game.get("official_guild") or {}
    members = guild.get("approximate_member_count")
    online = guild.get("approximate_online_count")
    app_id = str(game.get("application_id") or "")
    return {
        "rank": game.get("rank"),
        "weekDate": week_date,
        "applicationId": app_id,
        "gameName": game.get("game_name") or game.get("name"),
        "description": game.get("description"),
        "gameUrl": f"{SITE_ROOT}/game/{game['profile_slug']}" if game.get("profile_slug") else None,
        "releaseDate": game.get("release_date"),
        # Week-on-week movement, which is the whole point of the chart.
        "totalPlayersPctChange": game.get("total_players_pct_change"),
        "streamingActivity7dDeltaPct": game.get("streaming_activity_7d_delta_pct"),
        "weekTrendingStreak": game.get("week_trending_streak"),
        "searchResultCount": game.get("search_result_count"),
        "categories": [
            {"name": c.get("name"), "slug": c.get("slug"), "rank": c.get("rank")}
            for c in (game.get("categories") or []) if isinstance(c, dict)
        ],
        "coverImageUrl": game.get("cover_image_url"),
        "screenshotUrl": game.get("screenshot_url"),
        "officialGuildId": str(guild.get("id")) if guild.get("id") else None,
        "officialGuildName": guild.get("name"),
        "officialGuildMemberCount": members,
        "officialGuildOnlineCount": online,
        "officialGuildEngagementRatePct": _engagement(members, online),
        "officialGuildInviteUrl": guild.get("invite_link_url"),
        "officialGuildDiscoveryUrl": (
            f"{SITE_ROOT}/servers/{guild['server_web_page_slug']}"
            if guild.get("server_web_page_slug") else None
        ),
        "officialGuildIsVerified": guild.get("is_verified"),
        "officialGuildIsPartnered": guild.get("is_partnered"),
    }


def parse_game_profile(data: dict[str, Any]) -> dict[str, Any]:
    guild = data.get("official_guild") or {}
    media = data.get("media") or {}
    members = guild.get("approximate_member_count")
    online = guild.get("approximate_online_count")
    app_id = str(data.get("application_id") or "")
    return {
        "applicationId": app_id,
        "gameName": data.get("name"),
        "summary": data.get("summary"),
        "genres": data.get("genres") or [],
        "platforms": data.get("platforms") or [],
        "publishers": data.get("publishers") or [],
        "developers": data.get("developers") or [],
        "releaseDate": data.get("release_date"),
        # Discord's own last-30-days popularity rank for the title.
        "last30DayRank": data.get("l30_rank"),
        "links": [
            {"label": l.get("label"), "url": l.get("url")}
            for l in (data.get("links") or []) if isinstance(l, dict)
        ],
        "coverImageUrl": media.get("cover_image_url"),
        "bannerImageUrl": media.get("banner_image_url"),
        "screenshotUrls": media.get("screenshot_urls") or [],
        "trailers": data.get("trailers") or [],
        "trending": data.get("trending"),
        "officialGuildId": str(guild.get("id")) if guild.get("id") else None,
        "officialGuildName": guild.get("name"),
        "officialGuildMemberCount": members,
        "officialGuildOnlineCount": online,
        "officialGuildEngagementRatePct": _engagement(members, online),
        "officialGuildInviteUrl": guild.get("invite_link_url"),
    }


# -- applications ----------------------------------------------------------

def parse_bot_profile(payload: dict[str, Any]) -> dict[str, Any]:
    app_id = str(payload.get("id") or "")
    install = payload.get("install_params") or {}
    return {
        "applicationId": app_id,
        "name": payload.get("name"),
        "description": payload.get("description"),
        "tags": payload.get("tags") or [],
        "isVerified": payload.get("is_verified"),
        "isDiscoverable": payload.get("is_discoverable"),
        "isMonetized": payload.get("is_monetized"),
        "isBotPublic": payload.get("bot_public"),
        "botRequiresCodeGrant": payload.get("bot_require_code_grant"),
        "guildId": str(payload["guild_id"]) if payload.get("guild_id") else None,
        "iconUrl": _asset_url("app-icons", app_id, payload.get("icon")),
        "termsOfServiceUrl": payload.get("terms_of_service_url"),
        "privacyPolicyUrl": payload.get("privacy_policy_url"),
        "installScopes": install.get("scopes") or [],
        "installPermissions": install.get("permissions"),
        "inviteUrl": (
            f"{SITE_ROOT}/oauth2/authorize?client_id={app_id}"
            f"&scope={'+'.join(install.get('scopes') or ['bot'])}"
            f"&permissions={install.get('permissions') or '0'}"
        ) if app_id else None,
        "createdAt": snowflake_created_at(app_id),
        "storefrontAvailable": payload.get("storefront_available"),
    }
