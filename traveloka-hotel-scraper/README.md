# Traveloka Hotel & Accommodation Scraper

Pulls hotels, villas and apartments from Traveloka as structured JSON: the full
property profile, room inventory, and **a whole month of nightly rates per
property** with an automatic weekday-versus-weekend comparison.

It talks to Traveloka's own JSON API rather than rendering pages in a browser, so
a property costs a handful of HTTP requests instead of a headless Chrome session.

## What you get per property

| Group | Fields |
| --- | --- |
| Identity | `hotelId`, `name`, `displayName`, `url`, `accommodationType` (Hotel / Villa / Apartment), `starRating` |
| Location | `address`, `city`, `province`, `country`, `postalCode`, `latitude`, `longitude`, `areaName`, `areaGeoId` |
| Property | `checkInTime`, `checkOutTime`, `facilityCodes` + `facilityNames` (100+ per property), `supportedRateTypes`, `images` |
| Rooms | `rooms[]` — name, description, bedding, room size, occupancy, view, smoking policy, amenities, photos |
| Pricing | `priceCalendar[]` — one entry per night: `date`, `dayOfWeek`, `isWeekendNight`, `price`, `availabilityStatus`, `isCheapestOfMonth` |
| Pricing summary | `priceSummary` — `minPrice`/`maxPrice` with their dates, `averagePrice`, `weekdayAveragePrice`, `weekendAveragePrice`, `weekendPremiumPercent`, `nightsUnavailable` |
| Reviews | `reviewSummary` — `rating`, `ratingScale`, `reviewCount`, `ratingLabel` |

`weekendPremiumPercent` is the number most revenue managers actually want: how
much more a competitor charges for a Friday or Saturday night than for a weekday.

## Choosing properties

Four ways in, and you can mix them:

- **Property URLs** — paste Traveloka hotel pages. Only the numeric ID at the end
  of the URL matters, so shortened or re-slugged links still work.
- **Property IDs** — bare numeric IDs from an earlier run.
- **Property name searches** — matches **property names**, not cities. `Kempinski
  Jakarta` returns that hotel; `hotels in Jakarta` returns nothing useful. This is
  the right tool for assembling a named competitor set.
- **Sitemap sweep** — samples property IDs from Traveloka's public sitemaps for
  broad market analysis. Use `sitemapSkipLeaves` so repeat runs sample different
  properties instead of the same first page.

## What this actor cannot do, and why

**There is no "every hotel in city X, with prices" mode.** Traveloka's search-list
endpoint, and the dynamic per-room rate endpoint behind it, are protected by AWS
WAF with the `captcha` action — a visual challenge that no headless client can
answer. This was verified from clean residential Indonesian IPs as well as from
datacenter IPs, on the first request of a fresh session with a valid WAF
challenge token: the answer is `captcha` every time. It is a structural rule, not
an IP-reputation problem, so proxies do not change it.

What that rules out, concretely:

- listing all properties in a city or around a map area;
- per-room nightly rates and per-room discount/strikethrough prices.

What replaces it: the **price calendar**, which is not WAF-guarded and returns the
property's nightly lead-in rate for every date in a month. For tracking a
competitor set's pricing over time this is strictly more useful than a single
search snapshot — one request gives you 31 data points instead of one.

`starRating` is the official star classification. `reviewSummary.rating` is the
guest score out of 10. `availabilityStatus` of `NO_ALLOTMENT` means sold out for
that date, which is itself a useful demand signal.

## Cost and tuning

Requests per property: 1 profile + 1 review summary + 1 room list + 1 per calendar
month. A 12-month pull is 15 requests. Turn off `includeRooms` or
`includeReviewSummary` for leaner runs, and keep `calendarMonths` at 1 unless you
need the forward curve.

Traveloka's JSON API answers datacenter IPs normally, so the default Apify proxy
is fine. Residential Indonesian proxies do **not** unlock anything extra here.

## Output record types

Every record carries a `recordType` so failures are visible rather than silent:

- `PROPERTY` — scraped successfully.
- `NOT_FOUND` — the ID does not exist. Traveloka does not 404 for these; it echoes
  the ID back with every other field null, which this actor detects.
- `GATED` — an endpoint answered with an AWS WAF challenge.
- `ERROR` — a request failed; see `error`.

Partial failures do not lose the record: anything that could not be fetched is
listed in `warnings` and the rest of the property is still returned.

## A note on robots.txt

Traveloka's `robots.txt` disallows `/api/`, which is where this actor reads from.
It allows `/*/sitemap/**`, which is what the sitemap sweep uses. Decide for
yourself whether that fits your use of the data, your jurisdiction and your
agreement with Traveloka. Keep request rates modest and scrape only what you need.
