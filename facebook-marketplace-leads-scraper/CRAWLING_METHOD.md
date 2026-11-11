# Crawling method — Facebook Marketplace

Measured 2026-09-20, curl_cffi, no proxy, no login, exit IP Indonesia.

## Listings are server-rendered, whole

Unlike page posts and group posts, a Marketplace listing arrives as one object.
`GET /marketplace/<city>/<category>` returns ~840 KB with 21–24 listings inside
its embedded JSON:

```json
{"marketplace_listing_title": "2013 Subaru BRZ",
 "listing_price": {"formatted_amount": "$200,000", "amount": "200000.00"},
 "location": {"reverse_geocode": {"city": "Hayward", "state": "CA",
                                  "city_page": {"display_name": "Hayward, California"}}},
 "creation_time": 1789067301,
 "custom_sub_titles_with_rendering_flags": [{"subtitle": "50K miles"}],
 "delivery_types": ["IN_PERSON"], "is_sold": false,
 "marketplace_listing_seller": null}
```

So the parser finds any node owning `marketplace_listing_title` and reads the
object around it. No path walking, no id joins.

## The location trap

`/marketplace/109571519060768/vehicles` — a real Facebook location id — returns
**HTTP 200 with a full page of listings, every one of them in California**,
identical to a request with no location at all. `/marketplace/nyc/vehicles`
returns New York and New Jersey; `/marketplace/jakarta/vehicles` returns Jakarta
and West Java; `/marketplace/london/propertyrentals` returns London and Brent.

A numeric id is accepted and ignored. This is the worst class of failure on this
surface: the wrong answer arrives looking exactly like the right one. The actor
rejects numeric cities with a message instead of scraping them.

The paginated query shows why the slug is what matters —
`topicPageParams: {"location_id": "nyc", "url": "vehicles"}` is resolved server
side into `buyLocation: {"latitude": 40.7142, "longitude": -74.0064}`.

## Which URL parameters are honoured

Same feed, 24 listings each, prices compared:

| Parameter | Prices returned | Verdict |
| --- | --- | --- |
| none | $80 – $37,485 (median $3,500) | baseline |
| `minPrice=20000&maxPrice=40000` | $20,000 – $39,000 (median $26,073) | **honoured** |
| `sortBy=creation_time_descend` | $8 – $26,156 (median $4,875) | **honoured** (different set) |
| `daysSinceListed=1` | $80 – $37,485 (median $3,500) | **ignored** — identical to baseline |

`daysSinceListed` is not exposed by this actor. Recency is filtered locally
against `creation_time`, which Facebook does publish.

## Pagination

Two root queries and two pagination queries, chosen by whether the request is a
category feed or a search:

| Surface | Root query (id in the HTML) | Pagination query (id in the JS bundle) |
| --- | --- | --- |
| category | `CometMarketplaceCategoryContentContainerQuery` | `CometMarketplaceCategoryContentPaginationQuery` |
| search | `CometMarketplaceSearchRootQuery` | `CometMarketplaceSearchContentPaginationQuery` |

The root query's variables are published in the page's relay preloader block —
including `buyLocation`, `categoryIDArray`, `priceRange` and `radius` — so
pagination inherits the filters the first page was rendered with instead of
re-encoding them by hand. Measured: 24 rendered + 10 per GraphQL call.

**Cursor gotcha:** the category feed does not always put its cursor in a
`page_info` block. Each edge carries its own `cursor` string, so when no
`page_info` is found the last edge's cursor is used.

## The listing page adds what the feed never had

`/marketplace/item/<id>/` carries `redacted_description.text`, `condition`,
`location.latitude/longitude`, `reverse_geocode_detailed.postal_code_trimmed`,
`listing_price.currency`, and for vehicles `vehicle_make_display_name`,
`vehicle_model_display_name`, `vehicle_exterior_color` and so on.

**Gotcha:** that page also renders ~19 *related* listings in the same payload.
Reading the first node that happens to look like a listing describes somebody
else's item. The parser matches on the target id and nothing else.

## What is not public

`marketplace_listing_seller` is `null` on both the feed and the listing page for
a signed-out client. There is no alternative surface for it — the "message
seller" flow is authenticated. The actor emits `sellerName: null` rather than
dropping the field, so the absence shows up in the data.

## Cost shape

One HTTP request per ~24 listings (then ~10 per GraphQL page), plus one request
per listing when descriptions are wanted, plus a one-off bundle fetch the first
time pagination is needed in a session. No proxy, no browser.
