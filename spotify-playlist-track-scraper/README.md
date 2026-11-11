# Spotify Playlist & Track Metadata Scraper

Turn any Spotify playlist into a spreadsheet: every track with its artists,
album, release date, duration, cover art — and **`playcount`**, Spotify's real
lifetime stream count for that recording, which its official API does not
publish at all.

Built for curators, DJs, labels and content teams who need playlist contents
*outside* Spotify: to migrate a playlist to another platform, to analyse what a
tastemaker is actually playing, or to keep a catalogue in sync.

No Spotify account, no developer app, no API key, no browser.

---

## What you get per track

| Field | Notes |
| --- | --- |
| **`playcount`** | Lifetime streams for this recording. **Not available in Spotify's official API** |
| `trackName`, `artistName`, `artistNames`, `artists` | Title and every credited artist, with ids and links |
| `albumName`, `albumUrl`, `releaseDate` | The release this recording sits on |
| `duration`, `durationMs` | `3:32` and `212879` |
| `position`, `addedAt` | Where it sits in the playlist and when it was added |
| `explicit`, `playable`, `discNumber`, `trackNumber` | Content and sequencing flags |
| `trackId`, `trackUri`, `trackUrl`, `coverArt` | Stable identifiers plus the largest cover image |
| `isrc`, `popularity`, `previewUrl` | Only when **ISRC enrichment** is on — see below |

Plus one **`PLAYLIST`** row per playlist: name, description, follower count,
owner, cover art, and — for Spotify's own editorial charts — `lastUpdated`,
`rankType` and `newEntriesCount`.

---

## Quick start

```json
{
  "playlistUrls": ["https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"],
  "maxTracksPerPlaylist": 1000,
  "exportFormats": ["csv"]
}
```

Share links with a `?si=` tail, `/intl-id/` localised links, `spotify:playlist:`
URIs and bare ids are all accepted. Individual songs go in `trackUrls` and come
back with the **record label** and copyright lines as a bonus.

---

## About ISRC and the popularity score

These two fields are **off by default**, and it is worth knowing why.

Spotify's playlist API does not carry them. They exist on exactly one endpoint
an anonymous client can reach — Spotify's search endpoint — so each track needs
its own extra request. That endpoint is also the only rate-limited surface
involved: after a few dozen lookups it starts refusing, and **the refusal
follows your IP for roughly 20 hours**, not your session.

So:

- Leave `enrichWithIsrc` off for ordinary playlist exports. You still get
  `playcount`, which is the more useful number for most work.
- Turn it on when you genuinely need ISRC (royalty matching, radio reporting,
  cross-platform linking), keep `maxIsrcLookups` modest, and **enable the
  proxy** so the rate limit does not land on a shared address.
- If the limit is hit mid-run, enrichment stops and everything else still
  completes. Affected rows are marked `isrcLookup: "skipped-quota"` rather than
  silently left blank.

`isrcLookup` always tells you how solid the match is: `exact` means the very
same recording id, `title-artist` means the same song but possibly a different
release — which can carry a **different ISRC**.

---

## Cost

One request per 100 tracks, plus one to pick up an anonymous token. A 50-track
playlist is two requests; a 1 000-track playlist is eleven. ISRC enrichment adds
one request per track on top.

---

## Limits worth knowing

- **Private and follower-only playlists are not readable.** They come back as a
  `not_found` error row, the same as a deleted playlist — Spotify does not
  distinguish them from outside.
- **Playlists can contain podcast episodes and local files.** Those are skipped
  rather than emitted as empty rows; track `position` still reflects the real
  playlist order.
- **Spotify issues a separate track id per release.** The same song can appear
  under several ids with different play counts. `trackUri` is what identifies
  the exact recording in the playlist.

---

## Output

Every run writes to the Apify dataset. Set `exportFormats` to also drop a
ready-made `spotify-playlist-tracks.csv`, `.xlsx`, `.json` or `.ndjson` into the
run's key-value store.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for how the data is obtained.
