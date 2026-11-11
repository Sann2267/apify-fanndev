# Facebook Ads Performance Calculator & Benchmarker

Give it a niche. It samples what that niche is actually advertising on Meta right
now, and tells you what the niche has converged on: which calls-to-action,
which creative formats, which headlines, which landing domains, which words and
phrases — and **how long each of those choices stays on air**.

Run two niches and it also compares them side by side.

## Read this before you buy

**The Ad Library does not publish spend, impressions, CTR, CPM or ROAS for
commercial ads.** Meta publishes those only for political and issue ads. Any
tool claiming to calculate a commercial advertiser's CPM from public data is
guessing, and this one will not.

What public data *does* support is **revealed preference**. An advertiser keeps
paying for a creative that works and stops paying for one that does not, so how
long an ad has been running is a real signal — and it is one you can compute for
an entire niche. That is what this actor is built on, and every row says so:
each benchmark carries the `sampleSize` it came from, and the longevity metrics
are labelled as days on air, not as performance.

## What you get

**One `OVERVIEW` row per niche**

| Field | Meaning |
| --- | --- |
| `sampleSize` | ads the benchmark was computed from |
| `activeShare` | % of the sample still running |
| `videoShare` | % carrying a video creative |
| `distinctAdvertisers`, `adsPerAdvertiser` | is the niche crowded or dominated? |
| `medianCopyWords`, `p90CopyWords` | typical ad-copy length |
| `medianRunningDays`, `p90RunningDays`, `maxRunningDays` | how long ads survive here |

**Ranked rows** (`rank`, `value`, `count`, `share`):

- `TOP_CTA` — the buttons the niche uses
- `TOP_FORMAT` — VIDEO / IMAGE / DCO / carousel mix
- `TOP_ADVERTISER` — who is spending the most attention here
- `TOP_PLATFORM` — Facebook / Instagram / Messenger / Audience Network split
- `TOP_HEADLINE` — headlines repeated across the niche
- `TOP_LANDING_DOMAIN` — where the traffic is being sent
- `TOP_WORD`, `TOP_PHRASE_2`, `TOP_PHRASE_3` — the vocabulary of the niche

**Longevity rows** — median and p90 days on air, grouped by:

- `LONGEVITY_BY_CTA` — which button survives longest
- `LONGEVITY_BY_FORMAT` — video vs image, in days
- `LONGEVITY_BY_COPY_LENGTH` — short copy vs long copy, in days

**`COMPARISON` rows** when you run more than one niche: the same CTA, format,
word or phrase with its share in each niche next to it.

## Input example

```json
{
  "niches": [
    { "name": "skincare", "keywords": ["vitamin c serum", "retinol cream"] },
    { "name": "supplements", "keywords": ["protein powder", "creatine"] }
  ],
  "countries": ["US"],
  "sampleSizePerNiche": 200,
  "topN": 15,
  "includeAdSample": true
}
```

The simple form works too — `"niches": ["skincare serum", "protein powder"]` —
where each keyword becomes its own niche.

## How the sample is built

Each niche's ad budget is split across the searches that feed it, so a
two-keyword niche does not quietly collect twice as many ads as a one-keyword
niche and then look twice as confident. Ads are de-duplicated by archive id
across searches.

The sample is **not** filtered before it is measured. Filtering first would
benchmark the filter, not the niche.

## Honest limits

- Words are counted **once per ad**, not once per occurrence, so an ad that
  repeats its slogan six times does not outvote six advertisers who each said it
  once.
- Meta's dynamic-creative tokens (`{{product.name}}`) are stripped before word
  counting. They are real published text, but they are placeholders, and left in
  they would put "product" at the top of every ecommerce niche.
- Longevity groups with fewer than `minGroupSample` ads behind them are dropped
  rather than reported.
- `endDate` exists for running ads too — it is the current end of the flight, not
  a stop date — so "days on air" means *so far* for an active ad.
- A niche where the Ad Library returns nothing produces no benchmark rows and a
  warning in the log, not a fabricated zero.

## Running it on Apify: use a residential proxy for pagination

Facebook serves the **rendered first page** to any IP, including Apify's. But the
**first pagination request from a datacenter IP** comes back with
`Rate limit exceeded`, so a platform run with no proxy stops at the first 30 ads of each search, which caps the sample.

The rate limit is on Facebook's GraphQL endpoint, which every actor in this
family uses for its second page onwards. It was measured on 2026-09-20 with the
Ad Library actor, three runs of the same search within a minute:

| Run | Result |
| --- | --- |
| Apify, no proxy | 30 results, 1 page — log: `Rate limit exceeded` |
| Apify, `RESIDENTIAL` proxy | 60 results, 4 pages |
| Local machine, no proxy | 70 results, 5 pages |

So: switch the Apify proxy on and pick the **RESIDENTIAL** group whenever you
want more than the first page. Running from your own machine needs no proxy at
all.

The actor logs a warning naming the rate limit when it hits one, so a short run
is never silently mistaken for a short result set.
