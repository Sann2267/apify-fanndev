# Traveloka Ground Transport (Bus & Shuttle) Monitor

Intercity bus and shuttle departures from Traveloka as structured JSON — the
Southeast Asian ground-transport market that global scrapers tend to skip.

Give it a city pair and a date range; get every departure with operator, fare,
times, seats left and boarding points with coordinates.

## What you get

**Per departure** (`recordType: DEPARTURE`):

| Group | Fields |
| --- | --- |
| Operator | `operatorName`, `operatorId`, `fleetName`, `busType`, `productType` (BUS or SHUTTLE), `operatorRating`, `operatorReviewCount` |
| Fare | `fare`, `originalFare`, `discountPercent`, `childFare`, `infantFare`, `promoLabel`, `currency` |
| Schedule | `departureDate`, `departureTime`, `arrivalDate`, `arrivalTime`, `durationMinutes`, `timeZone` |
| Capacity | `seatCapacity`, `seatsAvailable`, `seatClass`, `seatLayout`, `availabilityStatus` |
| Boarding | `pickupPointName` + address + city + **latitude/longitude**, and the same for drop-off |
| Comfort | `facilities` (air conditioning, USB power, reclining seats, …) |

**Per route and date** (`recordType: ROUTE_SUMMARY`): `minFare`, `maxFare`,
`averageFare`, `operatorCount`, `totalSeatsAvailable`, `departuresOnPromo`, and
an `operators[]` breakdown with each operator's departure count, fare range and
rating. That one row is usually all a pricing analyst needs.

`originalFare` with `discountPercent` is the genuine promo signal: it only
appears when the operator is discounting off a published fare.

## The de-duplication that matters

Traveloka expands **every pickup point by every drop-off point**. A single
Jakarta–Bandung day returns around **9,500 inventory rows** and roughly 38 MB of
JSON, mostly the same physical departures repeated per boarding location.

`dedupeBy` handles this:

- **`trip`** (default) — one row per physical departure. This is what you want.
- **`none`** — every boarding option, if you are mapping pickup coverage.
- **`operator`** — one row per operator, time and class.

`maxDeparturesPerSearch` caps what is kept per route per date; the default of 200
comfortably covers a busy corridor after trip de-duplication.

## Routes

Write routes as `Jakarta-Bandung`. City names resolve to Traveloka's city codes,
which cover every terminal in that city — better for monitoring than pinning one
terminal. Terminal and landmark names work too if you want a specific boarding
point. Anything unresolvable is reported as `NOT_FOUND` rather than dropped.

Set `daysToMonitor` to sweep consecutive travel dates; one search per route per
day. Schedule the actor daily and the dataset becomes a fare and capacity history.

## What this actor does not cover

**Train is not included.** Traveloka's train inventory endpoint
(`/v2/train/search/inventoryv2`, domain `train`) is reachable and answers HTTP
200, but it returns "Kereta Tidak Tersedia" for every route, date, station-or-city
code and provider (`KAI` and `KCIC`) tested on 2026-09-20 — including Jakarta–
Yogyakarta, which plainly has daily service. Rather than ship a train mode that
silently returns nothing, the endpoint and its exact payload are documented in
`src/constants.py` so it can be switched on if Traveloka opens it.

One detail recorded there because it is easy to lose: the train API's date object
uses `date`, not `day` — the opposite of every other Traveloka endpoint.

**Airport transfer is not included** either; it uses a different search contract
(`/v2/pps/search/multileg`) built around location objects rather than city codes.

## Cost

One autocomplete lookup per distinct place name (cached across dates), then one
search per route per date. Bus responses are large, so the default delay between
requests is 0.6 seconds; raise it for long sweeps.

The bus API answers datacenter IPs normally, so the default Apify proxy is fine.

## Output record types

- `DEPARTURE` — one trip.
- `ROUTE_SUMMARY` — fares and operators for one route on one date.
- `NO_SERVICE` — Traveloka has no bus matching that route and date.
- `NOT_FOUND` — a place name could not be resolved.
- `GATED` — an endpoint answered with an AWS WAF challenge.
- `ERROR` — a request failed; see `error`.

## A note on robots.txt

Traveloka's `robots.txt` disallows `/api/`, which is where this actor reads from.
Decide for yourself whether that fits your use of the data, your jurisdiction and
your agreement with Traveloka. Keep request rates modest and scrape only what you
need.
