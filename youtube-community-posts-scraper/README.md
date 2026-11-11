# YouTube Community Post & Poll Scraper

Scrape the YouTube tab that every video-metric scraper ignores.

Give it channel handles. It returns each community post's **full text, like
count, publish time, outbound links, attached images, attached videos, and poll
questions with their options and total votes**.

This is audience-research material no other YouTube endpoint carries: what a
creator asks their audience, what they promote between uploads, and which posts
land.

No login, no cookies, no API key.

## What you get

```json
{
  "channelHandle": "@veritasium",
  "feedPosition": 1,
  "postId": "UgkxtIWAwjGL7mY_dtJC9fQX",
  "text": "Mayor of New York City, Zohran Mamdani, releases files exposing that New Yorkers were lied to about the quality of the air after the September 11th attacks…",
  "likeCountText": "1.3K",
  "likeCountApprox": 1300,
  "publishedTimeText": "8 days ago",
  "isEdited": false,
  "links": ["https://sept11documents.cityofnewyork.us/"],
  "attachmentType": "video",
  "video": {
    "videoId": "cMx139eTxoc",
    "title": "What does asbestos do to a person?",
    "url": "https://www.youtube.com/watch?v=cMx139eTxoc"
  }
}
```

Links are **unwrapped**: YouTube rewrites every outbound URL in a post to
`youtube.com/redirect?…&q=<real url>`. You get the destination, not the tracker.

## Attachment types

| `attachmentType` | What you get |
| --- | --- |
| `multi-image` | Up to 10 image URLs, highest resolution available (measured up to 5464×5464) |
| `image` | One image URL |
| `video` | `videoId`, title, URL, view-count text |
| `poll` | Options, total votes, poll type |
| `none` | Text-only post |

## Two limits, stated up front

**1. Like counts are abbreviated, never exact.** YouTube publishes `"1.9M"` and
nothing more precise to a logged-out client. You get `likeCountText: "1.9M"` and
`likeCountApprox: 1900000`, with `likeCountIsApprox: true` on every record. No
Actor can give you the exact figure without being signed in.

**2. Polls give the options and the total, not the split.** A poll returns its
exact wording and `totalVotesText: "1.7M votes"`. The per-option percentage is
shown only to a signed-in account that has voted — in the logged-out payload
there is a sign-in prompt where the percentage would be. `votesPerChoice` is
therefore `null` by design, with a note explaining why, rather than a fabricated
number.

Post **comment threads** are also out of scope: they need a separate InnerTube
continuation fetch.

## Four outcomes, not one

A scraper that reports "0 results" for all of these is hiding information:

| `recordType` | Meaning |
| --- | --- |
| `POST` | A parsed post |
| `EMPTY` | The page rendered fine and this channel has never posted |
| `ERROR` + `community-unavailable` | YouTube says the tab is off. **A channel setting, not a scrape failure** |
| `REDUCED` | The page never listed posts after 5 attempts — retry or use a proxy |

## Known limits

- **10 posts per channel.** That is one page. Older posts sit behind a
  continuation token this Actor does not follow.
- Publish times are **relative** (`"5 months ago"`), because that is all YouTube
  renders.

## The path that does not work

`/@handle/community` returns a full 761 KB page reading *"This Community isn't
available"* with zero posts — for **every** channel, including ones that post
constantly. It is not a per-channel setting and no consent cookie changes it.
The working path is `/@handle/posts`. This Actor uses the latter; see
[`CRAWLING_METHOD.md`](CRAWLING_METHOD.md).

## Input example

```json
{
  "mode": "channel",
  "channels": ["@MrBeast", "@veritasium", "@mkbhd"],
  "postsPerChannel": 10
}
```
