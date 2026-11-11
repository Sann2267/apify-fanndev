# Crawling Method — Google Maps Popular Times & Traffic Analytics

Reconnaissance performed 2026-09-16, HTTP-only, no browser, no login, no API key.

---

## Summary

| Question | Answer |
| --- | --- |
| Where does the data live? | `/maps/preview/place` only — **never** in `tbm=map` search results |
| Requests per venue | 1 search request per 20 venues, then **1 detail request per venue** |
| Residential proxy | **Required.** 0% coverage from a datacenter IP, 62.5% through residential |
| Typical coverage | ~60–75% of venues in a category have a curve; the rest genuinely have none |
| Live occupancy | Present on a minority of venues, and only while they are open |

---

## The data

`/maps/preview/place` carries a foot-traffic block shaped like:

```
[ [7, null, 1],                                        # day with no data
  [1, [[6, 0,  "",                     "", "6 am", null, "6a"],
       [7, 20, "Usually not too busy", "", "7 am", null, "6a"],
       ...], 0],
  ... ]
```

Each hour entry is `[hour24, occupancyPercent, label, "", displayHour, null, bucket]`.

Days are numbered **1 = Monday … 7 = Sunday**, verified two independent ways: the
sibling "current day" value was `3` on a Wednesday, and the only day carrying no
data was `7` for a gym whose opening hours show Sunday closed.

Beside the histogram, in its parent list:

```
[ container, currentDay, null, 1, currentHour, null, statusText, [hour, livePercent] ]
```

The final `[hour, livePercent]` pair is present **only** when Google has a real
live measurement.

### Live vs projection — a trap

Two different things look like live data:

* `"Now: Usually as busy as it gets"` — a **projection** from the weekly curve.
  No live measurement exists. Reporting this as live occupancy would be wrong.
* `"Busier than usual"` / `"Less busy than usual"` — a **real live reading**,
  always accompanied by the `[hour, livePercent]` pair.

The parser only sets `hasLiveData` for the second kind.

A neat independent confirmation that the parse is correct: for one gym the live
value was **80% against a usual 19% at 11:00**, and Google's own label for that
record was *"Busier than usual"* — the numeric comparison agrees with Google's
text, which it could not do by coincidence.

Also note `"Live music"` and `"Live performances"` appear in venue amenity tags
and match a naive search for "Live". They are not occupancy data.

### Never read this by slot index

The block sat at `d[6][84]` in the first captures, so an index-based reader is
tempting. It is wrong: Google moves the block between responses exactly as it
moves opening hours, and an index read silently reports "no popular times" for
venues that have it. This cost a full debugging cycle — a coverage sweep printed
`0/20` for three categories, which looked like "Google removed the data" and was
really the index having shifted. The parser matches on **shape** instead: a day
group is `[int 1-7, [hour entries] | null, ...]` where an hour entry is
`[0-23, 0-100, str, ..., str]`. That is also language-independent.

---

## The reduced-record problem — and why residential proxy is mandatory

Google serves two richnesses of place record and chooses by client. The
popular-times block is in the full one only. Measured:

| Egress | Popular-times coverage |
| --- | --- |
| Consumer ISP connection | 62.5% (5/8 venues, 4 with live readings) |
| **Apify platform, no proxy (datacenter IP)** | **0% (0/12)** |
| **Apify platform, `RESIDENTIAL`** | **62.5% (5/8), 4 with live readings** |
| Apify `GOOGLE_SERP` | unusable — cannot tunnel arbitrary HTTPS (CONNECT 400) |

This is the **opposite** of the sibling reviews and lead-generation actors, where
residential proxy caused consent interstitials and no-proxy was the right default.
The difference is what each actor needs: those need a page to load at all, which
a datacenter IP does fine; this one needs the *full* record, which a datacenter IP
never receives. Residential is therefore the default here, and the actor warns
loudly when it is switched off.

### Volume degradation

Separately from the datacenter/residential split, an IP that has made many recent
requests starts receiving reduced records too. Observed within one session:
early requests returned 165–190 KB records with popular times, later ones a stable
~30 KB with none. Cooldowns of 60 s, 3 s pacing and repeat requests for the same
feature id all failed to restore it; it recovered on its own some minutes later.

The actor therefore paces itself (`requestDelaySeconds`, default 1.5 s) and
watches for a long unbroken run of misses, reporting it explicitly instead of
emitting an empty dataset that looks like "these venues have no data".

---

## Coverage is genuinely partial

Even on a good IP, roughly a third of venues have no foot-traffic curve at all —
Google only publishes one where it has enough location history. Small independent
gyms and cafes frequently have none, larger chains usually do. `hasPopularTimes`
records which is which, and `onlyPlacesWithPopularTimes` controls whether the
empty ones reach the dataset.

Live occupancy is rarer still and only appears while a venue is open.

---

## Request cost

Unlike the lead-generation actor — where one search request yields 20 complete
leads — popular times is **not** in search results. Every venue costs its own
detail request, so a 200-venue run is ~210 requests. That, plus the pacing needed
to avoid degradation, is the actor's main cost driver.
