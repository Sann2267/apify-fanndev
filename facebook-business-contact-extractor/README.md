# Facebook Business Contact Extractor

Pull the public contact details businesses put on their own Facebook pages:
email, phone, website, street address, category, price range, services, opening
status, follower count and rating.

Feed it a list of pages, or let it **find** the pages by keyword and country.

No login, no cookies to paste, no proxy required.

## How keyword discovery works, and why

Facebook's own page search is closed to signed-out clients. `/search/pages/`,
`/search/places/`, `/search/top/` — every vertical returns **HTTP 404**. There is
no public "find pages matching X" endpoint any more.

The Ad Library is the exception: it *is* keyword-addressable, it is
country-scoped, and every result names its advertiser's page. So that is where
discovery runs. One useful side effect: every business it finds is currently
spending money on advertising, which is a sharper filter than a keyword match.

A live run for `"dentist"` in the US surfaced **53 distinct business pages** in
one pass.

If you already have a list, skip discovery and pass `pages` instead.

## What you get

| Field | Example |
| --- | --- |
| `pageName`, `primaryCategory` | `BARBUTO \| New York NY`, `Italian restaurant` |
| `email`, `phone` | `info@barbutonyc.com`, `+1 212-924-9700` |
| `website` | `http://www.barbutonyc.com/` (unwrapped from Facebook's redirect) |
| `address` | `113 horatio street, New York, NY, United States, 10014` |
| `priceRange`, `services` | `Price range · ££`, `["Dine in"]` |
| `hoursLabel` | `Closed now` |
| `followers`, `recommendPercent`, `reviewCount` | `6987`, `94.0`, `1236` |
| `contactScore` | `4` — how many of the four channels are published |
| `discoveredVia`, `discoveryQuery` | `ad-library`, `dentist @ US` |

With **`includeTransparency`** on, each page also gives `pageCreationDate`
(`17 February 2010`) and `isRunningAds` — useful for telling an established
business from a week-old one, and a prospect already buying ads from one that
is not.

## Input example

```json
{
  "searchKeywords": ["dental implants", "orthodontist"],
  "countries": ["US", "GB"],
  "maxPages": 300,
  "requireAnyContact": true,
  "includeTransparency": true,
  "exportFormats": ["xlsx"]
}
```

Or, with a list you already have:

```json
{
  "pages": ["BarbutoNYC", "https://www.facebook.com/gramercytavern"],
  "requireEmail": true
}
```

## Honest limits

- **Opening hours are not published.** Facebook shows logged-out visitors only
  `Open now` / `Closed now` — there is no weekly schedule in the payload. The
  field is named `hoursLabel` rather than `hours` so nobody mistakes it for one.
- **A null contact field means the business publishes none**, not that the
  parser missed it. That distinction is the whole point of a lead list, so the
  actor never falls back to guessing a value from nearby text. Addresses found
  in the page's *description* rather than its contact fields are reported
  separately as `emailsFromDescription`.
- **Missing slugs are reported as errors.** Facebook answers HTTP 200 for pages
  that do not exist, so a status-code check would return a blank row for every
  typo. This actor checks the payload size and gives you a `page_not_found`
  error row instead.
- **These pages are big** — 8 to 18 MB each. That is why `concurrency` defaults
  to 4. Raising it speeds a run up and costs memory and bandwidth.
- Follower counts are abbreviated by Facebook; the parsed number is approximate
  and the raw label is kept beside it.
