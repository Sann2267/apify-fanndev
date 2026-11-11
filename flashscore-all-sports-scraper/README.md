# Flashscore Scraper - Live Scores, Fixtures, Stats & H2H (14 Sports)

Scrape **Flashscore** match data across **14 sports from one Actor**: football, tennis, basketball, ice hockey, American football, baseball, handball, bandy, futsal, volleyball, cricket, darts, snooker and badminton. Pull an entire day of fixtures and results per sport, watch only what is in play right now, or open a single match and get **expected goals (xG), ball possession, shot maps, goals and cards minute by minute, lineups with player ratings, and head-to-head history**.

No account, no API key, no cookies, no browser. The Actor talks to the same public data feed the Flashscore website itself loads, so a run costs a handful of plain HTTP requests instead of a headless browser.

## Why use this actor

- **One Actor, 14 sports.** Most Flashscore scrapers on the Store are split per sport or per data type - one for tennis, another for live scores, another for odds. This one covers every sport that carries data, in every mode, with a single input schema. Ask for `sportIds: [1, 2, 3]` and you get football, tennis and basketball in the same dataset with the same field names.
- **A whole day in one request.** `fixtures` mode returns every match Flashscore publishes for a sport on a given day - roughly **275 football matches and 470 tennis matches** on an ordinary day - already grouped with their tournament and country.
- **Real match analytics, not just the score.** `match` mode returns the statistics panel as structured rows: expected goals (xG), ball possession, total shots, shots on target, big chances, corners, and for tennis aces and double faults. That is the data people actually model with.
- **Past and future, not only today.** `dayOffsets` walks roughly a week back and a week forward, so you can backfill last weekend's results and pull next weekend's fixture list in the same run.
- **Nothing is silently dropped.** Flashscore's feed uses undocumented two-letter keys. This Actor names the ones it has positively identified and ships the untouched upstream record alongside them under `_raw`, so a key that Flashscore adds tomorrow still reaches your dataset.
- **Honest about gaps.** Where a value could not be verified - the fine-grained status code, incident type IDs - it ships raw and is documented as raw instead of being guessed into a pretty label.

## How it works

Flashscore's website is a JavaScript app: its HTML is ~740 KB of shell and bundles and contains **no** match rows. All data is loaded from a separate feed host, `local-global.flashscore.ninja`, which answers plain HTTP GET requests as long as they carry one static header that Flashscore's own bundle sends. There is no login, no cookie warm-up, no challenge and no rate-limit gate on the endpoints this Actor uses.

The feed does not return JSON. It returns Flashscore's own delimited encoding, where records are separated by `~`, fields by `¬`, and keys from values by `÷`:

```
SA÷1¬~ZA÷ARGENTINA: Liga Profesional¬ZEE÷naYhNOaA¬ZY÷Argentina¬~AA÷WSSid6OM¬AD÷1788818400¬AE÷Barracas Central¬AF÷Argentinos Jrs¬AG÷0¬AH÷0¬...
```

The Actor decodes that into records, carries each tournament header forward onto the matches that follow it (the tournament is **not** repeated on the match rows), converts timestamps to ISO 8601, maps the status and winner codes, and adds a public match URL. Full details of how the format was mapped - including which keys appear on more than 90% of rows and which only appear once a match kicks off - are in [`CRAWLING_METHOD.md`](CRAWLING_METHOD.md).

## Input

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `mode` | string | `fixtures` | `fixtures`, `live`, `match` or `reference`. |
| `sportIds` | array | `["1"]` | Sport IDs to scrape (see table below). In `match` mode this only labels the output. |
| `dayOffsets` | array | `["0"]` | `fixtures` mode. `0` today, `-1` yesterday, `1` tomorrow; roughly -7..+7 is served. |
| `matchId` | string | - | `match` mode. One 8-character match ID (e.g. `WSSid6OM`) or a full Flashscore match URL. |
| `matchIds` | array | - | `match` mode. Several IDs or URLs in one run. |
| `includeSummary` | boolean | `true` | `match` mode. Goals, cards and substitutions with minute, player and side. |
| `includeStatistics` | boolean | `true` | `match` mode. Statistics panel including xG and possession for football. |
| `includeLineups` | boolean | `false` | `match` mode. Formation, starting XI, bench, player ratings when published. |
| `includeHeadToHead` | boolean | `false` | `match` mode. Previous meetings plus recent form for both sides. |
| `maxItems` | integer | `200` | Cap for `fixtures`/`live`, split evenly across every sport/day combination. |
| `maxConcurrency` | integer | `4` | How many match IDs to fetch in parallel in `match` mode. |
| `proxyConfiguration` | object | disabled | Optional. Not needed in normal use - see *Notes & limits*. |

### Sport IDs

| ID | Sport | ID | Sport |
| --- | --- | --- | --- |
| 1 | Football | 11 | Futsal |
| 2 | Tennis | 12 | Volleyball |
| 3 | Basketball | 13 | Cricket |
| 4 | Ice Hockey | 14 | Darts |
| 5 | American Football | 15 | Snooker |
| 6 | Baseball | 21 | Badminton |
| 7 | Handball | | |
| 10 | Bandy | | |

Run `reference` mode to see which IDs are carrying matches **today**, measured live rather than read from this table.

### Example inputs

**Every football match today**

```json
{ "mode": "fixtures", "sportIds": ["1"], "dayOffsets": ["0"], "maxItems": 300 }
```

**Weekend backfill across three sports**

```json
{ "mode": "fixtures", "sportIds": ["1", "2", "3"], "dayOffsets": ["-2", "-1", "0"], "maxItems": 900 }
```

**Only what is in play right now**

```json
{ "mode": "live", "sportIds": ["1", "3", "4"], "maxItems": 100 }
```

**Deep dive on specific matches**

```json
{
  "mode": "match",
  "matchIds": ["WSSid6OM", "2myy0lPc"],
  "includeSummary": true,
  "includeStatistics": true,
  "includeLineups": true,
  "includeHeadToHead": true
}
```

**Which sports are live today**

```json
{ "mode": "reference" }
```

## Output

Every record carries the envelope fields `_input`, `_source`, `_scrapedAt`, plus `_error`/`_errorDetail` when something failed. `recordType` tells the three shapes apart: `MATCH`, `MATCH_DETAIL` and `SPORT`.

### `MATCH` (fixtures and live modes)

```json
{
  "_input": "fixtures:sport=1:day=0",
  "_source": "S1-feed",
  "_scrapedAt": "2026-09-08T12:28:04Z",
  "recordType": "MATCH",
  "sportId": 1,
  "sportName": "Football",
  "tournament": "ARGENTINA: Liga Profesional - Clausura",
  "country": "Argentina",
  "tournamentId": "naYhNOaA",
  "tournamentStageId": "lEqmiyVI",
  "matchId": "2myy0lPc",
  "matchUrl": "https://www.flashscore.com/match/2myy0lPc/",
  "homeTeam": "Union de Santa Fe",
  "awayTeam": "Instituto",
  "homeTeamId": "vRMEOMPn",
  "awayTeamId": "vJEG4Uhc",
  "homeScore": "3",
  "awayScore": "2",
  "score": "3-2",
  "status": "FINISHED",
  "statusCode": "3",
  "winner": "HOME",
  "startTime": "2026-09-08T00:15:00Z",
  "finishedAt": "2026-09-08T02:07:31Z",
  "homeTeamImage": "YVxbV1iT-KxCl9RDG.png",
  "_raw": { "AA": "2myy0lPc", "AD": "1788826500", "...": "every upstream key, untouched" }
}
```

### `MATCH_DETAIL` (match mode)

```json
{
  "recordType": "MATCH_DETAIL",
  "matchId": "WSSid6OM",
  "matchUrl": "https://www.flashscore.com/match/WSSid6OM/",
  "meta": { "DA": "3", "DC": "1788818400", "DD": "1788825065" },
  "statistics": [
    { "period": "Match", "statId": "432", "name": "Expected goals (xG)", "home": "0.37", "away": "0.29" },
    { "period": "Match", "statId": "12",  "name": "Ball possession",     "home": "42%",  "away": "58%"  },
    { "period": "Match", "statId": "34",  "name": "Total shots",         "home": "7",    "away": "7"    },
    { "period": "Match", "statId": "13",  "name": "Shots on target",     "home": "1",    "away": "3"    },
    { "period": "Match", "statId": "459", "name": "Big chances",         "home": "1",    "away": "1"    },
    { "period": "Match", "statId": "16",  "name": "Corner kicks",        "home": "3",    "away": "4"    }
  ],
  "incidents": [
    { "stage": "1st Half", "minute": "25'", "player": "Briasco N.", "side": "HOME", "incidentTypeId": "1" },
    { "stage": "1st Half", "minute": "33'", "player": "Prieto S.",  "side": "HOME", "incidentTypeId": "2" }
  ],
  "lineups": [ { "LA": "Formation", "LD": "1-5-3-2", "LRH": "6.9" } ],
  "headToHead": [ { "KB": "Last matches: Barracas Central" } ]
}
```

A finished football match typically yields around **120 statistics rows** (per period and per stat), **10-20 incidents**, and 50+ lineup blocks.

### `SPORT` (reference mode)

```json
{
  "recordType": "SPORT",
  "sportId": 2,
  "sportName": "Tennis",
  "isNamed": true,
  "matchesToday": 470,
  "sampleTournament": "ATP - SINGLES: US Open (USA), hard"
}
```

## What you can build with it

- **Live score feed** for a bot, dashboard or notification service - run `live` mode on a schedule of a few minutes across the sports you care about.
- **Results database** - run `fixtures` daily with `dayOffsets: ["-1"]` and append; every row already carries tournament, country, both team IDs and the final score.
- **Model inputs for football analytics** - xG, possession, shots and big chances per match, joined on `matchId` from your fixtures table.
- **Fixture calendar** - `dayOffsets: ["1","2","3"]` gives you what is coming, with kick-off times already in UTC.
- **Head-to-head previews** - for each upcoming match ID, run `match` mode with `includeHeadToHead` and you have both sides' recent form.
- **Cross-sport coverage monitoring** - `reference` mode gives a daily count of matches per sport, useful to decide where the data is dense enough to build on.

## Notes & limits

- **Scores are absent, not zero, before kick-off.** An unstarted match has no score keys at all. The Actor deliberately does not collapse that into `0-0`; `score` simply is not present.
- **`status` is coarse on purpose.** `SCHEDULED`/`LIVE`/`FINISHED` are mapped from the status key that appears on more than 90% of rows. The finer code (values such as 4, 11, 12, 13, 38, 45 - covering half-time, extra time, postponed and similar states) is not documented upstream and was not exhaustively observed, so it ships untranslated as `statusCode`.
- **Incident type IDs ship raw** for the same reason. Goals and cards are distinguishable in practice, but the full ID map is not published, so this Actor does not pretend to know it.
- **Lineups are not always published.** Lower-division and youth matches often have none; the feed then returns an empty body and the field is omitted rather than faked.
- **The `live` feed also carries the day's other matches.** The Actor filters strictly to in-play rows, so a run during a quiet hour legitimately returns zero records.
- **`match` mode ignores the sport you pass.** The detail feed is keyed on the match ID alone - the same ID returns byte-identical data whatever sport number is sent - so `sportIds` there only labels the output record.
- **Old matches disappear upstream.** Flashscore drops matches from the feed host after a while; a long-gone ID returns `_error: not_found` rather than an empty record.
- **No proxy needed in normal use.** Every recon request succeeded on a direct connection. Proxy support is wired up for regions or IPs that get rate-limited.
- **Standings and odds are not included.** Neither could be located on the feed host with the endpoint names tried during recon; rather than ship a half-working mode, they are left out and documented here as a known gap.

## Per-sport notes

Coverage is not uniform across sports, and it is worth knowing that before you
build on it. Measured on an ordinary weekday:

| Sport | Matches in a day | What the detail feed gives you |
| --- | --- | --- |
| Football (1) | ~275 | The richest set: xG, possession, shots, big chances, corners, goals/cards by minute, lineups with ratings, H2H |
| Tennis (2) | ~470 | Aces, double faults, service and return stats per set; no lineups (individual sport) |
| Basketball (3) | ~25 | Score by quarter, team stats |
| Ice Hockey (4) | ~40 | Period scores, goals and penalties |
| Baseball (6) | ~20 | Innings, hits and errors |
| Handball (7), Volleyball (12) | 10-15 | Set/period scores |
| Cricket (13) | ~10 | Innings scores; formats vary by competition |
| Darts (14), Snooker (15), Badminton (21) | 15-45 | Frame/leg/set progress |
| American Football (5), Bandy (10), Futsal (11) | 1-5 | Thin - fine for scores, too sparse to model on |

Tennis and football are where the volume is. If your use case needs one dense
sport, start there; if it needs breadth, `reference` mode tells you every day
which sports are actually carrying matches.

## Scheduling tips

- **Live tracking:** run `live` mode every 2-5 minutes for the sports you care
  about. One run is one request per sport, so this stays cheap even at a high
  cadence.
- **Daily results archive:** run once after midnight UTC with
  `dayOffsets: ["-1"]` and append to the same dataset. `matchId` is a stable
  primary key for de-duplication.
- **Fixture calendar:** run weekly with `dayOffsets: ["1","2","3","4","5","6","7"]`.
- **Analytics pipeline:** run `fixtures` first, filter to `status: FINISHED`,
  then feed those `matchId` values into a second `match`-mode run with
  `includeStatistics`. That two-step pattern keeps the expensive per-match calls
  to matches you actually want.

## Troubleshooting / FAQ

**I got zero records in `live` mode.**
That is a real answer, not a failure: nothing was in play in those sports at that
moment. Football has quiet windows of several hours depending on the time zone.

**A match has no `score` field.**
It has not kicked off. Scores are absent before the start rather than zero - see
*Notes & limits*.

**`_error: not_found` on a match ID that worked last month.**
Flashscore drops old matches from the feed host. Pull detail close to when the
match is played, or archive it yourself.

**`_error: unauthorized`.**
The static header the feed requires has been rotated upstream. Nothing you can
configure; the Actor needs a one-line update. It raises immediately instead of
retrying, so a run in this state costs almost nothing.

**Lineups came back missing.**
Many lower-division, youth and women's matches never publish one. The Actor omits
the field rather than inventing an empty structure.

**Can I get league tables or betting odds?**
Not in this version - see *Notes & limits*. Both exist on the site, but the feed
IDs for them were not found during recon and shipping a guess would be worse than
shipping nothing.

**Why is the tournament a single string like `ENGLAND: Premier League`?**
That is exactly how Flashscore publishes it. The country is split out separately
into `country` for convenience, and `tournamentId`/`tournamentStageId` give you
stable keys to group by.

**Do I need a proxy?**
No. Every recon request succeeded on a direct connection, with no cookies and no
warm-up. Proxy support is available if your own IP range gets rate-limited.

**What does `_raw` contain?**
The untouched decoded record straight from Flashscore. If they add a key that
this Actor does not name yet, you still receive it.

## Legal & fair use

This Actor reads only data that Flashscore serves publicly to any visitor - no login, no paywall, no personal data. Sports fixtures, scores and statistics are facts, but Flashscore's compilation of them may be protected in some jurisdictions, and their terms of use apply to you as the operator. Use it for analysis, research and internal tooling; check your own legal position before republishing large extracts commercially. Keep run frequency reasonable - the whole point of the feed approach is that a day of matches costs one request, not thousands.
