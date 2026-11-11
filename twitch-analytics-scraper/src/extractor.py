"""Query builders + parsing logic -- turns GraphQL responses into
dataset-ready records.

All queries use GraphQL variables (not string interpolation) for
user-supplied values -- safe against injection.
"""

from datetime import datetime, timezone


class UnexpectedShape(Exception):
    """Upstream GraphQL response shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


TOP_GAMES_QUERY = """
query($first: Int!) {
  games(first: $first, options: {sort: VIEWER_COUNT}) {
    edges {
      node {
        id
        name
        displayName
        viewersCount
        broadcastersCount
        channelsCount
        boxArtURL
      }
    }
  }
}
"""

TOP_STREAMS_QUERY = """
query($first: Int!) {
  streams(first: $first, options: {sort: VIEWER_COUNT}) {
    edges {
      node {
        id
        title
        type
        viewersCount
        createdAt
        broadcaster {
          id
          login
          displayName
        }
        game {
          id
          name
        }
      }
    }
  }
}
"""

GAME_STREAMS_QUERY = """
query($name: String!, $first: Int!) {
  game(name: $name) {
    id
    name
    displayName
    viewersCount
    broadcastersCount
    streams(first: $first, options: {sort: VIEWER_COUNT}) {
      edges {
        node {
          id
          title
          type
          viewersCount
          createdAt
          broadcaster {
            id
            login
            displayName
          }
        }
      }
    }
  }
}
"""

CHANNEL_LIVE_QUERY = """
query($login: String!) {
  user(login: $login) {
    id
    login
    displayName
    stream {
      id
      viewersCount
      createdAt
      game {
        id
        name
      }
    }
  }
}
"""


def extract_top_games(data: dict, requested_first: int) -> list[dict]:
    games = data.get("games")
    if games is None:
        raise UnexpectedShape("games is null -- shape has likely changed.")
    edges = games.get("edges")
    if edges is None:
        raise UnexpectedShape("games.edges missing -- shape has likely changed.")

    scraped_at = utc_now_iso()
    truncated = len(edges) >= requested_first
    results = []
    for rank, edge in enumerate(edges, start=1):
        node = edge.get("node") or {}
        results.append(
            {
                "_input": "top-games",
                "_source": "S1-gql",
                "_scrapedAt": scraped_at,
                "rankApprox": rank,
                "_approxSort": True,
                "gameId": node.get("id"),
                "name": node.get("name"),
                "displayName": node.get("displayName"),
                "viewersCount": node.get("viewersCount"),
                "broadcastersCount": node.get("broadcastersCount"),
                "channelsCount": node.get("channelsCount"),
                "boxArtURL": node.get("boxArtURL"),
                "_truncatedToFirstPage": truncated,
            }
        )
    return results


def _stream_node_to_record(node: dict, rank: int, input_value: str, scraped_at: str, extra: dict | None = None) -> dict:
    broadcaster = node.get("broadcaster") or {}
    game = node.get("game") or {}
    record = {
        "_input": input_value,
        "_source": "S1-gql",
        "_scrapedAt": scraped_at,
        "rankApprox": rank,
        "_approxSort": True,
        "streamId": node.get("id"),
        "title": node.get("title"),
        "type": node.get("type"),
        "viewersCount": node.get("viewersCount"),
        "createdAt": node.get("createdAt"),
        "broadcasterId": broadcaster.get("id"),
        "broadcasterLogin": broadcaster.get("login"),
        "broadcasterDisplayName": broadcaster.get("displayName"),
    }
    if game:
        record["gameName"] = game.get("name")
    if extra:
        record.update(extra)
    return record


def extract_top_streams(data: dict, requested_first: int) -> list[dict]:
    streams = data.get("streams")
    if streams is None:
        raise UnexpectedShape("streams is null -- shape has likely changed.")
    edges = streams.get("edges")
    if edges is None:
        raise UnexpectedShape("streams.edges missing -- shape has likely changed.")

    scraped_at = utc_now_iso()
    truncated = len(edges) >= requested_first
    return [
        _stream_node_to_record(
            edge.get("node") or {}, rank, "top-streams", scraped_at, {"_truncatedToFirstPage": truncated}
        )
        for rank, edge in enumerate(edges, start=1)
    ]


def extract_game_streams(data: dict, game_name: str, requested_first: int) -> list[dict]:
    game = data.get("game")
    if game is None:
        return [
            {
                "_input": game_name,
                "_source": "none",
                "_scrapedAt": utc_now_iso(),
                "_error": "game_not_found",
                "_errorDetail": "",
            }
        ]

    streams = game.get("streams")
    if streams is None:
        raise UnexpectedShape("game.streams is null for an existing game -- shape has likely changed.")
    edges = streams.get("edges")
    if edges is None:
        raise UnexpectedShape("game.streams.edges missing -- shape has likely changed.")

    scraped_at = utc_now_iso()
    truncated = len(edges) >= requested_first
    extra = {
        "gameId": game.get("id"),
        "gameName": game.get("name"),
        "gameDisplayName": game.get("displayName"),
        "gameTotalViewersCount": game.get("viewersCount"),
        "gameBroadcastersCount": game.get("broadcastersCount"),
        "_truncatedToFirstPage": truncated,
    }
    return [
        _stream_node_to_record(edge.get("node") or {}, rank, game_name, scraped_at, extra)
        for rank, edge in enumerate(edges, start=1)
    ]


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
