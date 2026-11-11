# Crawling method — Facebook events

Measured 2026-09-20, curl_cffi, no proxy, no login, exit IP Indonesia.

## Event search is the last open search vertical

Every other Facebook search path returns **HTTP 404** to a logged-out client:

```
/search/pages/?q=...    404
/search/places/?q=...   404
/search/groups/?q=...   404
/search/top/?q=...      404
/search/posts/?q=...    404
```

`/events/search/?q=...` returns **200** with real server-rendered event nodes.
It takes no location parameter a signed-out client can drive, but it is a good
text search, so the city goes in the query: `yoga new york` returned Brooklyn
yoga classes, `konser jakarta` returned Jakarta concerts, `live music london`
returned London gigs.

`/events/explore/<city>/<id>/` and `/events/explore/` are dead ends — 332 KB
shell and 404 respectively.

## Two surfaces, two shapes

**Search** (`/events/search/?q=`) — the rich node:

```json
{"__typename": "Event", "id": "1089275243587546",
 "name": "Therapeutic Yoga: Movement Lab",
 "url": "https://www.facebook.com/events/1089275243587546/",
 "day_time_sentence": "Sun, 20 Sep at 16:00 EDT",
 "start_timestamp": 1789934400,
 "event_place": {"__typename": "FreeformPlace",
                 "contextual_name": "149 Irving Ave , Brooklyn, NY, ..."},
 "ticketing_context_row": {"price_range_text": null},
 "is_online": false,
 "social_context": {"text": "1 going"},
 "cover_photo": {"photo": {"accessibility_caption": "May be an image of ..."}}}
```

**Page events tab** (`/{slug}/events`) — carries `event_creator` (the host) but
**no `start_timestamp`**, only `day_time_sentence: "Mon, 6 Nov 2023"`.

That asymmetry is why the output has both a sentence and a timestamp, and why a
date filter drops page-tab events instead of parsing an abbreviated, localised,
sometimes year-less sentence into a date.

## The response comes at two levels of detail

The same search URL returns, on different requests, either the rich node above
or a stub:

```json
{"__typename": "Event", "id": "...", "name": "...", "url": "...",
 "typeaheadProfilePicture": {...}}
```

Both shapes appear in one response for the same event, too. Two consequences:

1. **Merge by id, gaps only.** Taking the first matching node produces events
   with null dates and places for no reason visible in the data. The parser
   merges every node sharing an id, never overwriting a value already found.
2. **Refetch once when everything is a stub.** A live run returned 20 stub-only
   events; a second request to the same URL returned full detail for all 20.
   The actor detects the stub-only case and refetches once — not in a loop — and
   reports `eventsWithDetail` either way.

## The event detail page is closed

`/events/<id>/` returns 67 KB with
`og:description = "See posts, photos and more on Facebook."` — identical for a
real id and an invented one. There is no detail fetch to offer, so the full
description and guest list are simply not in this actor's output. Facebook's
machine-generated `accessibility_caption` on the cover photo is the nearest
public substitute and is emitted as `coverPhotoCaption`.

## Pagination

- Search: `SearchCometResultsPaginatedResultsQuery`, id from the JS bundle,
  cursor from the rendered `page_info` (a JSON blob, not an opaque string).
- Page tab: `ProfileCometAppCollectionEventsRendererPaginationQuery`, same
  method.

Measured: 7 rendered + ~9 per GraphQL call on search. Where the replay does not
succeed, the actor keeps the rendered events, logs a warning and returns a
smaller honest answer.

## Cost shape

~470 KB per search page, ~715 KB per page events tab, plus one extra request per
pagination step and at most one refetch per stub-only search. No proxy, no
browser.
