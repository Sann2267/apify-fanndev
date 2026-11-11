# Sports Betting Odds & Player Props Scraper

Sportsbook lines for NFL, college football, NBA, WNBA, college basketball, MLB,
NHL, 219 soccer competitions, UFC, golf, tennis and F1 — the point spread, the
moneyline and the total from every book the source lists, **plus the things most
odds scrapers leave on the table**: how far each line has moved since the book
opened it, the full player-prop board (about 659 markets on one NFL game), the
season futures board with implied probability per runner, and the source's own
win projection so you can put the model next to the price.

No login, no API key, no browser. Public endpoints only.

---

## What you get

### `odds` — the line, per book, with its movement

One row per fixture per sportsbook.

| Field | Example |
| --- | --- |
| `eventName` | `Detroit Lions at Buffalo Bills` |
| `providerName` | `Draft Kings` |
| `details` / `spread` / `overUnder` | `BUF -5.5` / `-5.5` / `54.5` |
| `homeMoneyline` / `awayMoneyline` | `-245` / `+200` |
| `homeImpliedProbability` / `awayImpliedProbability` | `0.7101` / `0.3333` |
| `openSpread` → `currentSpread` (`spreadMovement`) | `+3` → `-5.5` (`-8.5`) |
| `openTotal` → `currentTotal` (`totalMovement`) | `52.5` → `54.5` (`+2.0`) |
| `favoriteFlippedSinceOpen` | `true` |

`spreadMovement`, `totalMovement`, `favoriteFlippedSinceOpen` and the implied
probabilities are **derived here** — upstream publishes the opening and current
numbers and leaves the arithmetic to you. The vig is left in, so the two sides
of a moneyline sum to a little over 1; that excess is the book's margin, and
removing it would be inventing data.

### `props` — the player board

About **659 prop markets on a single NFL game**: passing yards, receptions,
anytime touchdown scorer, first touchdown scorer, and 70-plus other market
types, each with the line it opened at, the line it sits at now and the
difference.

### `futures` — season-long markets

MVP, Offensive/Defensive Player of the Year, conference and division winners,
championship. Every runner carries its American price **and** its implied
probability, so `+400` and `-245` sit in the same sortable column.

### `predictor` — model against book

The source's own win projection and predicted margin per fixture. Put
`homeWinProbability` next to `homeImpliedProbability × 100`, or
`homePredictedPointDiff` next to `spread`, and the disagreements fall out.

### `events`, `providers`, `reference`

The schedule on its own (no odds, cheap), the sportsbook catalogue for a league
(71 entries for the NFL), and a probe that checks the source is live and
re-tests the assumptions this Actor is built on.

---

## Input

| Field | Default | Notes |
| --- | --- | --- |
| `mode` | `odds` | `odds`, `props`, `futures`, `events`, `predictor`, `providers`, `reference` |
| `league` | `nfl` | A short key, or the source's own `sport/league` form for anything else |
| `dates` | — | `20260920`, `2026`, or a range `20260901-20261001`. Empty = the current week only |
| `dateFrom` / `dateTo` | — | Used when `dates` is empty |
| `eventId` / `eventIds` | — | Scrape specific fixtures instead of a window |
| `season` | current year | `futures` mode |
| `includeUnpricedEvents` | `true` | Keep fixtures no book has priced yet, as `hasOdds: false` |
| `maxItems` | `500` | Record cap |
| `maxEvents` | `60` | Fixture cap — a whole NFL season window is 320 fixtures |
| `maxConcurrency` | `4` | |
| `maxNameLookups` | `400` | Budget for turning ids into names |
| `proxyConfiguration` | off | Not needed for ordinary runs |

League keys: `nfl`, `college-football`, `nba`, `wnba`, `ncaab`, `ncaaw`, `mlb`,
`nhl`, `epl`, `laliga`, `seriea`, `bundesliga`, `ligue1`, `ucl`, `mls`, `ufc`,
`pga`, `atp`, `wta`, `f1` — or anything else as `sport/league`, e.g.
`soccer/ned.1`. There are 17 sports and 219 soccer competitions.

### Examples

This week's NFL lines with movement:

```json
{ "mode": "odds", "league": "nfl" }
```

Every prop on one game:

```json
{ "mode": "props", "league": "nfl", "eventId": "401872932", "maxItems": 700 }
```

A month of Premier League fixtures:

```json
{ "mode": "events", "league": "epl", "dates": "20260915-20261015" }
```

The NFL futures board:

```json
{ "mode": "futures", "league": "nfl", "season": 2026, "maxNameLookups": 400 }
```

---

## Known limits — read these before you build on it

* **A fixture with no odds is normal.** Books post lines close to start time.
  Fixtures weeks out come back with `hasOdds: false` and a note; that is the
  source answering, not a block. Failures are separate `ERROR` records.
* **Coverage follows the season, not the league.** During testing NFL, college
  football, MLB, the Premier League, MLS and UFC carried lines; NBA, NHL,
  college basketball and tennis did not, because they were out of season.
* **Line movement needs both ends.** `spreadMovement` is null when the book has
  not published an opening number for that market.
* **Names are the expensive part.** Ids come free in the response; names cost one
  request each, cached. Past `maxNameLookups` a record keeps its ids and loses
  only the name — it is never dropped.
* **Prop counts are de-duplicated.** The feed publishes repeated rows (659 rows,
  521 distinct markets on one game). This Actor emits the distinct ones and logs
  how many repeats it dropped.
* **No historical line archive.** The source exposes open, close and current —
  not a tick-by-tick history. The movement-history endpoint returned `count: 0`
  on every fixture sampled. Run this Actor on a schedule if you want a series.
* **`providers` includes a placeholder.** Entry id `0` is literally named
  "Not Available"; it is passed through rather than hidden, as with every other
  upstream field.
* **Join on `providerId`, not `providerName`.** The same book is written
  "Draft Kings" in the odds response and "DraftKings" in the futures response.
  Names are passed through exactly as the source writes them.
* **Book count per fixture varies with kick-off.** A sportsbook's live in-play
  feed appears as a second row near game time and is gone hours later, so one
  row per fixture and two rows per fixture are both normal.

## Technical notes

Python, HTTP only, `curl_cffi` with a TLS ladder that remembers the winning
profile. No WAF answered during testing from either a residential address or
Apify's datacenter range, but the ladder stays because the profile that wins
locally is not always the profile that wins from a datacenter.

`CRAWLING_METHOD.md` has the full probe matrix, the ten gotchas found while
building (including the two hosts that disagree about date syntax and the
internal hostname leaking into pointers), and the candidates probed in the same
pass that were skipped with evidence.
