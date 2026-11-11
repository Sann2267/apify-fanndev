# Crawling Method — Google Maps Lead Generation & Contact Scraper

Reconnaissance performed 2026-09-16, HTTP-only, no browser, no login, no API key.

---

## Summary

| Question | Answer |
| --- | --- |
| WAF? | **None.** Ten TLS profiles all returned 200 from a plain ISP connection. |
| Residential proxy? | **No — actively harmful.** See "Proxy posture". |
| Search | `GET /search?tbm=map&pb=…&q=…` — 20 results/page, `!8i` offset pagination |
| Place details | `GET /maps/preview/place?pb=…` |
| Key finding | Search entries and place details share **one schema** — a search page yields 20 complete leads |

---

## Correction to a previous conclusion

The sibling reviews actor documents free-text place search as closed. **That was
wrong**, and this recon disproves it. The earlier `pb` was simply malformed: it
carried the viewport block but not the `!7i20!10b1!12m6…` result-request tail, so
Google answered with search *metadata* (a result count and a location chip) and
no result list — which looked like a refusal but was a well-formed answer to a
request that never asked for results.

Working search, verified:

```
GET https://www.google.com/search
    ?tbm=map&authuser=0&hl=en&gl=ID&q=dentist
    &pb=!4m12!1m3!1d20000!2d106.8094!3d-6.2245!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1
        !7i20!8i0!10b1!12m6!1m1!18b1!2m1!20e3!6m1!114b1!17m1!3e1!20m57!…
-> 200, ~162 KB, 20 businesses with full contact data
```

The viewport block is the geographic control surface: `!1d` is a span in metres,
`!2d` longitude, `!3d` latitude. Changing `!1d` demonstrably changes the result
set (1 km, 5 km, 20 km and 100 km around the same point return different
businesses), which is what makes genuine area targeting possible.

Pagination: `!8i{offset}` in steps of 20. Verified 140 unique businesses across
7 pages with **zero duplicates**.

---

## One schema, two surfaces

A `tbm=map` entry at `response[0][1][i][14]` and a `/maps/preview/place` record
at `response[6]` are the same positional shape:

| Slot | Field |
| --- | --- |
| 2 | address components |
| 4 | `[.., [reviews_url, "826 reviews", ..], .., rating, review_count]` |
| 7 | `[website_url, display_domain, ..]` |
| 9 | `[null, null, latitude, longitude]` — **real GPS coordinates** |
| 10 | feature id |
| 11 | business name |
| 13 | categories |
| 30 | IANA timezone |
| 39 | formatted address |
| 78 | Place ID (`ChIJ…`) |
| 178 | `[pretty_phone, [[local,1],[intl,2]], null, e164, ..]` |
| 203 | opening hours *(see the warning below)* |

This is the single most valuable property of the target: **one request returns
20 complete leads**, so a lead-gen run costs one request per 20 businesses
rather than one per business.

---

## Two parsing traps that produce silently wrong data

Both were caught only because the output was checked field-by-field against live
data rather than trusted because the run exited 0.

### 1. A whole-number rating is an `int`, not a `float`

`[null ×7, 4.9, 546]` but also `[null ×7, 5]`. A parser that sniffs
`isinstance(value, float)` to find the rating silently drops every 5.0-star
business, and one that treats "the int" as the review count reads the *rating*
as a count. Read this block **positionally**: rating at `[7]`, count at `[8]`,
reviews URL inside `[3]`.

### 2. Opening hours are not always at slot 203

For the same business, one response carries the weekly schedule at slot 203 and
another carries nothing there. A fixed-slot read returned a 1-day schedule for
33 of 40 leads and nothing at all from half the detail calls.

The fix is to locate the schedule **structurally** rather than by index: a day
entry is a list shaped `[str, int, [year, month, day], [[text, …]], …]`. Matching
on the date triple is also language-independent, so it survives a non-English
`hl`. After this change: **40/40 leads with all 7 days**, and the review count and
reviews URL went from 0/40 to 40/40 in the same run.

Google varies how much of a record it sends between otherwise identical
requests, so a parser here must tolerate both the rich and the reduced shape.

---

## Enrichment

Google never exposes an email address, so the outreach value comes from the
business's own website.

* Emails and social handles are extracted from the homepage.
* When the homepage has no email, **one** same-domain contact/about link is
  followed. One hop only — this is enrichment, not a crawl.
* **Share widgets are not accounts.** Nearly every site embeds a Facebook share
  button and a Twitter intent link, so a naive regex reports that every business
  has a Facebook page called `sharer` and a Twitter account called `share`.
  Known widget paths are filtered out; verified zero widget noise in output.
* Image sprites like `logo@2x.png` match a naive email regex and are rejected.

Observed on a 40-lead Jakarta run: 24 had a website, 12 yielded an email, 17
yielded social accounts. Failures (dead domains, TLS errors, 403s) are recorded
per lead in `enrichmentStatus` rather than thrown, so a lead always reaches the
dataset with its Maps data intact.

---

## Proxy posture

Measured on the Apify platform for the sibling reviews actor, same endpoints:

| Egress | Result |
| --- | --- |
| Plain ISP, no proxy | works |
| Apify platform, no proxy | works |
| Apify `RESIDENTIAL` | **fails** — Google answers with a consent/CAPTCHA interstitial |

Google polices residential proxy pools far harder than datacenter ranges because
those IPs are widely abused. With no WAF to defeat, a residential IP buys nothing
and costs the run. The proxy is therefore **off by default**.

Also: a free Apify plan has no `DATACENTER` group at all, so the actor never
hardcodes a group — naming one the account lacks fails the run at input
validation before it starts.

Both `CONSENT=YES+1` and `SOCS` cookies are pre-set; `CONSENT` alone is no longer
sufficient on current Google.

---

## Google serves two record richnesses, chosen by client

The same request returns either a full record (7-day schedule, review counts) or
a reduced one (today's hours only, no counts). This is decided by the client/IP,
not by the `pb`:

* From a plain ISP connection: full records, 40/40 leads with all seven days.
* From the Apify platform (datacenter IP): reduced records, on **both** the
  search and the place-detail surface.

`fetchPlaceDetails` recovers review counts, review URLs and descriptions from the
detail endpoint (verified 15/15 on the platform) but usually **cannot** recover
the weekly schedule there — 1/15 completed. Leads therefore carry
`openingHoursComplete` so a partial schedule is visible rather than implied.

This is worth remembering before assuming a parser bug: identical code returned
40/40 full weeks locally and 1/15 on the platform.

---

## Known limits

* **Results per query are finite.** Google stops serving pages well before the
  true number of businesses in a large area. Coverage of a city comes from
  tiling it into multiple search centres, not from paging one search forever.
* **Full weekly opening hours are usually unavailable from a datacenter IP.**
  See the section above.
* **Plus codes** are not present in search records; the field is emitted as null
  rather than faked.
* **Category names and hours wording follow `hl`.** Set `language`/`region` to
  the market you are targeting.
