# Traveloka Flight Price Tracker

Tracks what a route actually costs on Traveloka across dates, so you can see
where the cheap days are and get told when a fare drops.

Two fare surfaces per route, both read straight from Traveloka's JSON API:

- **12-month cheapest curve** — the lowest fare in each of the next twelve
  months. One request per route, and the clearest read on seasonality.
- **Departure-by-return date grid** — the cheapest fare for every departure and
  return date pair in the windows you choose, up to ~100 quotes per request.

## Price alerts

Set `priceThreshold` and every route record carries
`summary.belowThreshold: true` when its lowest fare falls to or below your
number. Point an Apify webhook at the run and filter on that field to push into
Slack, Telegram or anything else. `summary` also gives you `lowestFare`,
`cheapestMonth`, and the exact `cheapestDepartDate` / `cheapestReturnDate`.

Schedule the actor daily and the dataset becomes a fare history you can diff.

## Input

Routes are `ORIGIN-DESTINATION`. IATA codes resolve fastest (`CGK-DPS`) but city
names work too (`Jakarta-Denpasar`) — anything unresolvable is reported as
`NOT_FOUND` rather than silently dropped. `-`, `->`, `>` and the word `to` are all
accepted as separators.

Set the departure and return windows, cabin class, passenger mix and currency.
Everything else has a sensible default.

## What this actor cannot do, and why

**It reports fares, not individual flights.** There is no airline name, departure
time, aircraft or transit duration in the output. Traveloka's itinerary search
(`/v2/flight/search/initial` and the streaming feed behind it) is protected by AWS
WAF with the `captcha` action — a visual challenge no headless client can answer.
This was verified from clean residential Indonesian IPs as well as datacenter
IPs, on the first request of a fresh session with a valid WAF challenge token.
Proxies do not change it, so the actor sticks to the price-discovery endpoints,
which are not gated.

If you need schedules and airlines rather than prices, this is not the tool.

## The 100-cell trap

`departWindowDays × returnWindowDays` is capped at 100 date pairs per request by
Traveloka. Past that the API does not error — it returns **zero fares**, which
reads exactly like "this route has no flights". The actor splits oversized grids
into compliant blocks automatically, so you can ask for a 30-day window without
thinking about it.

A related quirk: a return date cannot precede its departure date, so a grid whose
return window sits before the departure window legitimately comes back nearly
empty.

## Output record types

- `ROUTE` — fares collected.
- `NOT_FOUND` — origin or destination could not be resolved to an airport.
- `NO_FARES` — the route resolved but Traveloka quoted nothing in the window.
- `ERROR` — a request failed; see `error`.

Anything that partly failed still returns, with the reason in `warnings`.

## Cost

One request to resolve each endpoint of a route (skipped when you pass IATA
codes), one for the monthly curve, and one per grid block. A typical route with a
10×10 grid is four requests.

Traveloka's fare APIs answer datacenter IPs normally, so the default Apify proxy
is fine. Residential Indonesian proxies do not unlock anything extra.

## A note on robots.txt

Traveloka's `robots.txt` disallows `/api/`, which is where this actor reads from.
Decide for yourself whether that fits your use of the data, your jurisdiction and
your agreement with Traveloka. Keep request rates modest and scrape only what you
need.
