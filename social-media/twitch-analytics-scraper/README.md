# Twitch Streamer & Channel Analytics

Trending games/categories, platform-wide top live streams, top channels within a category, and per-channel trending-rank lookup — no account or API key needed.

## Why use this actor

- Market-level Twitch intelligence: what's trending right now, who's dominating a category, and where a specific streamer ranks
- Complements a single-channel profile lookup with genuinely different, cross-channel data
- No account, login, or API key required
- Automatic retries on temporary network hiccups
- Transparent about ranking accuracy — every ranked field is clearly labeled "approximate" because Twitch's own sort isn't perfectly ordered (see Known limits) — nothing is dressed up as more precise than it is

## How it works

Pick a `mode`:
1. **`top-games`** — trending games/categories by current viewer count, with how many channels are streaming each.
2. **`top-streams`** — the platform-wide top live streams right now.
3. **`game-streams`** — the top live channels within one specific game/category.
4. **`channel-rank`** — checks whether specific channel(s) are currently live and trending, reporting their approximate position in the platform-wide top 30 and in their category's top 30.

## Input

**Top games:**
```json
{ "mode": "top-games", "limit": 20 }
```

**Top live streams:**
```json
{ "mode": "top-streams", "limit": 30 }
```

**Top streams in a game:**
```json
{ "mode": "game-streams", "gameName": "Just Chatting", "limit": 30 }
```

**Channel trending rank:**
```json
{ "mode": "channel-rank", "logins": ["xqc", "shroud"] }
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"top-games"` (default), `"top-streams"`, `"game-streams"`, or `"channel-rank"`. |
| `limit` | integer | Max results for `top-games`/`top-streams`/`game-streams`. Twitch caps this at 30 for streams, 100 for games (see Known limits). |
| `gameName` / `gameNames` | string / array | `game-streams` mode — exact game/category name(s) as shown on Twitch. |
| `login` / `logins` | string / array | `channel-rank` mode — channel login(s) to check. |
| `maxConcurrency` | integer | `game-streams`/`channel-rank` mode — how many items to process in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Top games mode** — one record per game:
```json
{
  "_input": "top-games",
  "_source": "S1-gql",
  "_scrapedAt": "2026-08-25T20:07:18Z",
  "rankApprox": 4,
  "_approxSort": true,
  "gameId": "30921",
  "name": "Rocket League",
  "viewersCount": 126135,
  "broadcastersCount": 1174,
  "boxArtURL": "https://static-cdn.jtvnw.net/ttv-boxart/30921-{width}x{height}.jpg"
}
```

**Top streams / game streams mode** — one record per live stream:
```json
{
  "_input": "Just Chatting",
  "_source": "S1-gql",
  "_scrapedAt": "2026-08-25T20:07:39Z",
  "rankApprox": 5,
  "_approxSort": true,
  "streamId": "317579103844",
  "title": "EN MODE MARDI PRIME",
  "viewersCount": 18547,
  "createdAt": "2026-08-25T19:43:29Z",
  "broadcasterLogin": "anyme023",
  "broadcasterDisplayName": "Anyme023",
  "gameName": "Just Chatting"
}
```

**Channel rank mode:**
```json
{
  "_input": "xqc",
  "_source": "S1-gql",
  "_scrapedAt": "2026-08-25T20:07:44Z",
  "login": "xqc",
  "displayName": "xQc",
  "isLive": true,
  "viewersCount": 30580,
  "gameName": "Special Events",
  "globalRankApprox": 7,
  "globalRankNote": "position 7 within the platform-wide top 30 live streams",
  "categoryRankApprox": 3,
  "categoryRankNote": "position 3 within the top 30 live streams in 'Special Events'"
}
```

An offline channel returns `isLive: false` with a `note` explaining that ranking only applies while live. A record with `_error` instead means that item couldn't be processed (`"_error": "channel_not_found"` or `"_error": "game_not_found"`).

## Known limits

- **Ranks are approximate, not guaranteed-exact.** Twitch's own `VIEWER_COUNT` sort was confirmed live to NOT be strictly monotonic — a fetched "sorted" page can have a low-viewer stream sandwiched between two much higher ones. Every ranked field is prefixed `*Approx` and stamped with `_approxSort: true` for exactly this reason. Treat rank as "roughly where this sits," not a precise leaderboard position.
- **Only the top 30 (streams) or top 100 (games) are visible at all.** Twitch blocks deeper pagination for HTTP-only clients (a device-integrity check that can't be satisfied without a real browser). A channel outside the top 30 in both its category and platform-wide returns `null` for both rank fields — that doesn't mean they have zero viewers, just that they're outside the visible window.
- **No chat activity, follower-history/growth trends, or revenue estimates.** These aren't available from any public, unauthenticated Twitch endpoint (the old anonymous chatters endpoint is confirmed dead) — this actor won't fabricate numbers third-party sites compute from their own private historical archives.
