# Spotify Artist Analytics & Monthly Listeners Tracker

Read the numbers on any Spotify artist page — **monthly listeners**, followers,
the **five cities with the most listeners** — and, because Spotify publishes no
history at all, remember them so the next run can tell you which way they moved.

Built for artist managers, A&R, promoters and PR teams who need growth evidence
rather than a screenshot: schedule it daily or weekly across a watchlist and
each run answers *how fast, in which direction, in which cities*.

No Spotify account, no Spotify for Artists login, no API key, no browser.

---

## What you get per artist

| Field | Notes |
| --- | --- |
| **`monthlyListeners`** | Unique listeners in the last 28 days |
| **`followers`** | Accounts following the artist |
| **`topCities`** | Five cities with city, country, region and listener counts |
| `listenersPerFollower` | Reach that has not converted into a following yet |
| **`monthlyListenersChange`** + `…Percent`, `…PerDay`, `trend` | Movement since the previous run |
| `topTracks` | Ten most-played tracks with **lifetime play counts** |
| **`discoveredOnPlaylists`** | The playlists actually feeding the artist new listeners |
| `featuredInPlaylists`, `relatedArtists` | Editorial placement and Spotify's similarity graph |
| `upcomingConcerts` | Dates, venues, cities, festival flag |
| `socialLinks` | Facebook, Instagram, Twitter, TikTok, YouTube, Wikipedia |
| `albumCount`, `singleCount`, `latestReleaseName`, `latestReleaseDate` | Catalogue at a glance |
| `biography`, `avatarImage`, `headerImage` | Press-kit material |

---

## Quick start

```json
{
  "artistUrls": ["https://open.spotify.com/artist/0gxyHStUsqpMadRV0Di1Qt"],
  "artistNames": ["Tulus", "NIKI"],
  "trackChanges": true,
  "exportFormats": ["csv"]
}
```

Artists can be given as links **or** plain names — a name costs one extra
search request, and the run log prints which artist it matched so you can spot
an ambiguous one.

---

## How the growth tracking works

Spotify shows today's number and nothing else. To turn that into a trend, each
run writes its readings to a **named key-value store** (`trackingStoreName`,
default `spotify-artist-analytics`) and compares the next run against it.

- The **first run** has nothing to compare against: rows are marked
  `isFirstReading: true`. That is the baseline, not a failure.
- Every later run adds `monthlyListenersChange`, `…ChangePercent`,
  `…ChangePerDay`, `followersChange`, `topTrackPlaycountChange`, `trend`,
  `previousReadingAt` and `daysSincePreviousReading`.
- `…ChangePerDay` is what makes a weekly run comparable with a daily one.
- Use a **named** store, not the run's own — a run-scoped store vanishes with
  the run and every run would look like the first. Point several scheduled runs
  at the same name to build one history; use different names to keep separate
  watchlists apart.

Schedule it daily for a launch campaign, weekly for a roster.

---

## Cost

**One request per artist**, plus one to pick up an anonymous token. A 200-artist
watchlist is 201 requests. Looking an artist up by name adds one request each.

---

## Limits worth knowing

- **Monthly listeners are a rolling 28-day figure Spotify refreshes on its own
  schedule**, so two runs hours apart will often show no change. Daily is the
  most granular cadence that means anything.
- **`worldRank` is null for almost everyone.** Spotify sends `0` for artists
  outside its published global ranking; that is normalised to `null` here so it
  cannot be misread as first place.
- **Top cities are always five**, and they are listener counts, not stream
  counts.
- **`discoveredOnPlaylists` arrives padded with placeholder entries** that
  resolve to nothing. They are dropped, so the count is of real playlists.
- This reads the **public artist page**. It is not Spotify for Artists and does
  not expose stream-by-stream, demographic or save data.

---

## Output

Every run writes to the Apify dataset. Set `exportFormats` to also drop a
ready-made `spotify-artist-analytics.csv`, `.xlsx`, `.json` or `.ndjson` into
the run's key-value store. Nested fields flatten poorly into CSV, so switch on
`emitTopTrackRows` if you want the top tracks as their own spreadsheet rows.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for how the data is obtained.
