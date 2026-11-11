# Google Maps Lead Generation & Contact Scraper

Build B2B outreach lists from Google Maps. Search any category in any city and
get the business name, category, address, phone, website, opening hours and GPS
coordinates — then **automatically enrich each lead with the email addresses and
social accounts found on its own website**.

No login, no Google API key, no browser. Pure HTTP.

---

## What you get per lead

| Field | Notes |
| --- | --- |
| `name`, `categories`, `primaryCategory` | Business name and every category Google assigns |
| `phone`, `phoneE164`, `phoneLocal` | `phoneE164` is dial-ready (`+61282967351`) |
| `website`, `websiteDomain` | As listed on Google |
| **`emails`** | Found on the business website — Google never exposes these |
| **`socialProfiles`** | Instagram, Facebook, LinkedIn, YouTube, TikTok, WhatsApp, Telegram, X |
| `address`, `addressParts`, `region` | Single-line plus split components |
| `latitude`, `longitude` | Real GPS coordinates |
| `openingHours` | Opening hours plus `openNow` and `openingHoursComplete` — see the note below |
| `rating`, `reviewsCount`, `reviewsUrl` | Social-proof signals for prioritising outreach |
| `placeId`, `featureId`, `googleMapsUrl` | Stable identifiers for de-duplication |
| `timezone` | IANA zone — useful for deciding when to call |

---

## Quick start

```json
{
  "searchQueries": ["dentist", "dental clinic"],
  "areaName": "jakarta",
  "maxResultsPerQuery": 200,
  "enrichFromWebsite": true,
  "requireEmail": false,
  "exportFormats": ["csv", "excel"]
}
```

### Targeting a location

A search query always needs a location, otherwise Google picks one from the exit
IP and results are not reproducible. Three ways, in increasing precision:

| Input | Use when |
| --- | --- |
| `areaName: "jakarta"` | Quickest. Built-in cities and countries. |
| `centerLatitude` + `centerLongitude` + `radiusKm` | "Everything within 5 km of this point." |
| `boundingBox: [south, west, north, east]` | Exact area, anywhere on earth. |

Areas are **tiled** into multiple search points for coverage, then every result
is filtered against your exact area using the lead's own GPS coordinates — so a
3 km radius really means 3 km. Verified: a 0.6 km radius returned 20 leads from
40 found, all within 0.489 km.

`tileSizeKm` controls thoroughness: smaller tiles find more businesses and cost
more requests. Left empty, it is chosen from the size of your area.

### Scraping specific businesses

Skip search entirely and pass `placeUrls` (any Google Maps URL, including
`maps.app.goo.gl` short links) or `placeIds` (a Place ID, a numeric CID, or a raw
feature ID). You can combine this with searching in the same run.

### A note on opening hours and review counts

Google serves two different richnesses of record and picks between them by
client. **The Apify platform usually receives the reduced one**, which has no
review count and only today's opening hours. Measured on the platform:

| With `fetchPlaceDetails` | Result |
| --- | --- |
| off | `reviewsCount` 0/25, hours 1 day |
| on | `reviewsCount` **15/15**, `reviewsUrl` 15/15, descriptions 13/15, hours still 1 day for 14/15 |

So `fetchPlaceDetails: true` reliably recovers **review counts, review URLs and
descriptions** at one extra request per lead. The **full 7-day schedule often
cannot be recovered from a datacenter IP at all** — that is Google's behaviour,
not a parsing gap, and every lead carries `openingHoursComplete` so you can tell
which schedules are partial. Running from a non-datacenter IP returns the full
week; a residential proxy is not a workaround here (see Anti-bot and proxy).

The run logs a warning when it detects reduced results and the option is off.

### Narrowing the list

`requirePhone`, `requireWebsite`, `requireEmail` and `minRating` drop leads that
are not worth an outreach slot. `requireEmail` is applied after enrichment, so it
needs `enrichFromWebsite` switched on.

---

## How enrichment works

For each lead with a website: fetch the homepage, extract emails, social handles
and `tel:` numbers. If the homepage has no email, follow **one** same-domain
contact/about link and try there. One hop — this is enrichment, not a crawl.

Two details that separate usable output from noise:

* **Share widgets are filtered out.** Almost every site embeds a Facebook share
  button, so a naive scraper reports that every business has a Facebook page
  called `sharer`. Known widget paths are rejected.
* **Failures are recorded, not thrown.** A dead domain, expired certificate or
  403 lands in `enrichmentStatus` (`ok`, `ok_contact_page`, `no_website`,
  `http_403`, `fetch_failed:…`) and the lead still reaches your dataset with its
  Maps data intact.

Typical yield on a 40-lead run: 24 had a website, 17 gave social accounts, 12
gave an email. Most businesses simply do not publish an email — `requireEmail`
lets you keep only the ones that do.

---

## Anti-bot and proxy

Reconnaissance found **no WAF** on these endpoints: ten TLS fingerprints all
returned 200 from a plain connection.

**Do not use residential proxy here.** This is the opposite of the usual advice,
and it was measured rather than assumed:

| Egress | Result |
| --- | --- |
| No proxy (the default) | works |
| Apify `RESIDENTIAL` | **fails** — Google answers with a consent/CAPTCHA interstitial |

Google polices residential pools far harder than datacenter ranges because those
IPs are widely abused. With no WAF to defeat, the residential IP buys nothing and
costs you the run. The proxy is **off by default**; enable one only to spread
load at high volume, and leave the group list empty so Apify picks a group your
plan actually has — naming a group your account lacks (a free plan has no
`DATACENTER`) fails the run before it starts.

The client impersonates Chrome 150 via `curl_cffi`, warms the Maps cookie jar
once per session, retries with exponential backoff, and rotates TLS profile on
403/429/503.

---

## Limits worth knowing

1. **Results per query are finite.** Google stops serving pages well before the
   true number of businesses in a large area. Coverage comes from tiling (more
   search points), not from paging one search forever. Lower `tileSizeKm` to dig
   deeper into a dense city.
2. **Most businesses have no email anywhere.** Enrichment can only find what the
   website publishes.
3. **Plus codes** are not present in Google's search records and are emitted as
   null rather than guessed.
4. **Category names and opening-hours wording follow `language`.** Set
   `language` and `region` to the market you are targeting.
5. **`reviewsCount` is Google's lifetime total**, not a count of anything this
   actor scraped.

---

## Output shape

Records follow the portfolio envelope — `_input`, `_source`, `_scrapedAt`,
`recordType` — with `_error` / `_errorDetail` on failures. Split a run by
`recordType`: `LEAD` or `ERROR`. An input that fails to resolve produces an
`ERROR` row rather than vanishing, so inputs always reconcile against outputs.

Exports (`exportFormats`) additionally write `leads.csv`, `leads.xlsx`,
`leads.json` and `leads.ndjson` to the key-value store. CSV and Excel columns are
ordered for outreach — name, category, phone, email, website first — and nested
values are flattened (`socialProfiles.instagram`).

---

## Development

```bash
pip install -r requirements.txt
python test_errors.py     # offline: parsing, geo, enrichment, exporters
python test_local.py      # live end-to-end run
```

`test_local.py` reads `_input.json` when present, otherwise uses its built-in
default input. See [CRAWLING_METHOD.md](CRAWLING_METHOD.md) for the endpoint
reconnaissance and the two parsing traps that produce silently wrong data.
