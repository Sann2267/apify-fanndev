# Google Maps Popular Times & Traffic Analytics

Collect Google Maps **Popular Times** foot-traffic curves in bulk — hour-by-hour
busyness for every day of the week, plus **live occupancy** where Google has it —
for whole categories of venue across a city.

Built for urban researchers, retail site-selection and investment analysts, and
competitive operations research: the data you can read one venue at a time in the
Google Maps UI, as a dataset you can actually analyse.

No login, no Google API key, no browser.

---

## What you get per venue

| Field | Notes |
| --- | --- |
| `popularTimes` | Seven days, each with an hourly curve: `{hour, occupancyPercent, label, displayHour}` |
| `busiestDay`, `busiestHour`, `peakOccupancyPercent` | Weekly peak, precomputed |
| `averageOccupancyPercent` | Mean across every reported hour |
| `liveOccupancyPercent`, `liveStatusText`, `hasLiveData` | Current busyness, when Google has a live reading |
| `currentDay`, `currentHour` | Scrape time in the venue's own timezone |
| `name`, `primaryCategory`, `address` | Venue identity |
| `latitude`, `longitude`, `timezone` | Real GPS coordinates; timezone is needed to read the curve locally |
| `rating`, `reviewsCount` | Rough proxy for venue size |
| `placeId`, `featureId`, `googleMapsUrl` | Stable identifiers |

Occupancy is Google's own 0–100 scale, where 100 is that venue's weekly peak —
**not** a headcount, and not comparable in absolute terms between venues.

---

## Wide vs long output

This matters more than it sounds:

* **`wide`** — one row per venue, the whole weekly curve nested inside it. Good
  for JSON consumers and for scanning venues.
* **`long`** — one row per **venue × day × hour**. This is the analysis-ready
  shape: open the CSV in a spreadsheet or `pandas` and you can group by hour
  across every gym in a city without unpacking anything.

A venue with a full week produces ~100–126 long rows.

```json
{
  "searchQueries": ["gym"],
  "areaName": "jakarta",
  "maxPlacesPerQuery": 100,
  "outputFormat": "long",
  "exportFormats": ["csv"]
}
```

Locations work the same way as the sibling Maps actors: `areaName`, or a centre
point with `radiusKm`, or an exact `boundingBox` (tiled for coverage, then
filtered using each venue's real coordinates). You can also pass `placeUrls` /
`placeIds` to track specific venues instead of searching.

---

## Why some runs return little data

Two separate effects, both measured rather than assumed. Read this before
concluding the actor is broken.

### 1. Residential proxy is required (on by default)

Google serves two richnesses of place record and picks by client. The
popular-times block is in the full one only:

| Egress | Coverage |
| --- | --- |
| Apify platform, no proxy | **0%** |
| Apify platform, `RESIDENTIAL` *(the default)* | **62.5%**, with live readings |

A datacenter IP gets the block stripped out entirely. **Leave the residential
proxy on**; the run warns you if you turn it off. `GOOGLE_SERP` cannot be used —
it does not tunnel arbitrary HTTPS.

This is deliberately the opposite of the sibling Google Maps reviews and
lead-generation actors, which run best with **no** proxy. Those only need a page
to load; this one needs the full record.

### 2. Coverage is genuinely partial anyway

Roughly a third of venues have no foot-traffic curve at all — Google only
publishes one where it has enough location history. Small independent venues
often have none; chains and busy venues usually do. `hasPopularTimes` tells you
which, and `onlyPlacesWithPopularTimes` decides whether empty ones are recorded.

Live occupancy is rarer still and only appears while a venue is open.

### 3. Heavy runs degrade their own IP

An IP that has made many recent requests starts receiving reduced records too.
The actor paces itself (`requestDelaySeconds`, default 1.5 s) and warns when many
venues in a row come back empty, rather than handing you an empty dataset that
looks like "no venue has data". For large runs raise the delay; if a run comes
back mostly empty, wait and re-run.

---

## Live occupancy: read the flag, not the text

Google shows two things that both look live:

* `"Now: Usually as busy as it gets"` — a **projection** from the weekly curve.
  No live measurement exists.
* `"Busier than usual"` / `"Less busy than usual"` — a **real** live reading.

Only the second sets `hasLiveData: true` and populates `liveOccupancyPercent`.
Filter on `hasLiveData`, never on the presence of `liveStatusText`.

---

## Cost

Popular times is **not** in search results — every venue needs its own request.
A 200-venue run is roughly 210 requests plus pacing. Budget accordingly, and use
`maxPlacesPerQuery` to keep runs bounded.

---

## Output shape

Records follow the portfolio envelope — `_input`, `_source`, `_scrapedAt`,
`recordType` — with `_error` / `_errorDetail` on failures. `recordType` is
`PLACE` in wide format, `POPULAR_TIMES_HOUR` in long format, or `ERROR`.

Three Console views ship with the actor: **Overview**, **Weekly curves (wide)**
and **Hourly rows (long)**.

---

## Development

```bash
pip install -r requirements.txt
python test_errors.py     # offline: parsing, live detection, long format, exporters
python test_local.py      # live end-to-end run
```

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the endpoint reconnaissance, the
day-numbering proof, and why this block must never be read by slot index.
