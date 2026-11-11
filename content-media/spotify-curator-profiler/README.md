# Spotify Curator & Playlist Owner Profiler

Find out **who is curating** a niche on Spotify, how much reach they have, and
what their taste actually looks like — the artists they favour, how underground
their picks are, how current their catalogue is, and whether they are still
active.

Built for artist teams pitching for playlist placement, for brands profiling
music influencers, and for market researchers mapping a scene.

No Spotify account, no API key, no browser.

---

## What you get per curator

| Field | Notes |
| --- | --- |
| `ownerName`, `ownerId`, `ownerUrl`, `ownerAvatar` | Who they are and where to find them |
| **`totalFollowers`** | Reach summed across their playlists found |
| `playlistsFound`, `biggestPlaylistName`, `totalTracksCurated` | Scale of what they run |
| **`topArtistNames`**, `topArtists`, `distinctArtists` | Who they actually play |
| **`undergroundScore`** | 0–1 from median play count — discovery curator or hits curator |
| `medianPlaycount`, `maxPlaycount` | The raw numbers behind it |
| `medianReleaseYear`, `catalogueSpreadYears` | New-music curator vs retrospective |
| `explicitShare` | Whether the playlist is brand-safe |
| **`lastUpdated`** | Still active, or abandoned two years ago |

Plus one **`PLAYLIST`** row per playlist — including its **description**, which
is where curators usually put their submission instructions and contact email.

---

## Quick start

```json
{
  "keywords": ["indie folk", "lofi study", "afrobeats 2026"],
  "minFollowers": 5000,
  "trackSampleSize": 50,
  "exportFormats": ["csv"]
}
```

Real output from a two-keyword run:

```
Lofi Girl          1 playlist   616,480 followers   underground 0.77   median yr 2021
mixstarrs          1 playlist   393,618 followers   underground 0.00   median yr 2020
Etymology Lofi     1 playlist   187,712 followers   underground 0.99   median yr 2022
```

Three curators in the same niche with completely different pitching profiles.

---

## Read this before you rely on it

**Spotify has closed off user profiles to anonymous clients.** Its profile
service answers `403 RBAC: access denied` even with a valid client-token, and a
user page renders nothing but a display name without a login. So there is **no
way to list a given user's public playlists, or who they follow** — that door
is shut, and any tool claiming otherwise is either logged in as someone or
guessing.

This actor works the other way round: it finds the **playlists**, which are
fully public and name their owner in full, and builds the curator profile from
those. That means:

- `playlistsFound` is what **this run discovered**, not the curator's complete
  catalogue. More keywords find more of their work.
- A curator only appears if at least one of their playlists surfaced in search.

---

## Coverage comes from keywords, not page size

Spotify's search returns **at most 30 mixed-type results** per query — tracks,
artists, playlists and podcasts together, typically 15–20 playlists — and it
**ignores every paging parameter**. Asking for more is not an error; it simply
changes nothing.

So breadth comes from running more, narrower keywords: `"indie folk"`,
`"indie folk 2026"`, `"folk acoustic chill"` will between them surface far more
curators than any single query can. Results are also **geo-biased by exit IP**,
so set the proxy country to the market you care about when profiling a local
scene.

**`includeEditorialPlaylists` is off by default** because Spotify's own account
owns the biggest playlist in nearly every niche, and leaving it in makes
"Spotify" top every ranking — true, but useless when you are looking for
independent curators to approach.

---

## Cost

One request per keyword, plus **one request per playlist** — which returns the
follower count and the track sample together, so taste profiling is free. Two
keywords yielding 13 playlists is 16 requests.

---

## Limits worth knowing

- **Follower counts are per playlist, not per curator.** Spotify publishes no
  profile-level follower number to anonymous clients, so `totalFollowers` is a
  sum across playlists found and one person following two of their playlists
  is counted twice.
- **`undergroundScore` is derived, not a Spotify field.** It is a transform of
  the median play count and is meant for comparing curators against each other,
  not as an absolute rating.
- **Playlists can hold podcast episodes and local files.** Those are skipped in
  the taste sample rather than counted as tracks.
- **A playlist that has been deleted or made private** produces an `ERROR` row;
  Spotify does not distinguish the two from outside.

---

## Output

Every run writes to the Apify dataset, with curators sorted by reach. Set
`exportFormats` to also drop a ready-made `spotify-curators.csv`, `.xlsx`,
`.json` or `.ndjson` into the run's key-value store.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for how the data is obtained.
