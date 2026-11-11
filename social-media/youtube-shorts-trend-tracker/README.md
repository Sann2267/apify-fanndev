# YouTube Shorts Viral Trend Tracker

See what is actually going viral on YouTube Shorts, by hashtag, with the numbers
you need to rank it.

Give it hashtags. It returns YouTube's own ranked grid of Shorts for each one,
then opens each clip for the figures the grid does not carry: **exact views,
likes, the like-to-view ratio, duration, sound attribution and hashtags**.

Shorts only — a regular upload that sneaks into a hashtag grid is flagged
(`isShortFormat: false`) rather than quietly mixed in.

No login, no cookies, no API key.

## What you get

```json
{
  "hashtag": "cooking",
  "gridPosition": 1,
  "title": "Frog Eggs Time Challenge! ⏱️🐸🧪",
  "channelName": "Meow Nhi Nhi",
  "viewCount": 3397251,
  "likeCount": 36218,
  "likeToViewPercent": 1.0661,
  "likeCountIsApprox": false,
  "lengthSeconds": 52,
  "soundAttribution": "Original Sound",
  "hashtags": ["Mukbang", "buldak", "buldakchallenge", "cooking", "foodchallenge"],
  "url": "https://www.youtube.com/shorts/FX4RT1cp7Rs"
}
```

`gridPosition` is YouTube's own ranking for that hashtag — it *is* the trend
signal, so it rides along on every record and enrichment never reorders anything.

## Why the per-Short fetch is on by default

The hashtag grid alone cannot rank anything. Measured 2026-09-20:

| | Hashtag grid | Short's own page |
| --- | --- | --- |
| Views | **rounded** — "3.3 million" | exact — `3,397,251` |
| Likes | **none at all** | yes |
| Like-to-view ratio | impossible | yes |
| Sound | no | yes |
| Duration | no | yes |
| Cost | 1 request per hashtag | 1 request per Short |

Set `detail: false` if you only want the ranked list and can live with
3.3M-sized buckets.

## Two kinds of like count

| Surface | Like figure | Sound? |
| --- | --- | --- |
| `/shorts/<id>` (default) | rounded — "36 thousand" → `36000` | yes |
| `/watch?v=<id>` (`exactLikes: true`) | exact — `36,218` | no |

Every record carries `likeCountIsApprox` so a rounded figure is never presented
as an exact one. If you ask for `exactLikes` **and** the Short's page has no
sound attribution, the Actor spends a second request to go get it — that is the
only path that costs two requests per Short.

## Tracking growth over time

Run the same hashtags on a schedule. Each run stamps `_scrapedAt`, so two runs
of `#cooking` give you the delta in `viewCount`, `likeCount` and `gridPosition`
per `videoId` — which is the growth-rate signal. The Actor does not keep state
between runs; comparing datasets is yours to do.

## Known limits, stated plainly

- **36 Shorts per hashtag.** That is one grid page, and it is what YouTube
  serves. The page carries a single continuation token; this Actor does not
  follow it. Ranked top-36 is the useful part of a trend anyway.
- **No historical data.** YouTube exposes the grid as it is right now. Growth
  requires scheduling (above).
- **Sound attribution is often just "Original Sound".** That is what YouTube
  reports for most Shorts; a licensed track shows its title instead.

## Reliability

The hashtag grid measured unusually stable — nine fetches across three TLS
profiles on 2026-09-20 returned 37 lockups and 36 view figures **every single
time**. Individual Shorts pages behave like watch pages and occasionally arrive
without their payload, so the Actor retries up to five times, rotating TLS
profile, before emitting `recordType: "REDUCED"`. A `REDUCED` record still
carries its grid figures — you lose the exact numbers, not the row.

## Input example

```json
{
  "mode": "hashtag",
  "hashtags": ["cooking", "fyp", "asmr"],
  "shortsPerHashtag": 36,
  "detail": true,
  "exactLikes": true,
  "concurrency": 4
}
```
