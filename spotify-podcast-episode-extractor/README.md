# Spotify Podcast Episode Extractor

Export every episode of any Spotify podcast — title, **full description**,
duration, release date, share link — and then get the things the description
actually contains: **chapter timestamps**, **sponsor domains**, and the **guest
names** in the title.

Built for media researchers, PR teams hunting interview slots, and content
analysts tracking what podcasts are covering. A podcast's guest list, chapter
breakdown and advertiser roster are all buried in one free-text blob; this
turns that blob into columns.

No Spotify account, no API key, no browser.

---

## What you get per episode

| Field | Notes |
| --- | --- |
| `episodeName`, **`description`**, `releaseDate`, `releasedAt` | Spotify publishes release times to the minute |
| `duration`, `durationMinutes` | `1:12:45` and `73` |
| **`guestHints`** | Names read out of the title — a heuristic, honestly named |
| **`chapters`**, `chapterCount` | Every `12:34 Topic` line, with second offsets |
| **`sponsorDomains`** | Advertiser domains, after stripping the show's own links |
| `links`, `mentionedHandles` | Everything else the description points at |
| `hasVideo`, `hasTranscript`, `isPaywalled`, `explicit` | What kind of episode it is |
| `episodeUrl`, `shareUrl`, `coverArt`, `audioPreviewUrl` | Links and media |

Plus one **`SHOW`** row per podcast: publisher, description, episode count,
**average rating and review count**, topics and cover art.

---

## Quick start

```json
{
  "showUrls": ["https://open.spotify.com/show/4rOoJ6Egrf8K2IrywzwOMk"],
  "showNames": ["Huberman Lab"],
  "releasedAfter": "2026-01-01",
  "maxEpisodesPerShow": 500,
  "exportFormats": ["csv"]
}
```

Podcasts can be given as links **or** plain names. Individual episodes go in
`episodeUrls`.

---

## The date window is also a cost control

Episodes arrive newest first, so `releasedAfter` does not just filter — it
**stops paging** the moment the catalogue goes older than your date. Pulling
September's episodes from a 2 753-episode show costs three requests, not
twenty-eight.

---

## About the mined fields

`mineDescriptions` costs **no extra requests**; it reads text already in the
response. What it does is labelled honestly:

- **`chapters`** — timestamp lines in the description. A timestamp later than
  the episode's own duration is discarded, because it is a date or a price that
  looks like one.
- **`sponsorDomains`** — link domains with the show's own distribution and
  social platforms removed. In an ad-supported podcast these are the
  advertisers; in one that is not, they are just links.
- **`guestHints`** / **`episodeNumberHint`** — derived from the title. Nothing
  on Spotify marks who a guest is, so these are guesses from title convention.
  They are named `…Hints` for that reason and should not be treated as a field
  Spotify publishes.

---

## Cost

One request for the show, plus one per 100 episodes. A 100-episode pull is
three requests including the token. Looking a show up by name adds one; each
individual episode URL costs one.

---

## Limits worth knowing

- **Transcript text is not public.** `hasTranscript` tells you Spotify has one;
  the words are not exposed to an unauthenticated client and are not fetched.
- **Paywalled episodes appear in the list** with `isPaywalled: true`, but their
  audio is not accessible.
- **`episodeCount` comes from the episode query, not the show query** —
  Spotify's show metadata returns a single sample episode and no total.
- **Descriptions vary enormously.** Some publishers write full chapter lists;
  others leave the description empty. `descriptionLength` and `chapterCount`
  make that visible rather than silently returning nothing.

---

## Output

Every run writes to the Apify dataset. Set `exportFormats` to also drop a
ready-made `spotify-podcast-episodes.csv`, `.xlsx`, `.json` or `.ndjson` into
the run's key-value store. Chapters and links are nested, so they are kept out
of the spreadsheet columns and stay in the JSON exports.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for how the data is obtained.
