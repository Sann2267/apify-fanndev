# Crawling method — Facebook Ads Benchmarker

The benchmarker reads the same surface as the Ad Library scraper; this file
repeats that method in full so the actor stands on its own, then describes what
the benchmarking layer adds.

## Source surface: the Ad Library

Measured 2026-09-20 from an ordinary residential IP in Indonesia, curl_cffi,
no proxy, no login.

## The 403 is a challenge, not a block

`GET https://www.facebook.com/ads/library/?...` returns **HTTP 403 with a
481-byte body** on the first request of a session. Sixteen curl_cffi TLS
profiles, `m.facebook.com`, `web.facebook.com`, full browser headers and a
warmed cookie jar all produce the same 403 — which is what makes it look like a
geo/IP gate. It is not. The body is:

```html
<script>
  fetch('/__rd_verify_Q_6hBQRNlur3_...?challenge=3', {method: 'POST'})
    .finally(() => window.location.reload());
</script>
```

A single unauthenticated `POST` to that path returns 200 with

```
set-cookie: rd_challenge=...; Max-Age=86400; Domain=facebook.com
```

and the next `GET` of the same URL returns **200 with an 829 KB payload**. One
POST per session; the cookie is good for 24 hours. `proxy-status:
http_request_denied` in the 403 headers is the edge refusing an unverified
client, not a reputation decision about the IP.

`src/fbcore.py::FacebookSession.get_html` does this inline: on a 403 it looks for
the `__rd_verify` path, POSTs it, and retries the original request without
counting the attempt against the backoff ladder.

## The first 30 ads are server-rendered

The 200 response carries the search result set inside its
`<script type="application/json">` blocks:

```
ad_library_main.search_results_connection
  ├─ count: 26055                  ← total matching ads
  ├─ edges[].node.collated_results[]  ← 30 ads
  └─ page_info: { end_cursor, has_next_page }
```

Each ad node carries `ad_archive_id`, `is_active`, `page_id`, `start_date`,
`end_date`, `publisher_platform`, and a `snapshot` holding `page_name`,
`body.text`, `title`, `caption`, `link_description`, `link_url`, `cta_text`,
`cta_type`, `display_format`, `images[]`, `videos[]`, `cards[]`,
`page_categories` and `page_like_count`.

The parser finds ads by looking for **any dict that owns `ad_archive_id` and
`snapshot`**, rather than walking the path above. Facebook has moved that path
before; the key names have been stable.

**Carousel gotcha:** a carousel ad leaves `images` and `videos` empty and puts
its creatives in `cards[]`. Reading only the top level reports zero media for the
format that carries the most, so `_media()` gathers from all three.

## Pagination replays Facebook's own query

The legacy async endpoint is gone:
`/ads/library/async/search_ads/` returns **404** for both GET and POST, with or
without the challenge cookie. Pagination is GraphQL.

- `doc_id` is **not** in the HTML (`"doc_id"` appears 0 times).
- It *is* in one of the page's nine JS bundles, as a one-line module:
  `__d("AdLibrarySearchPaginationQuery_facebookRelayOperation",[],function(...){a.exports="24922295957467452"})`
- The variables come from the page itself: the relay preloader block publishes
  `{"queryID": ..., "variables": {...}, "queryName": "AdLibraryFoundationRootQuery"}`,
  and the pagination query takes a 23-field subset of exactly those variables
  plus `cursor` and `first`.

`POST /api/graphql/` with `lsd` + the `__spin_r/_b/_t` triple harvested from the
served document returns 200 and the next 30 ads. Verified end to end:
30 ads from SSR, then a 79 KB GraphQL reply with the next batch.

Neither the doc_id nor the queryID is hard-coded. Both are harvested per run,
because a pinned id dies silently on Facebook's next deploy — and a silent death
here would look like "this search has no more ads".

## Advertiser scoping is real, and branded content looks like a leak

`view_all_page_id=<id>&search_type=page` genuinely scopes the result set:
`view_all_page_id=89516513179` with `active_status=all` returned 30/30 ads whose
`page_id` was exactly that, out of 115 matching.

With `active_status=active` the same search returned 25 Nordstrom Rack rows plus
`Maria` and `Melissa Gonzalez`. Those are not a filter leak — their
`snapshot.branded_content` is
`{"page_id":"89516513179","page_name":"Nordstrom Rack"}`. The creator's page
posts the ad, the brand pays for it. The parser emits both sides
(`pageName` / `sponsorPageName`) so the row explains itself.

## What the Ad Library does not publish

| Field | Commercial ads | Political / issue ads |
| --- | --- | --- |
| `spend`, `impressions_with_index` | `null` | populated (ranges) |
| `targeted_or_reached_countries` | `[]` | populated |
| `reach_estimate`, `total_active_time` | `null` | sometimes populated |
| age / gender breakdown | absent | absent from the search response |

Confirmed by running the same search with `ad_type=all` and
`ad_type=political_and_issue_ads`: 30 ads each, `impressions_text` present 30/30
on the political search and 0/30 on the commercial one. The ad detail page
(`/ads/library/?id=<archive_id>`) adds nothing here — `demographic_distribution`
and `delivery_by_region` are 0 hits in its HTML too.

These are emitted as `null`/`[]` rather than omitted, so a buyer can tell
"Meta does not publish this" apart from "the parser missed it".

## Platform note: datacenter IPs are rate-limited on pagination

Measured 2026-09-20 on the Apify platform, three runs of the same Ad Library
search within one minute:

| Run | Ads | Pages | Log |
| --- | --- | --- | --- |
| Apify, no proxy | 30 | 1 | `Pagination stopped after 1 page(s): Rate limit exceeded` |
| Apify, `RESIDENTIAL` proxy | 60 | 4 | clean |
| Local residential IP, no proxy | 70 | 5 | clean |

The server-rendered first page is served normally from a datacenter IP -- the
403 challenge is solved, the 30 ads arrive, the `doc_id` is harvested from the
bundle. It is the **first `POST /api/graphql/`** that comes back HTTP 200
carrying `{"errors": [{"message": "Rate limit exceeded"}]}`.

Two consequences, both built in:

1. `FacebookSession._note_rate_limit` inspects every GraphQL reply and logs the
   remedy by name the first time it sees a rate limit. Without it the symptom is
   indistinguishable from "the search only had 30 results" -- a silent wrong
   answer, which is the failure mode this portfolio is built to avoid.
2. The proxy field in the input schema says so, and says which group fixes it.

This is the opposite of the Google Maps finding in this portfolio, where
residential proxies *broke* the surface. It is worth measuring per surface
rather than assuming.

## Cost shape

One HTTP request per 30 ads, ~800 KB for the first page and ~80 KB per GraphQL
page after that, plus a one-off bundle fetch (~3.5 MB) the first time pagination
is needed in a session. No proxy, no browser, no captcha solver.

## What the benchmarker adds on top

The transport and parsing above are shared verbatim with the Ad Library scraper
(`src/search.py` is that actor's search layer, `src/parser.py` its parser). The
benchmarker's own work is in `src/analytics.py` and it is arithmetic, not
crawling:

- **Sample budgeting.** A niche's ad budget is divided across the searches that
  feed it, then de-duplicated by `ad_archive_id`. Without this a two-keyword
  niche collects twice the ads of a one-keyword niche and every share it reports
  looks twice as solid.
- **Words once per ad.** Phrase counts use a per-ad set, not a bag of words. An
  ad repeating its slogan six times would otherwise outvote six advertisers.
- **Template tokens stripped.** `{{product.name}}` is genuine published text on
  dynamic-creative ads, but it is a placeholder; counted, it puts "product" at
  the top of every ecommerce niche.
- **Longevity as the performance proxy.** Meta publishes no spend or impressions
  for commercial ads (see the table above), so `runningDays` grouped by CTA, by
  format and by copy-length band is the only performance-shaped signal the public
  surface supports. Groups thinner than `minGroupSample` are dropped rather than
  reported.
