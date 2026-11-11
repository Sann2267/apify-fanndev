# Steam Concurrent Players Monitor

Track how many people are playing games on Steam: right now, today, and over the years. Steam's own live charts, a live count for any game, monthly and hourly history, a long-tail ranking of ~12,700 games, and the total number of Steam users online. All from one actor.

Schedule it (for example every hour) and every record also tells you **how much the player count changed since the previous run**, with an optional alert flag for big swings.

## What you can collect

| Mode | What you get | Requests |
|---|---|---|
| **Live top 100 by current players** (`topConcurrent`) | Steam's live "Most Played" chart: players in-game now, today's peak, name, developer, release date | 1 |
| **Top 100 by daily peak** (`topDailyPeak`) | Yesterday's peak per game, plus its rank a week earlier | 1 |
| **Live player count for my games** (`appsCurrent`) | Live players for any game you list, optionally plus 24h peak, all-time peak and 30-day average | 1 per game |
| **Player history for my games** (`appHistory`) | Monthly average / gain / peak since launch, plus daily and hourly points | 2 per game |
| **Long-tail ranking** (`steamchartsTop`) | Up to ~12,700 games ranked by current players, with 30-day peak and hours played | 1 per 25 games |
| **Total Steam users online** (`steamOnline`) | Users logged in to Steam now, 48h peak and low, 5-minute series | 1 |

Games can be given as an appid (`730`), a Steam store / SteamCharts / SteamDB link, or just a name (`Elden Ring`).

## Example input

```json
{
    "mode": "appsCurrent",
    "apps": ["730", "https://store.steampowered.com/app/570/Dota_2/", "Elden Ring"],
    "includeSteamchartsStats": true,
    "compareWithPrevious": true,
    "alertChangePct": 20
}
```

## Example output

`topConcurrent` (real record, 2026-10-10):

```json
{
    "_input": "topConcurrent",
    "_source": "S1-steam-api-concurrent",
    "_scrapedAt": "2026-10-10T21:22:25Z",
    "recordType": "TOP_CONCURRENT",
    "rank": 1,
    "appid": 730,
    "concurrent_in_game": 1047853,
    "peak_in_game": 1404142,
    "name": "Counter-Strike 2",
    "storeUrl": "https://store.steampowered.com/app/730/CounterStrike_2",
    "isFree": true,
    "developers": ["Valve"],
    "publishers": ["Valve"],
    "releaseDate": "2012-08-21T17:00:00Z",
    "lastUpdate": "2026-10-10T21:18:11Z",
    "item": { "...": "raw Steam store item" },
    "previousPlayers": 1047853,
    "playersChange": 0,
    "playersChangePct": 0.0,
    "previousRank": 1,
    "rankChange": 0,
    "previousSnapshotAt": "2026-10-10T21:23:28Z",
    "isNewEntry": false,
    "sameUpstreamSnapshot": true
}
```

`appsCurrent` with SteamCharts stats:

```json
{
    "_input": "Elden Ring",
    "_source": "S1-steam-api-current",
    "recordType": "APP_CURRENT",
    "appid": 1245620,
    "player_count": 29280,
    "name": "ELDEN RING",
    "developers": ["FromSoftware, Inc."],
    "publishers": ["FromSoftware, Inc.", "Bandai Namco Entertainment"],
    "releaseDate": "2022-02-24T23:07:58Z",
    "checkedAt": "2026-10-10T21:23:23Z",
    "peak24h": 39449,
    "allTimePeak": 952523,
    "avgPlayersLast30Days": 28190.48
}
```

`appHistory` (series and months truncated):

```json
{
    "_input": "730",
    "_source": "S1-steamcharts-app",
    "recordType": "APP_HISTORY",
    "appid": 730,
    "name": "Counter-Strike 2",
    "currentPlayers": 1122810,
    "currentPlayersAt": "2026-10-10T20:01:55Z",
    "peak24h": 1402441,
    "allTimePeak": 1818368,
    "months": [
        {"month": "Last 30 Days", "avgPlayers": 810166.22, "gain": 4528.4, "gainPct": 0.56, "peakPlayers": 1450705},
        {"month": "September 2026", "avgPlayers": 805637.82, "gain": -19619.98, "gainPct": -2.38, "peakPlayers": 1450705},
        "... 170 more"
    ],
    "series": [
        {"timestamp": "2012-07-01T00:00:00Z", "players": 1642, "resolution": "monthly"},
        "... 948 more"
    ],
    "seriesPoints": 949
}
```

`steamOnline`:

```json
{
    "recordType": "STEAM_ONLINE",
    "label": "Steam users logged in",
    "usersOnline": 32606690,
    "usersOnlineAt": "2026-10-10T21:13:25Z",
    "peak48h": 42789427,
    "peak48hAt": "2026-10-10T14:42:46Z",
    "low48h": 25153899,
    "low48hAt": "2026-10-08T23:38:51Z",
    "seriesPoints": 604
}
```

Inputs that cannot be processed still produce a row with `recordType: "ERROR"` and a reason (`not_found`, `not_tracked`, `invalid_input`, ...), so you can always see which games failed and why.

## Monitoring (change detection)

With **Compare with previous run** on (the default), the actor remembers each game's number per mode in the named key-value store `steam-players-monitor-snapshots` and adds:

- `previousPlayers`, `playersChange`, `playersChangePct`: movement since the last run
- `previousRank`, `rankChange`: positive means the game climbed
- `isNewEntry`: the game wasn't in the previous snapshot (new on the chart)
- `sameUpstreamSnapshot`: Steam hadn't refreshed its data since your last run, so a 0 change means "no new data", not "no movement"
- `alert`: the change is at least **Alert threshold (%)**

Steam refreshes the live chart every few minutes and the daily-peak chart once a day; SteamCharts refreshes about hourly. Scheduling more often than that only repeats the same numbers.

## Good to know

- **Two sources, slightly different numbers.** Live counts (`topConcurrent`, `appsCurrent`) come straight from Steam's official API. History, 24h/all-time peaks and the long-tail ranking come from SteamCharts, which reads Steam about once an hour, so its "current" figure can be up to an hour old.
- **SteamCharts does not track every game.** Some new releases are missing (e.g. AION 2, #3 on Steam at test time). `appHistory` returns `not_tracked` for them; `appsCurrent` still returns the live count.
- **History resolution** (as of October 2026): monthly from launch until mid-2026, then daily, then hourly for the last ~30 days.
- **Official charts stop at 100 games.** Use `steamchartsTop` for anything below the top 100.
- **No login, no proxy needed.** None of the endpoints used is blocked or rate-limited at normal volumes. The proxy setting is there only for very large, very frequent jobs.

## Technical notes

- **WAF:** none on any surface (api.steampowered.com, store.steampowered.com, steamcharts.com), tested 2026-10-11. Even a bare Python client gets HTTP 200; 100 parallel API calls drew no 429s. `curl_cffi` with the `chrome124` TLS profile is used as insurance, rotating to safari17_0 / firefox133 / edge101 and a new exit IP if a gate ever appears.
- **Endpoints:** `ISteamChartsService/GetGamesByConcurrentPlayers` and `GetMostPlayedGames` (with `input_json.data_request`, so names come in the same call), `ISteamUserStats/GetNumberOfCurrentPlayers`, `IStoreBrowseService/GetItems` (batches of 100), `store/api/storesearch` for name lookup, `store/stats/userdata.json`, `steamcharts.com/app/{id}`, `/app/{id}/chart-data.json` and `/top/p.{n}`.
- **Quirk:** `GetMostPlayedGames` accepts `top_played_period` but ignores it (every value returns the same daily ranking), so it isn't exposed.
- SteamDB is intentionally not used: its terms prohibit automated access.
