# Spotify Global & Regional Charts Monitor

Scrape Spotify's **Top 50** daily charts across **49 countries**, the **Top
Songs** weekly charts across 14, and the global weekly **track, album and
artist** charts — and, because Spotify's chart playlists publish only today's
order, find out what actually *moved*.

Built for label analysts, radio programmers, music journalists and digital
marketers who need chart history rather than a single snapshot: schedule it and
every run reports climbers, fallers, new entries and drop-outs per territory.

No Spotify account, no API key, no browser.

---

## What you get

Per **`CHART_ENTRY`** row:

| Field | Notes |
| --- | --- |
| **`rank`**, `previousRank`, **`rankChange`**, **`entryStatus`** | `MOVED_UP` / `MOVED_DOWN` / `NO_CHANGE` / `NEW_ENTRY` |
| `trackName`, `artistName`, `artistNames`, `albumName` | The charting recording and everyone credited |
| **`playcount`** | Lifetime streams — **not in Spotify's official API** |
| `chartName`, `country`, `recurrence`, `chartLastUpdated` | Which chart, and when Spotify last recalculated it |
| `trackUrl`, `artistUrl`, `albumUrl`, `coverArt` | Links and artwork |

Plus a **`CHART_EXIT`** row for every track that was on the chart last run and
is not now, and one **`CHART_SUMMARY`** per chart — entry count, followers, how
many are new, how many climbed or fell, and the biggest climber.

From the public charts service you additionally get **album** and **artist**
charts, with Spotify's own `peakRank`, `appearancesOnChart` (weeks on chart) and
`consecutiveAppearances`.

---

## Quick start

```json
{
  "countries": ["GLOBAL", "US", "GB", "ID", "BR"],
  "recurrence": "daily",
  "includeGlobalWeeklyCharts": true,
  "trackRankMovement": true,
  "exportFormats": ["csv"]
}
```

---

## Two very different chart surfaces

**Country charts** come from Spotify's editorial chart playlists. They cover
around fifty territories and both cadences — but they are just ordered track
lists. Spotify tells you there are "3 new entries" and never which three.

**The public charts service** needs no credential whatsoever, and returns real
chart records: `previousRank`, `peakRank`, `entryStatus`, weeks on chart, for
tracks **and albums and artists**. Its limitation is coverage: global weekly
only. Per-country and historical charts there sit behind a login.

This actor reads both, and fills the gap in the first with its own memory.

---

## How movement tracking works

Each run writes the order it saw into a **named key-value store**
(`trackingStoreName`) and compares the next run against it.

- The **first run** is the baseline — entries are marked `entryStatus:
  "BASELINE"`, deliberately *not* `NEW_ENTRY`, because a real 50-track turnover
  should not look identical to a first run.
- Matching is on `trackUri`, so a re-release under a different id counts as a
  new entry — which is also how Spotify treats it.
- Use a **named** store, not the run's own: a run-scoped store is deleted with
  its run and every run would report `BASELINE`.

Daily charts recalculate once a day, so scheduling more often than daily
produces `NO_CHANGE` rows. Weekly charts update Thursdays.

---

## Cost

**One request per country chart**, one for the whole public charts service, plus
one to pick up an anonymous token. Ten countries plus the global charts is
twelve requests.

---

## Limits worth knowing

- **Viral 50 no longer exists.** Spotify retired it. Its old ids still answer
  HTTP 200 with an empty body, so the actor recognises them by name and says so
  in the error row rather than reporting an empty chart.
- **Weekly charts cover far fewer countries than daily ones** — 14 against 49.
  Asking for an unavailable country stops the run with the full list instead of
  silently returning nothing.
- **Chart playlists are invisible to search.** Spotify excludes them from every
  search surface, so they can only be reached by id. The catalogue in
  `src/catalog.py` was verified entry by entry; anything outside it can be
  passed as a `playlistUrls` entry.
- **`peakRank` and weeks-on-chart are only published on the public service**,
  and even there Spotify leaves them unset on many entries. Unset arrives as
  `0`, which is normalised to `null` so it cannot read as "peaked at 0".

---

## Output

Every run writes to the Apify dataset. Set `exportFormats` to also drop a
ready-made `spotify-charts.csv`, `.xlsx`, `.json` or `.ndjson` into the run's
key-value store.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for how the data is obtained.
