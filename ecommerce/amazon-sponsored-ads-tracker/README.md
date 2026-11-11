# Amazon Sponsored Ads Intelligence

Extract every **Sponsored** placement on page one of Amazon search for the
keywords you care about — with slot positions and a per-keyword advertiser
roll-up showing **who is bidding hardest on what**.

For brands monitoring competitors' ad strategy and share of voice.

No login, no API key. HTTP-only — no browser.

## What you get

Per sponsored placement:

```json
{
  "recordType": "SPONSORED_AD",
  "keyword": "yoga mat",
  "sampleIndex": 1,
  "position": 1,
  "slotBand": "TOP",
  "asin": "B09M8D4JMD",
  "title": "COOLMOON Yoga Mat Non Slip, Anti-Tear 1/4 Thick TPE...",
  "price": 36.99,
  "currency": "$",
  "rating": 4.6,
  "reviewCount": 1284,
  "isPrime": true,
  "productUrl": "https://www.amazon.com/dp/B09M8D4JMD"
}
```

Plus one summary per keyword — the competitive picture:

```
yoga mat           27 ads / 168 slots (16.1%)  topSlot=9  advertisers=16  avgPrice=$61.26
   positions=[1, 1, 2, 2, 3, 3, 3, 4, 4, 11, 11, 12]
   mostPersistentAsins=[{B09M8D4JMD: 2}, {B0F5VW37M7: 2}, {B0HGL1PBQ6: 2}]

wireless earbuds    2 ads /  48 slots ( 4.2%)  topSlot=1  advertisers=2   avgPrice=$23.49
protein powder     12 ads / 156 slots ( 7.7%)  topSlot=4  advertisers=12  avgPrice=$79.06
```

`mostPersistentAsins` is the core signal: an ASIN appearing in **every**
sample is bidding continuously, not just winning one impression.

## ⚠️ Why it samples each keyword more than once

Amazon auctions ad slots **per impression**, so a single fetch is one draw,
not the truth. Measured in one run:

| Keyword | sample 1 | sample 2 | sample 3 |
| --- | --- | --- | --- |
| yoga mat | 13 ads | 1 ad | 13 ads |
| wireless earbuds | 1 | 0 | 1 |
| **protein powder** | **0** | **0** | **12** |

A single fetch of "protein powder" would have told you **nobody advertises
on it** — on a keyword with twelve advertisers. `samplesPerKeyword` defaults
to **3** for exactly this reason. Raise it to 5 for keywords you care about.

It also means **zero ads is a real answer**, not a bug: measured density
across seven keywords ranged 0%–21.7%. A summary row is emitted either way.

## Input

```json
{
  "keywords": ["yoga mat", "wireless earbuds", "protein powder"],
  "marketplace": "com",
  "samplesPerKeyword": 3,
  "includeOrganic": false
}
```

| Field | Description |
| --- | --- |
| `keywords` | Search terms to monitor |
| `marketplace` | com, co.uk, de, fr, it, es, ca, com.au, co.jp, in |
| `samplesPerKeyword` | 1–5 impressions per keyword (default 3) |
| `includeOrganic` | Also emit non-sponsored results, to compare paid vs organic placement |
| `includeSummary` | Per-keyword advertiser roll-up (default on) |
| `maxResultsPerKeyword` | Cap results parsed per sample |
| `delaySeconds` | Pacing — Amazon serves CAPTCHAs to traffic it dislikes |
| `proxyConfiguration` | Residential **strongly recommended** |

## Things worth knowing

**Prices are forced into the marketplace's currency.** Amazon prices pages
from the request's geo-IP — from an Indonesian IP, amazon.com returned
`IDR 336,939.57` instead of `$19.99`. The actor sends the cookie that pins
the currency, so figures stay comparable wherever the run exits from. The
`currency` field is on every row regardless, so never assume USD.

**Amazon search is fussy about TLS fingerprints.** Most are rejected
outright with a 503 block page; the actor ships only the five profiles
verified to work and rotates through them. This is a different ladder from
the Best Sellers actor — same domain, different defences.

**CAPTCHAs are reported, never solved.** A challenged keyword emits
`CAPTCHA_ESCALATION` and the run continues with the rest.

## Known limits

- **Page one only** — that is where the bidding competition is.
- **This measures ad presence and position, not spend.** No public surface
  exposes bids or CPC; slot position and persistence across samples are the
  observable proxies for aggression.
- Ad density may be lower for anonymous traffic than for a logged-in
  shopper, so counts are a **lower bound**.
- Sponsored Brand banners and video ad units were not present on the pages
  tested; the actor captures in-line Sponsored Product placements.

See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the fingerprint matrix, the
currency-forcing tests, the parsing pitfall that inflated ad counts 7×, and
the full density measurements.
