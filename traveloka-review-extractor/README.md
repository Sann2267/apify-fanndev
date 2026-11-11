# Traveloka Review & Sentiment Extractor

Give it a Traveloka URL, get back every review as structured JSON — ready to pipe
straight into sentiment analysis, a reputation dashboard, or a spreadsheet.

Works across Traveloka's product families from the same input box: hotels,
Xperience activities, bus operators, airport transfers and car rentals. The
product is detected from the URL path, so you can mix them in one run.

## What you get

**Per review** (`recordType: REVIEW`):

| Field | Notes |
| --- | --- |
| `text` | Review in your chosen locale |
| `originalText` | What the guest actually typed, before machine translation |
| `isMachineTranslated` | True when `text` came from Google Translate, not the guest |
| `score`, `scoreScale` | Guest score, normally out of 10 |
| `reviewedAt` | ISO-8601 UTC, parsed from Traveloka's millisecond timestamp |
| `reviewerName`, `reviewerStatus` | Partly masked by Traveloka; `ANONYMOUS` is common |
| `photoUrls`, `videoUrls`, `mediaCount` | Full-size guest media |
| `subRatings` | Per-aspect scores when the reviewer gave them |
| `helpfulCount` | How many people marked it helpful |
| `propertyReplyText` | The operator's public reply, when there is one |

Keeping `originalText` separate from `text` matters for NLP: scoring a machine
translation measures the translator as much as the guest.

**Per object** (`recordType: OBJECT_SUMMARY`), one row holding `objectName`,
`rating`, `ratingLabel`, `totalReviewCount`, `reviewsCollected`, and `ratingTags`
— Traveloka's aspect tags with counts, split into `positiveTagIds` and
`negativeTagIds`, which is the closest thing to sentiment the platform publishes
itself. Filter the dataset on `recordType` to separate the two shapes.

## Filtering and sorting

- **Sort** newest first, most helpful, or by rating in either direction. Lowest
  rating first is the fast way to do a complaint audit.
- **Rating bands** — exceptional (9+), very good (8+), pleasant (6+).
- **Format** — text only, media only, or both. Useful for dropping score-only
  ratings before NLP.
- **Aspect tags** — run once with no tag filter, read `ratingTags` off the
  summary record, then re-run filtered to `BAD_CLEANLINESS` or similar to read
  only the reviews behind one complaint.

## A note about `sort`

Traveloka's review API takes `sort` as a **bare string**. If you send it as an
object (`{"sortType": ...}`) the API answers HTTP 200 and quietly ignores it, so
the data looks sorted but is not. This actor always sends the string form; the
trap is documented here because it bites anyone rolling their own client.

## Xperience reviews work even though Xperience search does not

Traveloka's activity *search* and *detail* endpoints sit behind an AWS WAF
CAPTCHA and cannot be read headlessly. The **review** service does not — so if
you have an activity URL, this actor reads its reviews normally. What it cannot
do is discover activities for you; bring the URLs.

## Cost

Per object: 1 aggregate + 1 aspect-tag call + 1 count + one request per page of
reviews (20 per page by default). Pulling 200 reviews is about 13 requests.

`maxReviewsPerObject` is the stopping point; Traveloka pages until `hasNext` goes
false, and the actor de-duplicates by `reviewId` so an overlapping page cannot
inflate your counts.

## Output record types

- `REVIEW` — one guest review.
- `OBJECT_SUMMARY` — rating, totals and aspect tags for one object.
- `NOT_FOUND` — no reviews and no rating summary; usually the product type does
  not match the URL.
- `GATED` — an endpoint answered with an AWS WAF challenge.
- `ERROR` — a request failed; see `error`.

## A note on robots.txt

Traveloka's `robots.txt` disallows `/api/`, which is where this actor reads from.
Decide for yourself whether that fits your use of the data, your jurisdiction and
your agreement with Traveloka. Reviews are personal content written by real
people — keep request rates modest, and mind your obligations when you store or
republish them.
