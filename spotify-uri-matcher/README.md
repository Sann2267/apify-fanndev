# Spotify Bulk Text-to-URI Matcher

Paste a list of songs as plain text and get the exact **`spotify:track:` URI**
and open.spotify.com link for each — with a confidence score, and with bad
matches **rejected instead of guessed**.

Built for developers, setlist managers and curators automating playlist
building from outside sources: a Billboard chart, a YouTube ranking, a
festival lineup, a radio log, a spreadsheet a promoter emailed over.

No Spotify account, no API key, no browser.

---

## The problem this actually solves

Spotify's search returns a result for **any** text. Ask it for
`"asdkjh qweoiu zxcvbn"` and it hands back a real song. So a matcher that takes
the first result never fails and is wrong every time the input is — and you
find out when the playlist is already built.

This one scores every candidate against your title and artist and refuses
anything below a threshold you set:

```
exact    1.000  Bohemian Rhapsody - Queen        -> Bohemian Rhapsody   | Queen
exact    1.000  Texas Hold 'Em - Beyoncé         -> TEXAS HOLD 'EM      | Beyoncé
medium   0.814  Golden - HUNTR/X, EJAE, …        -> Golden              | HUNTR/X
low      0.320  asdkjh qweoiu zxcvbn             -> (rejected)
```

Rejected lines keep their best guess and the reason, so you can review rather
than re-run.

---

## Input formats it accepts

All of these work, mixed freely in one paste:

```
Bohemian Rhapsody - Queen
Queen - Bohemian Rhapsody
Beautiful Things by Benson Boone
Lose Control / Teddy Swims
12. Blinding Lights - The Weeknd
Birds of a Feather -- Billie Eilish
Title<TAB>Artist
https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT
```

**Both orders are tried** — `Title - Artist` and `Artist - Title` — and
whichever reads better wins, because neither can be told from the text alone.
Leading track numbers are stripped. A line that is already a Spotify link or
URI is passed straight through without spending a request.

For maximum accuracy, use the structured `tracks` input instead, where title
and artist are separate fields and an optional `durationMs` disambiguates
between recordings of the same song.

---

## Quick start

```json
{
  "queriesText": "Bohemian Rhapsody - Queen\nEspresso - Sabrina Carpenter\nNot Like Us - Kendrick Lamar",
  "minimumMatchScore": "0.70",
  "emitUnmatched": true
}
```

Every run also writes **`matched-uris.txt`** to the key-value store — the
matched URIs, one per line, ready to paste into a playlist importer.

---

## Choosing a threshold

| Setting | Use when |
| --- | --- |
| `0.85` | A wrong URI is worse than a missing one — automated playlist writes |
| `0.70` (default) | Balanced; catches casing, accents and version suffixes |
| `0.55` | You will review near-misses by hand and want maximum recall |

A **title-only** query is capped at `high` however well it scores — several
different recordings share a title, and nothing in the input says which one.

---

## Cost

**One request per line**, plus one to pick up an anonymous token. A 500-track
list is 501 requests. Lines that are already Spotify links cost nothing.

---

## Limits worth knowing

- **ISRC lookup is not supported here.** The search this actor uses does not
  understand ISRC queries — it treats the code as free text and returns
  nonsense. ISRC lookup only works on Spotify's public Web API search, which
  bans by IP for about twenty hours once its small anonymous allowance runs
  out, so it is deliberately not wired in.
- **One song, many ids.** Spotify mints a separate track id per release, so an
  album version, a single version and a remaster are different URIs. Supplying
  `durationMs` is the most reliable way to steer towards the one you mean.
- **Regional availability varies.** A track that exists in one market may be
  missing in another; matching is done against Spotify's global catalogue.
- **Scores are a similarity measure, not a probability.** `0.70` does not mean
  "70% likely correct" — calibrate it against your own list once and keep it.

---

## Output

Every run writes to the Apify dataset, plus `matched-uris.txt`. Set
`exportFormats` to also drop a ready-made `spotify-uri-matches.csv`, `.xlsx`,
`.json` or `.ndjson` into the run's key-value store. The **Needs review** table
view in the Console shows only the rejected lines with their best guesses.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for how the data is obtained.
