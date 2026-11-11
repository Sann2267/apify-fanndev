"""Endpoints, headers and the pinned GraphQL persisted-query hashes.

The hashes below were harvested from web-player.53e49eea.js on 2026-09-20 and
are only a starting point: Spotify rotates them on every web player deploy. The
client re-harvests the whole set from the live bundle the first time Spotify
answers ``PersistedQueryNotFound``, so a stale entry here costs one extra
request rather than a broken run. Keeping them pinned means the common case --
Spotify has not deployed -- never pays for a multi-megabyte bundle download.
"""

from __future__ import annotations

import re

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Any embed page works; this one is a stable, never-region-locked track.
EMBED_TOKEN_URL = "https://open.spotify.com/embed/track/4cOdK2wGLETKBW3PvgPWqT"
WEB_PLAYER_URL = "https://open.spotify.com/"
PARTNER_URL = "https://api-partner.spotify.com/pathfinder/v1/query"
WEB_API_URL = "https://api.spotify.com/v1"

BUNDLE_PATTERN = re.compile(
    r"https://open(?:-exp)?\.spotifycdn\.com/cdn/build/web-player/web-player\.[0-9a-f]+\.js"
)

# curl_cffi impersonation profile. Spotify has no TLS-fingerprint gate on any of
# these hosts -- plain requests works too -- but impersonating a real browser
# keeps the actor indistinguishable from the web player it is mimicking.
TLS_PROFILE = "chrome131"

MAX_RETRIES = 4
RETRY_DELAY_BASE = 1.5
REQUEST_DELAY = 0.35

PERSISTED_QUERIES: dict[str, str] = {
    "queryArtistOverview": "9f8134ef565e78621f1e1793555bd6633c5ac144ae0f89604ed3ae3f80b3c8e6",
    "fetchPlaylist": "86dde7b9d9356e2369414647cf6950cfed96e778e129cfdfc99aea6c1613b3b0",
    "fetchPlaylistContents": "86dde7b9d9356e2369414647cf6950cfed96e778e129cfdfc99aea6c1613b3b0",
    "fetchPlaylistMetadata": "86dde7b9d9356e2369414647cf6950cfed96e778e129cfdfc99aea6c1613b3b0",
    "getTrack": "a8ef9e9f02b836feb0da3003c31dbb30decc6f4b473ef89ca88c882386d668de",
    "getAlbum": "6a74b456cd1735c9193d9e8ec8cc5184cad7ce13572210315229db3975964361",
    "queryAlbumTracks": "6a74b456cd1735c9193d9e8ec8cc5184cad7ce13572210315229db3975964361",
    "queryShowMetadataV2": "40202837452991ffa80ced96987bc1a937e21d5a89df5bf1fb743110e4d6e93a",
    "queryPodcastEpisodes": "06046f9b939d56c8eb7cdbb687da938de1164c006871aec91dc26e4dc7d8eb08",
    "getEpisodeOrChapter": "3416929067571ac4b79db16716be3c6ea5f6265f7975a0ee94b1fc5ee1dc1e9d",
    "queryTrackArtists": "ee2b038198f5e62c679c3996584d9249bbee55fe69fc212271c56492a022c798",
    "similarAlbumsBasedOnThisTrack": "1d1f93a737498adca2c892c73af87fc0b052afe4e1a33c989540c32413dfae17",
    # Free-text search. This is what the web player's search box calls, and it is
    # the reason these actors do not depend on api.spotify.com/v1/search: that
    # endpoint answers an anonymous token for only a few dozen requests before
    # banning the *IP* for roughly 20 hours (Retry-After: 73444), while
    # pathfinder search has shown no such ceiling.
    "searchSuggestions": "b50ebd72524415b132ddaca04158fd7aca529da28be322c9924643c0633df5bd",
    "assistedCurationSearch": "f78953bf9207d73493c27284103f5aeb6e728876d5793851bf79bc706127ff70",
}

# searchSuggestions ignores limit, offset and every other paging variable: it
# always answers with exactly this many mixed-type hits. Asking for more is not
# an error, it simply changes nothing, so callers must not paginate it.
SEARCH_SUGGESTIONS_CAP = 30

# The unauthenticated charts service. No token, no headers, no account -- but
# only this one path exists publicly, and it serves the three global weekly
# charts. Per-country and historical charts live behind /auth/v0/, which needs
# a logged-in session, so regional charts come from the editorial playlists.
CHARTS_PUBLIC_URL = "https://charts-spotify-com-service.spotify.com/public/v0/charts"
