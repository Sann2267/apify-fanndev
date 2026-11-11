# Facebook Ad Library Full Scraper

Pull complete ad records out of Meta's public Ad Library — the full ad copy, the
headline, the call-to-action, the destination URL, every image and video file
including carousel cards, the flight dates, how many days the ad has been on air,
which Meta surfaces it runs on, and who is paying for it.

Search by **keyword** (everything a niche is running) or by **advertiser**
(everything one page is running), in any country the Ad Library covers.

No login, no cookies to paste, no proxy required.

## What you get

One row per ad:

| Field | Example |
| --- | --- |
| `pageName`, `pageId`, `pageUrl` | `Nordstrom Rack`, `89516513179`, … |
| `adText` | `Buy online and pick up in store for free! Get up to 70% off …` |
| `title`, `linkDescription`, `caption` | `Fast & Free Pickup`, …, `nordstromrack.com` |
| `ctaText`, `ctaType` | `Learn more`, `LEARN_MORE` |
| `linkUrl` | where the click goes |
| `displayFormat` | `VIDEO`, `IMAGE`, `DCO`, … |
| `imageUrls`, `videoUrls`, `thumbnailUrls` | direct CDN files |
| `cards[]` | per-card copy for carousel ads |
| `startDate`, `endDate`, `runningDays`, `isActive` | `2026-09-10T07:00:00Z`, …, `9`, `true` |
| `publisherPlatforms` | `["FACEBOOK","INSTAGRAM","MESSENGER"]` |
| `pageLikeCount`, `pageCategories` | `2518041`, `["Clothing (Brand)"]` |
| `adLibraryUrl` | open the same ad in a browser |
| `totalMatchingAds` | how many ads the search matches in total |

Plus a `RUN_SUMMARY` row with ads collected, how many are active, how many
distinct advertisers and the median days on air.

## Two things worth knowing before you buy

**1. Spend and impressions exist only for political and issue ads.**
`spendText`, `impressionsText` and `targetedCountries` are populated when
`adType` is `political_and_issue_ads`. For ordinary commercial ads Meta does not
publish them anywhere, at any price, so they come back empty. That is Meta's
policy, not a gap in this actor — and no scraper can fill it. Everything else in
the table above is available for commercial ads.

**2. Demographic targeting is not published for commercial ads either.**
The "target wilayah/demografi" you may be looking for is available as
`targetedCountries` on political and issue ads. Age/gender breakdowns are shown
in Meta's own EU transparency reports for a subset of ads and are not part of the
Ad Library search response. This actor returns what the Ad Library actually
serves and leaves the rest null rather than inventing a plausible number.

## Advertiser input takes a numeric page id

The Ad Library addresses advertisers by numeric page id, not by vanity slug. Open
the advertiser in the Ad Library and copy the URL — it contains
`view_all_page_id=<id>` — or paste the id on its own. A plain
`facebook.com/<slug>` URL is rejected with a log line rather than silently
returning nothing.

## Advertiser searches include the influencer ads a brand pays for

Search one advertiser and a few rows will carry somebody else's name in
`pageName` — a creator. Those are branded-content ads: the creator's page posts
them, the brand pays. The row tells you both:
`isBrandedContent: true`, `sponsorPageName: "Nordstrom Rack"`. Nothing has
leaked; this is part of what that advertiser is running, and it is usually the
part a competitor analysis wants to see.

## Input example

```json
{
  "searchTerms": ["running shoes", "protein powder"],
  "countries": ["US", "GB"],
  "adType": "all",
  "activeStatus": "active",
  "mediaType": "video",
  "maxAdsPerQuery": 120,
  "minRunningDays": 14,
  "exportFormats": ["csv"]
}
```

That runs four searches (2 terms × 2 countries), keeps video creatives that have
been on air at least two weeks, and drops a CSV in the key-value store alongside
the dataset.

## How many ads can it get?

Facebook server-renders the first 30 ads of a search. Beyond that, this actor
replays Facebook's own pagination query, 30 ads at a time, up to
`maxAdsPerQuery`. A search matching 26,000 ads will happily give you 1,000 of
them; set the cap to what you actually want to pay for.

If Facebook reshuffles its JavaScript bundles mid-run and the pagination query
cannot be located, the actor keeps the 30 server-rendered ads, logs a warning and
carries on. You get a smaller honest answer, never a failed run.

## Common uses

- **Competitor monitoring** — track every ad a competitor is running, and how
  long each has survived. A creative on air for 90 days is one that works.
- **Swipe files** — collect the copy and creative of a whole niche in one run.
- **Landing-page research** — `linkUrl` shows the exact destination of every ad.
- **Political transparency** — spend and impression ranges, per ad, per country.

## Running it on Apify: use a residential proxy for pagination

Facebook serves the **rendered first page** to any IP, including Apify's. But the
**first pagination request from a datacenter IP** comes back with
`Rate limit exceeded`, so a platform run with no proxy stops at the first 30 ads of each search.

Measured 2026-09-20, same actor, same search, same minute:

| Run | Result |
| --- | --- |
| Apify, no proxy | 30 ads, 1 page — log: `Pagination stopped after 1 page(s): Rate limit exceeded` |
| Apify, `RESIDENTIAL` proxy | 60 ads, 4 pages |
| Local machine, no proxy | 70 ads, 5 pages |

So: switch the Apify proxy on and pick the **RESIDENTIAL** group whenever you
want more than the first page. Running from your own machine needs no proxy at
all.

The actor logs a warning naming the rate limit when it hits one, so a short run
is never silently mistaken for a short result set.

## Notes

- Dynamic-creative ads legitimately contain Meta template tokens such as
  `{{product.name}}` in `adText`. That is the published text, not a parse error.
- `videoUrls` and `imageUrls` are signed CDN links and expire after a while.
  Download what you need during or shortly after the run.
- `endDate` is filled in for running ads too — it is the current end of the
  flight, not a stop date. Read it with `isActive`.
- The Ad Library answers the first request of a session with HTTP 403 and a
  verification challenge. This actor solves it automatically; nothing is required
  from you.
