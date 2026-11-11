# Google Maps Business Verification & Status Monitoring

Find neglected Google Business Profiles in any area — **unclaimed listings**,
businesses with **no website** or no phone, thin profiles, and closed locations —
each scored as a Google Business Profile sales opportunity.

Built for local SEO agencies prospecting claim-and-optimise clients: instead of
checking listings one at a time in Maps, sweep a whole category across a city and
get a ranked call list.

No login, no Google API key, no browser.

---

## What it tells you per business

| Field | Notes |
| --- | --- |
| **`claimStatus`** / `isUnclaimed` | `unclaimed` means nobody has taken the profile — your core pitch |
| **`businessStatus`** | `operational`, `temporarily_closed`, `permanently_closed` (see the limit below) |
| `hasWebsite`, `hasPhone`, `hasOpeningHours` | The profile gaps you would fix |
| `reviewsCount`, `rating` | Thin review counts signal a neglected listing |
| **`opportunityScore`** | 0–100, weighted for GMB sales value |
| **`opportunityIssues`** | The specific problems, e.g. `["unclaimed","no_website","no_phone"]` |
| `name`, `primaryCategory`, `address`, `phone`, `website` | Contact details for the outreach itself |
| `latitude`, `longitude`, `placeId`, `googleMapsUrl` | Location and stable identifiers |

Plus one **`AREA_SUMMARY`** row per run — the market-level pitch: how many
listings in this area are unclaimed, how many lack a website, and how many are
both.

---

## Quick start

```json
{
  "searchQueries": ["warung", "salon", "laundry"],
  "areaName": "jakarta",
  "maxResultsPerQuery": 200,
  "onlyUnclaimed": true,
  "exportFormats": ["csv"]
}
```

Real output from a 20-result sweep of `warung` in Jakarta: **15 unclaimed (75%),
17 without a website, 15 with both**, top prospect scoring 75.

### It actually discriminates

The same run against other categories, which is how you know the signal is real
rather than a constant:

| Category | Unclaimed |
| --- | --- |
| `warung` (small local eateries) | **15/20** |
| `internet cafe` | 7/20 |
| `salon` | 1/20 |
| `dentist` | **1/20** |

Professional practices are almost always claimed; informal micro-businesses are
almost never. Point the actor at the second group.

### Building a call list

`onlyUnclaimed`, `onlyWithoutWebsite`, `onlyWithoutPhone` and
`minOpportunityScore` narrow the sweep to businesses worth a call. They combine,
so `onlyUnclaimed + onlyWithoutWebsite` gives you the strongest prospects only —
and legitimately returns nothing for a well-managed category.

`minOpportunityScore: 65` is a good starting threshold.

### Locations

`areaName` for a built-in city or country, or a centre point with `radiusKm`, or
an exact `boundingBox`. Areas are tiled into multiple search points and then
filtered against your exact area using each business's real coordinates.

---

## How the score works

| Signal | Points |
| --- | --- |
| Unclaimed listing | 40 |
| No website | 25 |
| No phone | 10 |
| No opening hours | 10 |
| Fewer than 5 reviews | 10 |
| Rating below 4.0 | 5 |

A **permanently closed** listing is forced to **0** however neglected it looks —
a dead business is not a prospect and should never sit at the top of your call
list. It still appears with `businessStatus: permanently_closed` so you can see
why.

---

## Limits worth knowing

1. **Closed businesses are hard to discover.** Google appears to exclude
   permanently closed listings from search results — across nine queries in two
   countries, including chains known to be defunct (7-Eleven Indonesia, Toys R
   Us, Blockbuster), not one closed listing came back. Closure is therefore
   reported reliably only for businesses you supply directly via `placeUrls` /
   `placeIds`, or when `verifyWithPlaceDetails` is on. Use this actor to *monitor*
   known businesses for closure, not to *discover* closed ones.
2. **`verifyWithPlaceDetails` costs one extra request per business.** Leave it
   off for large sweeps; turn it on for a shortlist you are about to call.
3. **Claim status reflects what Google exposes publicly.** It is derived from the
   presence of Google's own "Own this business?" action, which is the same signal
   a human sees in Maps.
4. **Category names follow `language`.** Keep `language: "en"` unless you need
   local category names — the closure wording matched is English.

---

## Cost and proxy

Every signal except closure rides in the search response, so a sweep costs **one
request per twenty businesses** — the cheapest actor in this Maps family.

Proxy is **off by default** and that is correct here: the claim signal survives
even the reduced record Google serves datacenter IPs, so the platform's own IP
loses nothing. Residential is not recommended for Google — it draws consent and
CAPTCHA interstitials.

---

## Output shape

Portfolio envelope — `_input`, `_source`, `_scrapedAt`, `recordType` — with
`_error` / `_errorDetail` on failures. `recordType` is `BUSINESS`,
`AREA_SUMMARY` or `ERROR`. Three Console views ship with the actor: **Overview**,
**Sales prospects** and **Status & verification**.

---

## Development

```bash
pip install -r requirements.txt
python test_errors.py     # offline: claim detection, closure logic, scoring, filters
python test_local.py      # live end-to-end run
```

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the reconnaissance, the
category-by-category validation of the claim signal, and the "every record
contains the word closed" trap.
