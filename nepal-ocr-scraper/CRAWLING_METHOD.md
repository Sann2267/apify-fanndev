# Crawling Method — Nepal Office of the Company Registrar (OCR)

**Last verified:** 2026-08-26/27

## Which domain, and why the earlier attempt likely timed out

Nepal's Office of the Company Registrar has **three** separate web properties
under gov.np infrastructure, and only one of them is both correct and fast:

| Host | What it is | Result |
|---|---|---|
| `www.ocr.gov.np` | Does not exist / does not resolve as a live host | Connection times out completely (20s+, zero bytes) |
| `nepal.gov.np:8080` | The "National Portal" listing that surfaces highly in search for "OCR Nepal online search" | Responds fast, but `robots.txt` is `Disallow: /` — blocked outright |
| `ocr.gov.np` (no `www`) | OCR's real public marketing/info site | Responds in ~2s, plain `robots.txt` (`Crawl-delay: 10`, no disallow) |
| `camis.ocr.gov.np` | "CAMIS" — OCR's current citizen-facing portal (React/Vite SPA) | Responds in well under 1s; this is where the actual search API lives |
| `application.ocr.gov.np` | Legacy JSF/RichFaces app from an older system generation | Responds fine but stateful/ViewState-bound; not used (see below) |

**A prior research session's timeout was almost certainly a wrong-domain dead
end**, not a real reachability problem — `www.ocr.gov.np` and
`nepal.gov.np:8080` are both natural first guesses from a web search, and
both are genuine dead ends (one unreachable, one robots-blocked). The actual
site (`ocr.gov.np`, no `www`) and its application portal (`camis.ocr.gov.np`)
are fast and healthy.

## Robots.txt

- `ocr.gov.np/robots.txt` → `User-agent: * / Crawl-delay: 10`. No
  Claude/AI-crawler mention, no disallow.
- `camis.ocr.gov.np/robots.txt` → returns HTTP 200 with the SPA's own
  `index.html` (a client-side-router catch-all — there is no dedicated
  robots.txt file on this host at all). No crawl rules are declared here
  either.
- `nepal.gov.np:8080/robots.txt` → `Disallow: /`. Not used by this actor.

## TLS / connectivity gotcha

`camis.ocr.gov.np` serves an **incomplete certificate chain** (missing
intermediate certificate). A client that does OS-level chain building (plain
`curl`, browsers, Python's `requests` via `certifi` + system trust store in
some configs) tolerates this silently; `curl_cffi`'s bundled cert store does
not, and fails every request with `CertificateVerifyError: unable to get
local issuer certificate` until `verify=False` is set explicitly (see
`src/client.py`). Confirmed this is a real server misconfiguration, not a
local/proxy artifact — reproduced identically from a clean residential
connection with no proxy in the loop.

## The public search — reverse-engineered from the SPA's own JS

CAMIS (`camis.ocr.gov.np`) is a modern Vite/React single-page app used for
both authenticated e-filing (registration, annual returns — all behind
login) **and** a small set of explicitly public pages. Its client-side
router config marks the search-company route `whiteList: true` (i.e.
reachable with no auth token), and its page title literally reads "Search
Company" with a "Back to Login" button — this is OCR's own public lookup
tool, not an internal API stumbled into by accident.

1. The SPA's entry bundle (`/assets/index-<hash>.js`) references an
   `axios` client with `baseURL: "https://camis.ocr.gov.np/gateway"`.
2. Its route table lazy-loads a `SearchCompany-<hash>.js` chunk for
   `/search-company`. Fetching that chunk directly (`GET
   /assets/SearchCompany-<hash>.js`) reveals the exact API call in full,
   unminified enough to read:

   ```
   POST https://camis.ocr.gov.np/gateway/external/api/company-registration/search-company-details
   Content-Type: application/json

   {"companyNameEnglish": "...", "companyNameNepali": "...", "companyRegistrationNumber": "..."}
   ```

3. The frontend debounces keystrokes (500ms) and always sends all three
   fields, blank for the two not in use — the UI is a two-option toggle
   (Company Name / Registration Number) plus one Devanagari-aware textbox.
   `src/extractor.py`'s `build_request_body` reproduces this dispatch:
   digits-only input → `companyRegistrationNumber`; Devanagari-script
   input → `companyNameNepali`; anything else → `companyNameEnglish`.

No cookies, no CSRF token, no session, no Authorization header of any kind
were required — confirmed with a completely cold `curl_cffi` client across
dozens of calls (specific name, exact registration number, a deliberately
invented garbage string, and one deliberately unbounded blank-everything
query).

## Response shape

```json
{
  "status": true,
  "message": "Basic Information list fetched successfully !!",
  "data": [ { "...": "one object per matched company, see README" } ]
}
```

A **zero-match query returns a clean `"data": []`** with `HTTP 200` and
`"status": true` — not an error, not a different status code. Confirmed on
`companyNameEnglish: "zzzznonexistentxyz999"`. `src/extractor.py` raises
`NoResultsFound` only when this array comes back empty.

## The critical gotcha: no server-side result cap or pagination

This endpoint has **no page size, no `limit`/`offset`, no truncation of any
kind** on the server side:

- Querying the single common word `"nepal"` (`companyNameEnglish: "nepal"`)
  returned **10,652 matched companies** in one ~8.6 MB JSON response.
- Sending **all three fields blank** — which the UI's own textbox would
  never normally produce, but the API does not reject — returned the
  **entire public company registry** in one response: ~53 MB, tens of
  seconds to download.

This actor never sends a blank-everything query, and truncates the returned
array to `maxResultsPerQuery` (default 50, max 2000) before writing records
to the dataset — see `search_one_query` in `src/main.py`. A user who wants
exhaustive results for a broad term should be aware the true match count may
exceed what they requested; the actor logs the true total when it truncates.

## Data quirk: dates are Bikram Sambat, not Gregorian

`registrationDateBSEn`/`registrationDateBSNp` are in the **Bikram Sambat**
calendar used by the Nepali government (e.g. `"2081-03-31"` BS, not
Gregorian) — passed through unconverted, per this project's raw-passthrough
convention. Do not treat these as ISO Gregorian dates downstream.

## Data quirk: `isRokka`

`isRokka` is a real, meaningful boolean on the public register — a company
under "Rokka" is subject to a legal freeze/injunction (recorded by OCR, e.g.
due to litigation or a dispute) restricting further filings against it.
Confirmed a real `true` case during testing ("HOTEL EVEREST INTERNATIONAL",
registration number 98138).

## What is genuinely public vs. not

Only the "basic information" record shown in the README (name EN/NP,
registration number EN/NP, registration date BS, company type, address
EN/NP, `isRokka`) is reachable without login. Unlike some other registries
in this collection, OCR does **not** expose a public "full profile" page
with directors, shareholders, or capital structure — that data lives behind
CAMIS's login wall (confirmed by reading the router: every route carrying
director/shareholder/capital-structure components requires auth; only
`search-company` is whitelisted). The legacy `application.ocr.gov.np` JSF app
was also examined (`CompanyDetails.jsp`, a "Search Company by Registration
Number" form with no visible login wall) but was **not** pursued further:
it is a stateful RichFaces ViewState postback flow (comparatively brittle to
script, one more HTTP round-trip per query) that would return the same or
less information than the CAMIS API already provides cleanly and
statelessly.

## Diff cadence

Quarterly smoke test recommended. CAMIS is an actively developed portal
(webpack/Vite asset hashes will change on every deploy); if `SEARCH_URL`
starts 404ing, re-fetch `camis.ocr.gov.np`'s current entry bundle, find the
new `SearchCompany-<hash>.js` chunk reference, and re-read it the same way
described above.
