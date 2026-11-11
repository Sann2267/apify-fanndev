# Facebook Reels & Video Metadata / Transcript Extractor

Extract Facebook reels and videos with their play counts, engagement, duration,
audio track, **direct MP4 URLs** and **spoken-word transcripts**.

Read a page's whole reels or videos tab, or pass individual reel / watch / video
URLs. No login, no cookies to paste, no proxy required.

## The transcripts are real

Facebook publishes a SubRip caption file for many reels. This actor finds the
`.srt` link in the payload, downloads it, and parses it into plain text plus
timed cues:

> `You think you know Domino's but when it's mission critical, it's not the pizza
> we send in. Operation Loaded Chicken is a go. Crispy Bacon and Tomato, team
> leader…`

A live check on one page's reels tab found captions on **4 of 10** reels and
transcribed them. Videos with no captions get `transcript: null` — this actor
does not run speech recognition of its own and does not pretend to.

## What you get

| Field | Example |
| --- | --- |
| `videoId`, `permalinkUrl`, `isReel` | `637979908801309`, `facebook.com/reel/…`, `true` |
| `pageName`, `pageId` | `Domino's Pizza` |
| `caption`, `title` | the post text and video title |
| `playCount`, `playCountLabel` | `292000`, `292K` |
| `reactionCount`, `commentCount`, `shareCount` | |
| `engagementTotal`, `engagementRatePercent` | `442`, `0.151` |
| `lengthSeconds`, `width`, `height` | `39.25`, `1080`, `1920` |
| `trackTitle`, `isOriginalAudio` | audio track behind the reel |
| `videoHdUrl`, `videoSdUrl`, `thumbnailUrl` | direct downloads |
| `captionsUrl`, `captionLocales`, `transcript` | |
| `createdAtIso` | `2025-01-27T…` |

## Two tabs, two kinds of play count

| Tab | Play count |
| --- | --- |
| `/reels/` | abbreviated — Facebook publishes `"292K"`, parsed to `292000` |
| `/videos` | exact integers — `270777`, `390753`, `292030` |

Both numbers are given: `playCount` (parsed) and `playCountLabel` (exactly what
Facebook rendered), so an approximation is never mistaken for an exact figure.
Read both tabs to get the widest coverage.

## Input example

```json
{
  "pages": ["dominos"],
  "tabs": ["reels", "videos"],
  "maxVideosPerTab": 30,
  "fetchTranscripts": true,
  "onlyWithCaptions": true,
  "exportFormats": ["csv"]
}
```

Or for specific videos:

```json
{
  "videoUrls": [
    "https://www.facebook.com/reel/637979908801309",
    "https://www.facebook.com/watch/?v=10153231379946729",
    "1053159700187202"
  ]
}
```

The watch URL is used as the resolver, so you never need to know whether an id
is a reel or a page video.

## Running it on Apify: use a residential proxy for pagination

Facebook serves the **rendered first page** to any IP, including Apify's. But the
**first pagination request from a datacenter IP** comes back with
`Rate limit exceeded`, so a platform run with no proxy stops at the videos Facebook renders in the tab.

The rate limit is on Facebook's GraphQL endpoint, which every actor in this
family uses for its second page onwards. It was measured on 2026-09-20 with the
Ad Library actor, three runs of the same search within a minute:

| Run | Result |
| --- | --- |
| Apify, no proxy | 30 results, 1 page — log: `Rate limit exceeded` |
| Apify, `RESIDENTIAL` proxy | 60 results, 4 pages |
| Local machine, no proxy | 70 results, 5 pages |

So: switch the Apify proxy on and pick the **RESIDENTIAL** group whenever you
want more than the first page. Running from your own machine needs no proxy at
all.

The actor logs a warning naming the rate limit when it hits one, so a short run
is never silently mistaken for a short result set.

## Notes

- `engagementRatePercent` is engagement over plays, and is **null** when the play
  count is unknown or zero. A fabricated denominator would turn an unknown into a
  confident wrong number.
- `videoHdUrl`, `videoSdUrl`, `thumbnailUrl` and `captionsUrl` are signed CDN
  links and expire. Download what you need during or shortly after the run.
- Reels tabs are large — about 13 MB each — which is why `maxVideosPerTab`
  defaults to 20.
- A page with no reels tab, or a video restricted to signed-in viewers, produces
  an `ERROR` row saying so rather than a silent empty result.
