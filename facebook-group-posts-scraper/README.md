# Facebook Group Posts & Comments Scraper

Read what a public Facebook group is actually talking about: every post with its
text, author, timestamp, reaction count, comment count, share count and media —
paginated past the handful Facebook renders by default.

Built for market researchers, product teams and brand managers who want the
community's own words rather than a summary of them.

## Read this before you buy

**Facebook publishes the comment *count* on a group post to logged-out clients,
but not the comment *text*.** Measured 2026-09-20: a group post permalink
returns `comments.total_count: 29` and `comments.edges: []`, served by Meta's
`Unauthenticated` comment renderer. Every post this actor returns carries its
real `commentCount`; `commentsServed` tells you how many comment bodies Facebook
actually handed over, which for group posts is currently zero.

The `scrapeComments` option is there if you want to verify that for yourself, or
to pick the bodies up automatically if Meta's gating changes. It is **off by
default** because switching it on costs one request per post and, today, returns
nothing.

Everything else on this page is real and tested.

## What you get

One row per post:

| Field | Example |
| --- | --- |
| `groupName`, `groupId`, `groupPrivacy` | `React.JS developers -2023`, `1873009809663604`, `OPEN` |
| `groupMemberCount`, `groupMemberCountLabel` | `117400`, `117.4K members` |
| `authorName`, `authorId`, `authorUrl` | `Mohamed Hafez`, … |
| `text` | the post body |
| `createdAtIso` | `2026-07-09T01:41:29Z` |
| `reactionCount`, `commentCount`, `shareCount` | `43`, `29`, `4` |
| `attachmentUrls`, `attachmentCount` | photo/video CDN links |
| `postUrl` | permalink |

Plus a `RUN_SUMMARY` row: posts collected, distinct authors, total reactions,
total comments, newest and oldest post.

## Which groups can be read

Only groups that Facebook serves to a signed-out visitor. A private group, a
deleted group and a typo all return the same HTTP 200 with a ~330 KB shell, so
this actor checks the payload rather than the status code and gives you a
specific error row:

> `group_unavailable — Facebook served the empty shell (~330 KB). The group is
> private, does not exist, or is not readable without logging in.`

That is deliberately honest: a status-code check would report every private
group as a successful empty scrape.

## Input example

```json
{
  "groups": [
    "React.JSdevelopers",
    "https://www.facebook.com/groups/1873009809663604"
  ],
  "maxPostsPerGroup": 100,
  "minComments": 5,
  "postedAfter": "2026-01-01",
  "exportFormats": ["csv"]
}
```

## Filters

`textContains`, `minReactions`, `minComments` and `postedAfter` are applied after
fetching, so the run summary still reflects everything that was read. Posts whose
reaction count or timestamp Facebook withheld are **dropped** by a numeric
filter rather than admitted on a guess — an unknown number cannot be shown to
clear a bar.

## Running it on Apify: use a residential proxy for pagination

Facebook serves the **rendered first page** to any IP, including Apify's. But the
**first pagination request from a datacenter IP** comes back with
`Rate limit exceeded`, so a platform run with no proxy stops at the first batch of posts.

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

- `authorId` is an opaque `pfbid…` token for newer accounts rather than a
  number. That is Facebook's own identifier format, not a parsing artefact.
- `attachmentUrls` are signed CDN links and expire. Download what you need during
  or shortly after the run.
- Group membership questions and their answers are shown only to admins and are
  not part of any public surface, so they are not returned.
- Member counts are abbreviated by Facebook (`117.4K`); the parsed number is
  approximate and the raw label is kept beside it.
