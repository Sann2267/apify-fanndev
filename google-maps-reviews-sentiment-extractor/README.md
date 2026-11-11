# Google Maps Reviews & Sentiment Extractor

> **Correction (2026-09-16):** the claim below that free-text place search is closed is **wrong**. The sibling actor `google-maps-lead-generation-scraper` searches Google Maps successfully; the `pb` used here was malformed (it omitted the `!7i20!10b1!12m6…` result-request tail, so Google returned search metadata with no result list). This actor still takes place identifiers only, but the limitation is a design choice, not a platform restriction.


Pull every public Google Maps review for a place — rating, date, reviewer, like
count, photos and the **owner's reply** — and get each one scored positive,
neutral or negative automatically. Export to JSON, CSV, Excel or NDJSON.

No login, no Google API key, no browser. Pure HTTP.

---

## What you get per review

| Field | Notes |
| --- | --- |
| `rating` | 1–5 stars |
| `text` / `textTranslated` | Original text plus Google's translation when it has one |
| `publishedAt` | Real UTC timestamp, not just "2 months ago" (`relativeTime` has that too) |
| `reviewer` | Name, profile URL, avatar, total reviews, total photos, Local Guide flag |
| `likesCount` | How many people found the review helpful |
| `ownerResponse` | The business reply — text and when it was posted |
| `photos` | Photos attached to the review |
| `attributes` | Google's structured answers, e.g. "When did you visit?" → "Weekday" |
| `sentiment` | `label`, `score` (−1…1), `method`, and `ratingTextConflict` |
| `permalink` | Direct link to that single review |

Each place also produces one **PLACE** summary row: sentiment counts and
percentages, average rating, rating histogram, owner-response rate, total likes,
and a count of rating/text conflicts.

---

## Input

Supply places as **Google Maps URLs, Place IDs, CIDs, or feature IDs**:

```json
{
  "placeUrls": [
    { "url": "https://www.google.com/maps/place/Eiffel+Tower/@48.8583701,2.2944813,17z/data=!4m6!3m5!1s0x47e66e2964e34e2d:0x8ddca9ee380ef7e0!8m2!3d48.8583701!4d2.2944813" },
    { "url": "https://www.google.com/maps?cid=3292831917685799941" },
    { "url": "https://maps.app.goo.gl/xxxxxxxx" }
  ],
  "placeIds": ["ChIJrTLr-GyuEmsRBfy61i59si0", "0x6b12ae37b47f5b37:0x8eaddfcd1b32ca52"],
  "mode": "reviews",
  "sortBy": "newest",
  "maxReviewsPerPlace": 300,
  "exportFormats": ["csv", "excel"]
}
```

> **A free-text search query is not accepted.** Google closed every HTTP-only
> place-search surface, so this actor works from place identifiers. Paste the URL
> from your browser's address bar and you are done. See
> [Limitations](#limitations-read-before-buying).

### Modes

| Mode | Emits | Use it for |
| --- | --- | --- |
| `reviews` *(default)* | Every review + a PLACE summary | Full extraction and analysis |
| `summary_only` | PLACE summary only, one page fetched | Cheap sentiment snapshot across many places |
| `owner_responses` | Only reviews the business replied to | Auditing reply rate and reply quality |

### Useful options

| Option | Default | Notes |
| --- | --- | --- |
| `sortBy` | `newest` | `newest` is the only order that reliably walks the whole list. `relevant` returns a mixed-rating sample. |
| `maxReviewsPerPlace` | 100 | Google serves 60 on page 1, then 20 per page. |
| `minRating` / `maxRating` | — | Set both to 1 and 2 to isolate complaints. |
| `onlyWithOwnerResponse` | `false` | Same filter as `owner_responses` mode. |
| `language` / `region` | `en` / `US` | `hl` and `gl`. Also picks the translation target language. |
| `exportFormats` | `[]` | `json`, `csv`, `excel`, `ndjson` → written to the key-value store. |

---

## How the sentiment scoring works

Each review is scored by blending **VADER** text polarity with the **star
rating**, because neither alone is reliable:

* the rating is coarse — 3-star reviews are often strongly opinionated, and
  5-star reviews frequently contain real complaints;
* the text lexicon has no opinion at all on rating-only reviews, which are a
  large share of Google Maps data.

The default blend is 60% text / 40% rating, and `method` records which signals a
given row actually used:

| `method` | Meaning |
| --- | --- |
| `text+rating` | English review text blended with the rating |
| `translated+rating` | Non-English review, scored via Google's English translation |
| `rating-only` | No text, or a language with no translation available |
| `none` | Neither text nor rating — scored neutral, never dropped |

**Sarcasm handling.** A lexicon cannot detect sarcasm: *"Highly thrilling
experience 😡"* on a 1-star cancellation complaint scores **+0.94** on text
alone. When a confident text polarity contradicts an extreme rating (1, 2 or 5
stars), the rating is weighted to 75% — the reviewer's own star verdict is the
better ground truth for satisfaction. That review correctly lands at **−0.54,
negative**. Those rows are flagged with `sentiment.ratingTextConflict: true`, and
counted per place as `ratingTextConflicts` — they are usually the most
interesting reviews in the set, so they are surfaced rather than just corrected.

Scoring runs inside the actor: no API key, no per-review cost, no data sent
anywhere.

---

## Limitations (read before buying)

These are properties of what Google still exposes publicly, verified rather than
assumed. Full evidence in [CRAWLING_METHOD.md](CRAWLING_METHOD.md).

1. **No free-text place search.** Google's Maps search is JS-only for
   non-browser clients and every legacy search endpoint now 404s. Supply place
   identifiers. Unrecognised input gets a clear error, never a wrong place.
2. **Place name and coordinates come from your URL, not from Google.** Google's
   resolver returns `null` for the name and the same default world-view viewport
   for every place. Paste a full `/maps/place/<Name>/...` URL and both are
   captured; supply a bare Place ID and both are `null`.
3. **Geographic filters filter, they do not discover.** Because of (1) and (2),
   `boundingBox` / `radiusKm` / `areaName` narrow the places *you* supply to
   those inside an area — they cannot find new places in it. A place with no
   coordinates is kept with a warning by default, or skipped with a `SKIPPED`
   record if you set `onMissingCoordinates: "skip"`. Nothing is dropped silently.
4. **Reviews per place are finite.** Google stops serving pages well before the
   lifetime review count of large places; the actor stops when the cursor runs
   out and reports how many it got.
5. **`averageRating` is the average of what was scraped**, not Google's lifetime
   average for the business.
6. **Sentiment is English-centric.** Non-English reviews are scored through
   Google's translation where available, and fall back to rating-only otherwise.
   `method` always tells you which happened.

---

## Anti-bot and proxy

Reconnaissance found **no WAF** on this endpoint: ten TLS fingerprints across
five Google country hosts all returned 200 from a plain residential connection.

**Do not use residential proxy here.** This is the opposite of the usual advice
and it was measured, not assumed:

| Egress | Result |
| --- | --- |
| Plain home ISP, no proxy | works |
| Apify platform, no proxy *(the default)* | works — 42 records in 7s |
| Apify platform, `RESIDENTIAL` | **fails** — Google answers the place resolver with an interstitial instead of the page |

Google polices residential proxy pools far harder than datacenter ranges,
because those IPs are widely abused. Since these endpoints have no WAF, the
residential IP buys nothing and costs you the run.

**The proxy is therefore off by default** and the actor runs on the platform's
own IP. Enable one only to spread load across IPs at high volume, and leave the
group list empty so Apify picks a group your plan actually has — naming a group
your account lacks (a free plan has no `DATACENTER`) fails the run at input
validation before it starts:

```json
{ "proxyConfiguration": { "useApifyProxy": true } }
```

The client impersonates Chrome 150 via `curl_cffi`, warms the Maps cookie jar
once per session, retries with exponential backoff, and rotates TLS profile and
cookie jar on 403/429/503.

---

## Output shape

Records follow the portfolio envelope — `_input`, `_source`, `_scrapedAt`,
`recordType` — with `_error` / `_errorDetail` on failures and `_warning` on
skips. Split a run by `recordType`: `PLACE`, `REVIEW`, `SKIPPED`, `ERROR`.

A place that fails to resolve produces an `ERROR` row rather than vanishing, so
you can always reconcile inputs against outputs.

---

## Development

```bash
pip install -r requirements.txt
python test_errors.py     # offline checks: parsing, geo, sentiment, exporters
python test_local.py      # live end-to-end run against Google
```

`test_local.py` reads `_input.json` when present, otherwise uses its built-in
default input.
