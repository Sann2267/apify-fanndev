# Crawling method - psacard.com

Recon date: **2026-09-18**, plain HTTP, no proxy, no account.

## The finding that decides everything: TLS profile

Same IP, same minute, same URL - only the impersonated fingerprint differs:

| profile | `/cert/49204884` | `/pop/...` | `api.psacard.com` | `/auctionprices` |
|---|---|---|---|---|
| chrome124 | **403** "Security Check" 160 KB | login | 403 | 200 |
| chrome99_android | **403** | login | 403 | 200 |
| safari17_0 | **403** | login | 403 | 200 |
| edge101 | **403** | login | 403 | 200 |
| **firefox133** | **200 / 145 KB** | login | 429 | 200 |

Cloudflare's rule here blocks Chromium-family fingerprints and lets Firefox
through. This is exactly the case `.ai/CLAUDE.md` warns about: **one profile
failing is a data point, not a verdict** - four of five profiles said "closed"
and the target was open the whole time.

The client keeps a ladder (`firefox133` -> `firefox135` -> `chrome124` ->
`safari17_0`), starts on the one that works today, and remembers the winner for
the life of the run.

## Second gate: the exit IP (found on the platform, not locally)

Locally (Indonesian residential IP) `firefox133` returns 200. The **same build
on Apify returned `isAvailable: false`** -- PSA refuses datacenter ranges even
with the winning TLS profile. Re-running with
`{"useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"]}` returned
`isAvailable: true`.

So this target needs **both** gates cleared: Firefox fingerprint *and* a
residential exit. Residential proxy is the Actor's default for that reason, and
the input schema says so. This mirrors `google-maps-popular-times-analytics` in
this repo, and is the opposite of the other two Maps Actors -- proxy policy is
per target, never portfolio-wide.

## Public vs account-only

| Path | Anonymous result |
|---|---|
| `/cert/<n>` | **200**, full data |
| `/cardfacts` | 200, 161 KB |
| `/auctionprices` (landing) | 200, 84 KB, no item links |
| `/auctionprices/<sport>/<set>/<player>/values/<id>` | **redirects to sign-in** |
| `/pop/<category>/<year>/<set>/<id>` | **redirects to sign-in** |

The research note that led here described "`psacard.com/pop` 200 / 20 KB, open".
That 20 KB **is the sign-in page** - a classic shallow-probe false positive. The
population number this Actor returns comes from the certificate page instead,
which publishes it for the specific item and grade.

## What the cert page publishes

* Item information as `<dt>`/`<dd>` pairs: cert number, grade, label type,
  reverse barcode, year, brand/title, subject, card number, category,
  variety/pedigree.
* Three labelled stat boxes: **PSA Estimate** (`$60.00`), **PSA Population**
  (`4,923`, linked to the set's pop report) and **PSA Pop Higher** (`0`).
* A **"Sales of Similar Items"** table: image, sold price + date, marketplace +
  sale type, grade + the sold copy's own cert number (linked), lot number.

## Gotchas found (and handled in code)

1. **The data lives inside `<div hidden id="S:n">` React streaming
   placeholders.** It is all in the HTML, so no browser is needed - but a
   parser that only reads visible containers finds an empty page.
2. **Class names are Tailwind soup** that changes on redeploy
   (`text-body1 text-primary mt-1 text-center font-semibold uppercase`). The
   stat boxes are therefore located by their **label text**, which is product
   vocabulary and far more stable, then read from the next value element.
3. **The population is a link, the estimate is a paragraph.** The same lookup
   must accept both `<a>` and `<p>` as the value node.
4. **A challenge can arrive with HTTP 200**, so challenges are detected by body
   marker (`Security Check`, `Just a moment`, `cf-mitigated`) as well as status.
5. **Retrying a challenged profile is pointless** - the same fingerprint
   reproduces the same result. The client changes profile instead of retrying.
6. **Account-only sections answer 200 and redirect to `app.collectors.com/signin`.**
   Treated as "not public" and never parsed, so a login page can never be
   mistaken for data.
7. **Sale dates are MM/DD/YY**, normalised to ISO.
8. **A 200 with no `<dt>` pairs raises**, rather than emitting a blank record -
   the difference between "PSA has nothing" and "our parser broke" must stay
   visible in the dataset.

## Verified sample (2026-09-18)

Cert `49204884` - 2018 Panini Prizm Emergent #3 Luka Doncic, GEM MT 10:
PSA Estimate **$60.00**, Population **4,923**, Pop Higher **0**, five
comparable sales from $46.00 to $70.00, latest 2026-09-15 on eBay.

## Not implemented (deliberately)

- **Population reports and auction-price archives** - account-only.
- **Card Facts pages** (`/cardfacts`, open) - editorial content, not structured
  data, and a different product.
