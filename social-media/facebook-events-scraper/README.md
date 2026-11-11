# Facebook Events Scraper

Collect public Facebook events by keyword and city, or straight from a page's
events tab: name, date, venue address, online or in-person, ticket price line,
host and attendance.

No login, no cookies to paste, no proxy required.

## Location goes in the search term

Facebook's event search takes no location parameter a signed-out client can use.
It is, however, a genuinely good text search — putting the city in the query
works:

| Query | Result |
| --- | --- |
| `yoga new york` | New York and Brooklyn yoga classes |
| `konser jakarta` | Jakarta concerts |
| `live music london` | London gigs |

So this actor takes `searchTerms` and `locations` and combines them:
2 terms × 3 cities = 6 searches. Supply locations on their own and each becomes
a search in its own right.

This is the one Facebook search vertical still open to logged-out clients —
`/search/pages/`, `/search/groups/` and `/search/top/` all return HTTP 404.

## What you get

| Field | Example |
| --- | --- |
| `name`, `eventUrl` | `Yoga with Shape Up NYC` |
| `dayTimeSentence` | `Fri, 25 Sep at 11:00 EDT and 2 more` |
| `startsAtIso`, `startTimestamp` | `2026-08-28T15:00:00Z` |
| `placeAddress` | `2636 E 14th St, Brooklyn, NY, United States, New York 11235` |
| `placeName`, `city`, `latitude`, `longitude` | |
| `isOnline`, `isPast`, `isCanceled`, `eventKind` | |
| `priceRangeText` | ticketing line, where the event sells tickets |
| `hostName`, `hostUrl` | on page-tab events |
| `goingCount`, `interestedCount`, `attendanceText` | `1`, …, `1 going` |
| `coverPhotoUrl`, `coverPhotoCaption` | |

## Two date fields, and why

Facebook publishes a human sentence (`Sun, 20 Sep at 16:00 EDT`) and, on search
results, an exact timestamp. Both are emitted: a sentence cannot be sorted, a
timestamp cannot be read aloud, and the sentence is the **only** one of the two
that a page's events tab carries.

That has a consequence worth knowing: a `startsAfter` / `startsBefore` filter
**drops** page-tab events, because they have no timestamp to judge. The run log
says so when it happens. Guessing a date from an abbreviated sentence with no
year would be worse.

## Input example

```json
{
  "searchTerms": ["live music", "art exhibition"],
  "locations": ["new york", "london"],
  "maxEventsPerQuery": 60,
  "excludePast": true,
  "onlyInPerson": true,
  "exportFormats": ["csv"]
}
```

Or from specific pages:

```json
{
  "pages": ["MTV", "https://www.facebook.com/coachella"],
  "maxEventsPerQuery": 50
}
```

## Honest limits

- **The event detail page is not public.** `facebook.com/events/<id>/` returns a
  67 KB generic shell to logged-out visitors — the same one for real and
  invented ids. So there is no full description and no guest list, and this
  actor does not pretend otherwise. `coverPhotoCaption` — Facebook's own alt
  text for the poster — is the closest thing the public payload has to a
  description, and it often contains the poster's headline.
- **The search response comes at two levels of detail.** Sometimes every event
  carries its date, venue and photo; sometimes the same URL returns
  name-and-link stubs. The actor detects a stub-only response and refetches
  once, which in testing restored full detail on all 20 events. It refetches
  once, not in a loop, and reports what it got.
- `goingCount` is parsed from Facebook's attendance line, which abbreviates
  large numbers. `attendanceText` keeps the original.
- Most events use a free-text place with no separate venue name; `placeName` is
  then the first segment of the address the organiser typed.

## Running it on Apify: use a residential proxy for pagination

Facebook serves the **rendered first page** to any IP, including Apify's. But the
**first pagination request from a datacenter IP** comes back with
`Rate limit exceeded`, so a platform run with no proxy stops at the events Facebook renders on the first page.

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
