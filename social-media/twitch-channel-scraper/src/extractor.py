"""Query builders + parsing logic -- turns GraphQL responses into
dataset-ready records.

All queries use GraphQL variables (not string interpolation) for the
`login` argument -- safe against injection from arbitrary user input, and
the standard way to parameterize a GraphQL POST body.

Field-shape notes (see CRAWLING_METHOD.md for the full recon log of every
field name that was tried and rejected before landing on these):
  - `ScheduleSegment` does NOT have `startTime`/`endTime`/`isRecurring`/
    `category` (all guessable, all wrong) -- it has `startAt`/`endAt`/
    `isCancelled` (British spelling)/`categories` (plural, a list).
  - `Schedule` does NOT have a `vacation` field at the root (also
    guessable, also wrong).
  - `Tag` requires a subfield selection (`{ id localizedName }`) --
    Twitch's GraphQL validator errors if you request it as a bare scalar.
"""

import json
from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream GraphQL response shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


CHANNEL_QUERY = """
query($login: String!) {
  user(login: $login) {
    id
    login
    displayName
    description
    createdAt
    profileImageURL(width: 300)
    bannerImageURL
    primaryColorHex
    followers {
      totalCount
    }
    stream {
      id
      title
      type
      viewersCount
      createdAt
      game {
        id
        name
        boxArtURL
      }
      tags {
        id
        localizedName
      }
    }
    lastBroadcast {
      startedAt
      title
    }
  }
}
"""

VIDEOS_QUERY = """
query($login: String!, $first: Int!, $sort: VideoSort!, $type: BroadcastType) {
  user(login: $login) {
    videos(first: $first, sort: $sort, type: $type) {
      totalCount
      pageInfo {
        hasNextPage
      }
      edges {
        node {
          id
          title
          publishedAt
          viewCount
          lengthSeconds
          previewThumbnailURL
          game {
            name
          }
        }
      }
    }
  }
}
"""

CLIPS_QUERY = """
query($login: String!, $first: Int!, $period: ClipsPeriod!, $sort: ClipsSort!) {
  user(login: $login) {
    clips(first: $first, criteria: { period: $period, sort: $sort }) {
      edges {
        node {
          id
          slug
          title
          viewCount
          createdAt
          durationSeconds
          url
          thumbnailURL
          curator {
            login
          }
        }
      }
    }
  }
}
"""

SCHEDULE_QUERY = """
query($login: String!) {
  user(login: $login) {
    channel {
      schedule {
        segments {
          id
          title
          startAt
          endAt
          isCancelled
          hasReminder
          categories {
            id
            name
          }
        }
        nextSegment {
          id
        }
      }
    }
  }
}
"""


def extract_channel(data: dict, login: str) -> dict:
    user = data.get("user")
    if user is None:
        return extract_error(login, "channel_not_found")

    stream = user.get("stream")
    game = (stream or {}).get("game") or {}
    tags = (stream or {}).get("tags") or []
    last_broadcast = user.get("lastBroadcast") or {}
    followers = user.get("followers") or {}

    return {
        "_input": login,
        "_source": "S1-gql",
        "_scrapedAt": utc_now_iso(),
        "id": user.get("id"),
        "login": user.get("login"),
        "displayName": user.get("displayName"),
        "description": user.get("description"),
        "createdAt": user.get("createdAt"),
        "profileImageURL": user.get("profileImageURL"),
        "bannerImageURL": user.get("bannerImageURL"),
        "primaryColorHex": user.get("primaryColorHex"),
        "followersCount": followers.get("totalCount"),
        "isLive": stream is not None,
        "streamId": (stream or {}).get("id"),
        "streamTitle": (stream or {}).get("title"),
        "streamType": (stream or {}).get("type"),
        "viewersCount": (stream or {}).get("viewersCount"),
        "streamStartedAt": (stream or {}).get("createdAt"),
        "gameName": game.get("name"),
        "gameBoxArtURL": game.get("boxArtURL"),
        "tags": [t.get("localizedName") for t in tags if t.get("localizedName")] or None,
        "lastBroadcastStartedAt": last_broadcast.get("startedAt"),
        "lastBroadcastTitle": last_broadcast.get("title"),
    }


def extract_videos(data: dict, login: str, requested_first: int) -> list[dict]:
    user = data.get("user")
    if user is None:
        return [extract_error(login, "channel_not_found")]

    videos = user.get("videos")
    if videos is None:
        raise UnexpectedShape("user.videos is null for an existing user -- shape has likely changed.")

    edges = videos.get("edges")
    if edges is None:
        raise UnexpectedShape("user.videos.edges missing -- shape has likely changed.")

    total_count = videos.get("totalCount")
    has_next_page = (videos.get("pageInfo") or {}).get("hasNextPage")
    # Deep (`after`-cursor) pagination is blocked by Twitch's integrity
    # gate for HTTP-only clients (see CRAWLING_METHOD.md) -- this actor
    # returns only the first page. Flag every row so downstream consumers
    # know more exist, instead of silently looking like a complete list.
    truncated = bool(has_next_page) or (total_count is not None and total_count > requested_first)

    scraped_at = utc_now_iso()
    results = []
    for edge in edges:
        node = edge.get("node") or {}
        game = node.get("game") or {}
        video_id = node.get("id")
        results.append(
            {
                "_input": login,
                "_source": "S1-gql",
                "_scrapedAt": scraped_at,
                "channelLogin": login,
                "channelTotalVideoCount": total_count,
                "_truncatedToFirstPage": truncated,
                "videoId": video_id,
                "title": node.get("title"),
                "publishedAt": node.get("publishedAt"),
                "viewCount": node.get("viewCount"),
                "lengthSeconds": node.get("lengthSeconds"),
                "previewThumbnailURL": node.get("previewThumbnailURL"),
                "gameName": game.get("name"),
                "url": f"https://www.twitch.tv/videos/{video_id}" if video_id else None,
            }
        )
    return results


def extract_clips(data: dict, login: str, requested_first: int) -> list[dict]:
    user = data.get("user")
    if user is None:
        return [extract_error(login, "channel_not_found")]

    clips = user.get("clips")
    if clips is None:
        raise UnexpectedShape("user.clips is null for an existing user -- shape has likely changed.")

    edges = clips.get("edges")
    if edges is None:
        raise UnexpectedShape("user.clips.edges missing -- shape has likely changed.")

    # `clips` has no `totalCount`/`pageInfo.hasNextPage` field (confirmed
    # during recon) -- a full page (== requested_first, capped at
    # MAX_FIRST) is the only truncation signal available.
    truncated = len(edges) >= requested_first

    scraped_at = utc_now_iso()
    results = []
    for edge in edges:
        node = edge.get("node") or {}
        curator = node.get("curator") or {}
        results.append(
            {
                "_input": login,
                "_source": "S1-gql",
                "_scrapedAt": scraped_at,
                "channelLogin": login,
                "_truncatedToFirstPage": truncated,
                "clipId": node.get("id"),
                "slug": node.get("slug"),
                "title": node.get("title"),
                "viewCount": node.get("viewCount"),
                "createdAt": node.get("createdAt"),
                "durationSeconds": node.get("durationSeconds"),
                "url": node.get("url"),
                "thumbnailURL": node.get("thumbnailURL"),
                "curatorLogin": curator.get("login"),
            }
        )
    return results


def extract_schedule(data: dict, login: str) -> list[dict]:
    user = data.get("user")
    if user is None:
        return [extract_error(login, "channel_not_found")]

    channel = user.get("channel") or {}
    schedule = channel.get("schedule")
    if schedule is None:
        # A channel with no upcoming schedule configured returns
        # `schedule: null` -- this is a legitimate empty state, not a
        # shape change (confirmed on multiple sampled channels).
        return []

    segments = schedule.get("segments")
    if segments is None:
        raise UnexpectedShape("user.channel.schedule.segments missing -- shape has likely changed.")

    next_segment_id = (schedule.get("nextSegment") or {}).get("id")
    scraped_at = utc_now_iso()
    results = []
    for seg in segments:
        categories = seg.get("categories") or []
        results.append(
            {
                "_input": login,
                "_source": "S1-gql",
                "_scrapedAt": scraped_at,
                "channelLogin": login,
                "segmentId": seg.get("id"),
                "title": seg.get("title") or None,
                "startAt": seg.get("startAt"),
                "endAt": seg.get("endAt"),
                "isCancelled": seg.get("isCancelled"),
                "hasReminder": seg.get("hasReminder"),
                "categories": [c.get("name") for c in categories if c.get("name")] or None,
                "isNextSegment": seg.get("id") == next_segment_id if next_segment_id else False,
            }
        )
    return results


def extract_error(login: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": login,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
