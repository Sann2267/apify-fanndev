# Facebook Page Review & Rating Scraper

Get a Facebook business page's rating and the reviews behind it: the headline
percentage, the total review count, and for each review the author, the
recommend / do-not-recommend vote, the written text, Facebook's own experience
tags, the timestamp and the engagement.

No login, no cookies to paste, no proxy required.

## The rating is a percentage, not stars

Facebook retired star ratings for pages. What a page has now is a recommendation
vote, and its summary line looks like this:

> `30% recommend (12,651 reviews)`

So `recommendPercent: 30.0` and `reviewCount: 12651` **are** the rating. There is
no 4.3-out-of-5 hidden in the payload, and this actor does not manufacture one
from the percentage.

## What you get

**One `PAGE_RATING` row per page**

| Field | Example |
| --- | --- |
| `ratingSummaryText` | `30% recommend (12,651 reviews)` |
| `recommendPercent` | `30.0` |
| `reviewCount` | `12651` |
| `reviewsEnabled` | `true` |
| `reviewsCollected` | how many this run actually kept |

**One `REVIEW` row per review**

| Field | Example |
| --- | --- |
| `reviewerName`, `reviewerId`, `reviewerUrl` | `Mike Phipps`, … |
| `isRecommended` | `false` |
| `reviewTitle` | `Mike Phipps doesn't recommend Domino's Pizza.` |
| `reviewText` | `Every time I order, there is something that goes wrong…` |
| `tags` | `["Disappointing food", "Casual"]` |
| `createdAtIso` | `2026-09-20T00:03:50Z` |
| `reactionCount`, `commentCount` | engagement on the review itself |
| `reviewUrl` | permalink |

Plus a `RUN_SUMMARY`: reviews collected, how many recommend, how many do not,
how many carry written text, and the sample's own recommend percentage next to
the page's official one.

## Input example

```json
{
  "pages": ["dominos", "https://www.facebook.com/starbucks"],
  "maxReviewsPerPage": 100,
  "onlyNotRecommended": true,
  "onlyWithText": true,
  "exportFormats": ["xlsx"]
}
```

That is the complaints workflow: every negative review with text, for two pages,
in a spreadsheet.

## Pacing

Facebook streams the reviews tab about **three reviews per request**. 100 reviews
is roughly 34 requests, so set `maxReviewsPerPage` to what you actually need. The
rating summary is read in the very first request and is returned no matter how
low you set the cap.

## Honest limits

- `isRecommended` is read from Facebook's own sentence ("… doesn't recommend …"),
  because the payload carries no boolean for it. The actor requests `en-US` so
  that sentence is in English; if it ever comes back in another language the
  vote is reported as `null` rather than guessed.
- A page with reviews switched off returns `reviewsEnabled: false` and no review
  rows. That is the real answer, not a failure.
- A slug that does not exist returns an `ERROR` row saying so. Facebook answers
  HTTP 200 for missing pages, so a status-code check would report every typo as a
  successful empty scrape; this actor checks the payload instead.
- Replies from the business are comments on the review post. The `commentCount`
  includes them; their text is not collected.
- `reviewerId` is an opaque `pfbid…` token for newer accounts. That is
  Facebook's own identifier format.

## Running it on Apify: use a residential proxy for pagination

Facebook serves the **rendered first page** to any IP, including Apify's. But the
**first pagination request from a datacenter IP** comes back with
`Rate limit exceeded`, so a platform run with no proxy stops at the first few reviews.

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
